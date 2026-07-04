from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import stripe
from django.conf import settings

from .models import Payment


def secret_key_for_mode(stripe_mode: str) -> str:
    if stripe_mode == Payment.StripeMode.LIVE:
        return settings.CONFIG.stripe.live_secret_key
    return settings.CONFIG.stripe.test_secret_key


def webhook_secret_for_mode(stripe_mode: str) -> str:
    if stripe_mode == Payment.StripeMode.LIVE:
        return settings.CONFIG.stripe.live_webhook_secret
    return settings.CONFIG.stripe.test_webhook_secret


def get_stripe_value(stripe_object: object, key: str, default: Any = None) -> Any:
    if isinstance(stripe_object, dict):
        return stripe_object.get(key, default)
    return getattr(stripe_object, key, default)


def timestamp_to_datetime(timestamp: int | None) -> datetime | None:
    if timestamp is None:
        return None
    return datetime.fromtimestamp(timestamp, tz=UTC)


def create_checkout_session(
    *,
    payment: Payment,
    line_items: list[dict[str, object]],
    success_url: str,
    cancel_url: str,
    metadata: dict[str, str],
):
    stripe.api_key = secret_key_for_mode(payment.stripe_mode)
    return stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata=metadata,
        payment_intent_data={"metadata": metadata},
        idempotency_key=f"payment:{payment.id}:checkout:create",
    )
