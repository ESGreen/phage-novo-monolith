from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from camp.models import CampYear
from payments.models import Payment, PaymentLog

pytestmark = pytest.mark.django_db


def create_user(email: str = "member@example.com"):
    return get_user_model().objects.create_user(email=email, password="test-password-1")


def create_camp_year(year: int = 2026) -> CampYear:
    return CampYear.objects.create(year=year)


def create_payment(
    status: str = Payment.Status.CREATED,
    total_amount_cents: int = 10000,
) -> Payment:
    user = create_user()
    camp_year = create_camp_year()
    paid_at = timezone.now() if status == Payment.Status.PAID else None
    return Payment.objects.create(
        user=user,
        camp_year=camp_year,
        status=status,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=total_amount_cents,
        add_on_amount_cents=0,
        total_amount_cents=total_amount_cents,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=total_amount_cents,
        stripe_checkout_session_id="cs_test_123",
        stripe_payment_intent_id="pi_test_123",
        checkout_expires_at=timezone.now() + timedelta(hours=1),
        paid_at=paid_at,
    )


def completed_event(payment: Payment, amount_total: int | None = None, currency: str = "usd"):
    return {
        "id": "evt_completed",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_test_123",
                "payment_intent": "pi_test_123",
                "payment_status": "paid",
                "amount_total": amount_total or payment.total_amount_cents,
                "currency": currency,
                "created": int(timezone.now().timestamp()),
                "metadata": {
                    "payment_id": str(payment.id),
                    "user_id": str(payment.user_id),
                    "camp_year_id": str(payment.camp_year_id),
                    "camp_year": str(payment.camp_year.year),
                    "stripe_mode": payment.stripe_mode,
                },
            }
        },
    }


def post_webhook(client, mocker, event):
    mocker.patch(
        "payments.webhooks.stripe.Webhook.construct_event",
        side_effect=[event, Exception("wrong secret")],
    )
    return client.post(
        "/stripe/webhook/",
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="sig",
    )


def test_invalid_webhook_signature_returns_400(client, mocker) -> None:
    mocker.patch(
        "payments.webhooks.stripe.Webhook.construct_event",
        side_effect=Exception("bad signature"),
    )

    response = client.post(
        "/stripe/webhook/",
        data=b"{}",
        content_type="application/json",
        HTTP_STRIPE_SIGNATURE="sig",
    )

    assert response.status_code == 400
    assert PaymentLog.objects.filter(event_type="webhook.signature.failure").exists()


def test_checkout_completed_marks_payment_paid(client, mocker) -> None:
    payment = create_payment()

    response = post_webhook(client, mocker, completed_event(payment))

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID
    assert payment.paid_at is not None
    assert payment.stripe_payment_intent_id == "pi_test_123"


def test_checkout_completed_amount_mismatch_requires_review(client, mocker) -> None:
    payment = create_payment()

    response = post_webhook(client, mocker, completed_event(payment, amount_total=9999))

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REQUIRES_REVIEW


def test_checkout_completed_currency_mismatch_requires_review(client, mocker) -> None:
    payment = create_payment()

    response = post_webhook(client, mocker, completed_event(payment, currency="eur"))

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REQUIRES_REVIEW


def test_duplicate_checkout_completed_is_idempotent(client, mocker) -> None:
    payment = create_payment(status=Payment.Status.PAID)

    response = post_webhook(client, mocker, completed_event(payment))

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.PAID
    assert PaymentLog.objects.filter(event_type="webhook.duplicate").exists()


def test_checkout_expired_marks_created_payment_cancelled(client, mocker) -> None:
    payment = create_payment()
    event = {
        "id": "evt_expired",
        "type": "checkout.session.expired",
        "data": {"object": {"id": "cs_test_123", "metadata": {"payment_id": str(payment.id)}}},
    }

    response = post_webhook(client, mocker, event)

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CANCELLED


def test_payment_intent_failed_marks_created_payment_failed(client, mocker) -> None:
    payment = create_payment()
    event = {
        "id": "evt_failed",
        "type": "payment_intent.payment_failed",
        "data": {"object": {"id": "pi_test_123", "metadata": {"payment_id": str(payment.id)}}},
    }

    response = post_webhook(client, mocker, event)

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.FAILED


def test_full_refund_marks_paid_payment_refunded(client, mocker) -> None:
    payment = create_payment(status=Payment.Status.PAID)
    event = {
        "id": "evt_refund",
        "type": "charge.refunded",
        "data": {
            "object": {
                "payment_intent": "pi_test_123",
                "amount": 10000,
                "amount_refunded": 10000,
                "metadata": {"payment_id": str(payment.id)},
            }
        },
    }

    response = post_webhook(client, mocker, event)

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REFUNDED


def test_partial_refund_requires_review(client, mocker) -> None:
    payment = create_payment(status=Payment.Status.PAID)
    event = {
        "id": "evt_partial_refund",
        "type": "charge.refunded",
        "data": {
            "object": {
                "payment_intent": "pi_test_123",
                "amount": 10000,
                "amount_refunded": 5000,
                "metadata": {"payment_id": str(payment.id)},
            }
        },
    }

    response = post_webhook(client, mocker, event)

    assert response.status_code == 200
    payment.refresh_from_db()
    assert payment.status == Payment.Status.REQUIRES_REVIEW
