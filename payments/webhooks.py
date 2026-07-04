from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import stripe
from django.db import models, transaction
from django.utils import timezone

from core.models import SiteSettings

from .models import Payment, PaymentLog
from .stripe_client import webhook_secret_for_mode


class WebhookSignatureError(RuntimeError):
    pass


def handle_webhook(payload: bytes, signature: str) -> None:
    stripe_mode, event = _verify_event(payload, signature)
    event_type = _value(event, "type", default="")
    event_id = _value(event, "id", default="")
    data_object = _value(event, "data", "object", default={})
    _log(None, PaymentLog.Level.INFO, event_type, stripe_mode, event_id, "Webhook received.")

    if event_type == "checkout.session.completed":
        _handle_checkout_completed(data_object, stripe_mode, event_id)
    elif event_type == "checkout.session.expired":
        _mark_created_payment(data_object, Payment.Status.CANCELLED, stripe_mode, event_id)
    elif event_type == "payment_intent.payment_failed":
        _mark_created_payment(data_object, Payment.Status.FAILED, stripe_mode, event_id)
    elif event_type == "charge.refunded":
        _handle_refund(data_object, stripe_mode, event_id)


def _verify_event(payload: bytes, signature: str):
    current_mode = SiteSettings.load().stripe_mode
    modes = [current_mode]
    other_mode = (
        Payment.StripeMode.LIVE
        if current_mode == Payment.StripeMode.TEST
        else Payment.StripeMode.TEST
    )
    modes.append(other_mode)
    verified = []
    for stripe_mode in modes:
        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                webhook_secret_for_mode(stripe_mode),
            )
        except Exception:
            continue
        verified.append((stripe_mode, event))
    if len(verified) != 1:
        _log(
            None,
            PaymentLog.Level.WARNING,
            "webhook.signature.failure",
            "",
            "",
            "Webhook signature verification failed.",
        )
        raise WebhookSignatureError("Webhook signature verification failed.")
    return verified[0]


def _handle_checkout_completed(session: object, stripe_mode: str, event_id: str) -> None:
    metadata = _value(session, "metadata", default={}) or {}
    payment_id = _metadata_value(metadata, "payment_id")
    if not payment_id:
        _log(
            None,
            PaymentLog.Level.WARNING,
            "webhook.requires_review",
            stripe_mode,
            event_id,
            "Missing payment_id metadata.",
        )
        return

    with transaction.atomic():
        try:
            payment = Payment.objects.select_for_update().get(pk=int(payment_id))
        except (Payment.DoesNotExist, ValueError):
            _log(
                None,
                PaymentLog.Level.WARNING,
                "webhook.requires_review",
                stripe_mode,
                event_id,
                "Unknown payment_id metadata.",
            )
            return

        if payment.status == Payment.Status.PAID:
            _log(
                payment,
                PaymentLog.Level.INFO,
                "webhook.duplicate",
                stripe_mode,
                event_id,
                "Payment is already paid.",
            )
            return

        errors = _checkout_completion_errors(payment, session, metadata, stripe_mode)
        if errors:
            payment.status = Payment.Status.REQUIRES_REVIEW
            payment.save(update_fields=["status", "updated_at"])
            _log(
                payment,
                PaymentLog.Level.WARNING,
                "webhook.requires_review",
                stripe_mode,
                event_id,
                "; ".join(errors),
            )
            return

        payment.status = Payment.Status.PAID
        payment.paid_at = _stripe_created_at(session) or timezone.now()
        payment.stripe_payment_intent_id = _value(session, "payment_intent", default="") or None
        if not payment.stripe_checkout_session_id:
            payment.stripe_checkout_session_id = _value(session, "id", default="")
        payment.save(
            update_fields=[
                "status",
                "paid_at",
                "stripe_payment_intent_id",
                "stripe_checkout_session_id",
                "updated_at",
            ]
        )
        _log(
            payment,
            PaymentLog.Level.INFO,
            "webhook.payment_paid",
            stripe_mode,
            event_id,
            "Payment marked paid.",
        )


def _checkout_completion_errors(
    payment: Payment,
    session: object,
    metadata: object,
    stripe_mode: str,
) -> list[str]:
    errors = []
    session_id = _value(session, "id", default="")
    if str(payment.user_id) != str(_metadata_value(metadata, "user_id")):
        errors.append("User metadata mismatch")
    camp_year_id = _metadata_value(metadata, "camp_year_id")
    camp_year = _metadata_value(metadata, "camp_year")
    if str(payment.camp_year_id) != str(camp_year_id) and str(payment.camp_year.year) != str(
        camp_year
    ):
        errors.append("Camp year metadata mismatch")
    if payment.stripe_mode != stripe_mode:
        errors.append("Stripe mode mismatch")
    if payment.stripe_checkout_session_id and payment.stripe_checkout_session_id != session_id:
        errors.append("Checkout Session ID mismatch")
    if _value(session, "payment_status", default="") != "paid":
        errors.append("Checkout Session is not paid")
    if _value(session, "amount_total") != payment.total_amount_cents:
        errors.append("Amount mismatch")
    if str(_value(session, "currency", default="")).lower() != "usd":
        errors.append("Currency mismatch")
    if (
        Payment.objects.filter(
            user=payment.user,
            camp_year=payment.camp_year,
            status=Payment.Status.PAID,
        )
        .exclude(pk=payment.pk)
        .exists()
    ):
        errors.append("Another paid payment exists")
    return errors


def _mark_created_payment(
    data_object: object, status: str, stripe_mode: str, event_id: str
) -> None:
    payment = _find_payment(data_object)
    if payment is None:
        _log(
            None,
            PaymentLog.Level.WARNING,
            "webhook.payment_missing",
            stripe_mode,
            event_id,
            "Payment not found.",
        )
        return
    if payment.status == Payment.Status.CREATED:
        payment.status = status
        payment.save(update_fields=["status", "updated_at"])
        _log(
            payment,
            PaymentLog.Level.INFO,
            "webhook.state_change",
            stripe_mode,
            event_id,
            f"Payment marked {status}.",
        )


def _handle_refund(charge: object, stripe_mode: str, event_id: str) -> None:
    payment = _find_payment(charge)
    if payment is None:
        _log(
            None,
            PaymentLog.Level.WARNING,
            "webhook.payment_missing",
            stripe_mode,
            event_id,
            "Payment not found.",
        )
        return
    amount = _value(charge, "amount")
    amount_refunded = _value(charge, "amount_refunded")
    if (
        payment.status == Payment.Status.PAID
        and amount == amount_refunded == payment.total_amount_cents
    ):
        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=["status", "updated_at"])
        _log(
            payment,
            PaymentLog.Level.INFO,
            "webhook.state_change",
            stripe_mode,
            event_id,
            "Payment marked refunded.",
        )
    else:
        payment.status = Payment.Status.REQUIRES_REVIEW
        payment.save(update_fields=["status", "updated_at"])
        _log(
            payment,
            PaymentLog.Level.WARNING,
            "webhook.requires_review",
            stripe_mode,
            event_id,
            "Refund requires review.",
        )


def _find_payment(data_object: object) -> Payment | None:
    metadata = _value(data_object, "metadata", default={}) or {}
    payment_id = _metadata_value(metadata, "payment_id")
    if payment_id:
        try:
            return Payment.objects.get(pk=int(payment_id))
        except (Payment.DoesNotExist, ValueError):
            return None
    session_id = _value(data_object, "id", default="")
    payment_intent_id = _value(data_object, "payment_intent", default="") or session_id
    return Payment.objects.filter(
        models.Q(stripe_checkout_session_id=session_id)
        | models.Q(stripe_payment_intent_id=payment_intent_id)
    ).first()


def _log(
    payment: Payment | None,
    level: str,
    event_type: str,
    stripe_mode: str,
    event_id: str,
    message: str,
) -> None:
    PaymentLog.objects.create(
        payment=payment,
        level=level,
        event_type=event_type,
        stripe_mode=stripe_mode,
        stripe_event_id=event_id,
        message=message,
        redacted_payload={"event_type": event_type} if event_type else None,
    )


def _value(data: object, *keys: str, default: Any = None) -> Any:
    current = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key, default)
        else:
            current = getattr(current, key, default)
        if current is default:
            return default
    return current


def _metadata_value(metadata: object, key: str) -> object:
    return _value(metadata, key, default=None)


def _stripe_created_at(session: object):
    created = _value(session, "created")
    if created is None:
        return None
    return datetime.fromtimestamp(created, tz=UTC)
