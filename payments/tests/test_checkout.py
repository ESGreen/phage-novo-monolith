from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from payments.models import Payment, PaymentAddOn

pytestmark = pytest.mark.django_db


def create_user(email: str = "member@example.com"):
    return get_user_model().objects.create_user(email=email, password="test-password-1")


def create_camp_year(year: int = 2026) -> CampYear:
    return CampYear.objects.create(year=year)


def create_tax_tier(camp_year: CampYear, name: str = "Standard", minimum: int = 10000) -> TaxTier:
    now = timezone.now()
    return TaxTier.objects.create(
        camp_year=camp_year,
        name=name,
        minimum_amount_cents=minimum,
        start_date=now - timedelta(days=1),
        expiration_date=now + timedelta(days=1),
    )


def create_tax_add_on(camp_year: CampYear, name: str = "Hoodie", amount: int = 2500) -> TaxAddOn:
    now = timezone.now()
    return TaxAddOn.objects.create(
        camp_year=camp_year,
        name=name,
        amount_cents=amount,
        start_date=now - timedelta(days=1),
        expiration_date=now + timedelta(days=1),
    )


def mock_checkout_session(mocker, session_id: str = "cs_test_123"):
    return mocker.patch(
        "payments.stripe_client.stripe.checkout.Session.create",
        return_value={
            "id": session_id,
            "url": f"https://checkout.example/{session_id}",
            "expires_at": int((timezone.now() + timedelta(hours=1)).timestamp()),
        },
    )


def create_payment(
    user,
    camp_year: CampYear,
    status: str = Payment.Status.CREATED,
    checkout_expires_at=None,
) -> Payment:
    paid_at = timezone.now() if status == Payment.Status.PAID else None
    return Payment.objects.create(
        user=user,
        camp_year=camp_year,
        status=status,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        checkout_expires_at=checkout_expires_at,
        paid_at=paid_at,
    )


def test_checkout_creates_payment_and_redirects_to_stripe(client, mocker) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year, name="Sustainer", minimum=10000)
    add_on = create_tax_add_on(camp_year, name="Hoodie", amount=2500)
    create_mock = mock_checkout_session(mocker)

    response = client.post(
        "/2026/taxes/",
        {
            "tax_tier": str(tier.id),
            "tax_amount_dollars": "125.00",
            "add_ons": [str(add_on.id)],
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "https://checkout.example/cs_test_123"
    payment = Payment.objects.get()
    assert payment.status == Payment.Status.CREATED
    assert payment.stripe_mode == Payment.StripeMode.TEST
    assert payment.tax_amount_cents == 12500
    assert payment.add_on_amount_cents == 2500
    assert payment.total_amount_cents == 15000
    assert payment.tax_tier_name_snapshot == "Sustainer"
    assert payment.tax_tier_minimum_cents_snapshot == 10000
    assert payment.stripe_checkout_session_id == "cs_test_123"
    assert payment.checkout_expires_at is not None
    assert PaymentAddOn.objects.get(payment=payment).name_snapshot == "Hoodie"

    kwargs = create_mock.call_args.kwargs
    assert kwargs["payment_method_types"] == ["card"]
    assert kwargs["success_url"] == (
        "http://testserver/2026/taxes/return/?session_id={CHECKOUT_SESSION_ID}"
    )
    assert kwargs["cancel_url"] == "http://testserver/2026/taxes/"
    assert kwargs["metadata"]["payment_id"] == str(payment.id)
    assert kwargs["metadata"]["user_id"] == str(user.id)
    assert kwargs["metadata"]["camp_year"] == "2026"
    assert kwargs["metadata"] == kwargs["payment_intent_data"]["metadata"]
    assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 12500
    assert kwargs["line_items"][1]["price_data"]["unit_amount"] == 2500
    assert kwargs["idempotency_key"] == f"payment:{payment.id}:checkout:create"


def test_checkout_is_blocked_when_already_paid(client, mocker) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year)
    create_payment(user, camp_year, status=Payment.Status.PAID)
    create_mock = mock_checkout_session(mocker)

    response = client.post(
        "/2026/taxes/",
        {"tax_tier": str(tier.id), "tax_amount_dollars": "100.00", "add_ons": []},
    )

    assert response.status_code == 200
    assert b"Taxes Paid" in response.content
    assert Payment.objects.count() == 1
    create_mock.assert_not_called()


def test_checkout_is_blocked_by_unexpired_created_payment(client, mocker) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year)
    create_payment(user, camp_year, checkout_expires_at=timezone.now() + timedelta(minutes=30))
    create_mock = mock_checkout_session(mocker)

    response = client.post(
        "/2026/taxes/",
        {"tax_tier": str(tier.id), "tax_amount_dollars": "100.00", "add_ons": []},
    )

    assert response.status_code == 200
    assert b"Checkout Pending" in response.content
    assert Payment.objects.count() == 1
    create_mock.assert_not_called()


def test_checkout_allows_new_attempt_when_created_payment_expired(client, mocker) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year)
    create_payment(user, camp_year, checkout_expires_at=timezone.now() - timedelta(minutes=1))
    mock_checkout_session(mocker, session_id="cs_new")

    response = client.post(
        "/2026/taxes/",
        {"tax_tier": str(tier.id), "tax_amount_dollars": "100.00", "add_ons": []},
    )

    assert response.status_code == 302
    assert response["Location"] == "https://checkout.example/cs_new"
    assert Payment.objects.count() == 2


def test_checkout_allows_waived_taxes_with_add_ons(client, mocker) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    create_tax_tier(camp_year)
    add_on = create_tax_add_on(camp_year, name="Hoodie", amount=2500)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    create_mock = mock_checkout_session(mocker)

    response = client.post(
        "/2026/taxes/",
        {"tax_tier": "waived", "tax_amount_dollars": "0.00", "add_ons": [str(add_on.id)]},
    )

    assert response.status_code == 302
    assert response["Location"] == "https://checkout.example/cs_test_123"
    payment = Payment.objects.get()
    assert payment.tax_amount_cents == 0
    assert payment.add_on_amount_cents == 2500
    assert payment.total_amount_cents == 2500
    assert payment.tax_tier_name_snapshot == "Waived Taxes"
    assert payment.tax_tier_minimum_cents_snapshot == 0
    assert PaymentAddOn.objects.get(payment=payment).name_snapshot == "Hoodie"
    kwargs = create_mock.call_args.kwargs
    assert len(kwargs["line_items"]) == 1
    assert kwargs["line_items"][0]["price_data"]["unit_amount"] == 2500


def test_checkout_return_page_never_marks_payment_paid(client) -> None:
    user = create_user()
    client.force_login(user)
    camp_year = create_camp_year()
    payment = create_payment(
        user,
        camp_year,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    payment.stripe_checkout_session_id = "cs_return"
    payment.save(update_fields=["stripe_checkout_session_id", "updated_at"])

    response = client.get("/2026/taxes/return/?session_id=cs_return")

    assert response.status_code == 200
    assert b"Payment Pending" in response.content
    payment.refresh_from_db()
    assert payment.status == Payment.Status.CREATED
