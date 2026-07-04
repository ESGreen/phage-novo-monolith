from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from camp.models import CampYear, TaxAddOn
from camp.taxes import is_tax_waived
from core.models import SiteSettings

from . import stripe_client
from .models import Payment, PaymentAddOn, PaymentLog


class CheckoutBlocked(RuntimeError):
    pass


@dataclass(frozen=True)
class CheckoutResult:
    payment: Payment
    checkout_url: str


def get_paid_payment(user: object, camp_year: CampYear) -> Payment | None:
    return Payment.objects.filter(
        user=user,
        camp_year=camp_year,
        status=Payment.Status.PAID,
    ).first()


def get_unexpired_created_payment(user: object, camp_year: CampYear) -> Payment | None:
    return Payment.objects.filter(
        user=user,
        camp_year=camp_year,
        status=Payment.Status.CREATED,
        checkout_expires_at__gt=timezone.now(),
    ).first()


def create_tax_checkout(user: object, camp_year: CampYear, form) -> CheckoutResult:
    if get_paid_payment(user, camp_year) is not None:
        raise CheckoutBlocked("Taxes are already paid for this year.")
    if is_tax_waived(user, camp_year):
        raise CheckoutBlocked("Taxes are waived for this year.")
    if get_unexpired_created_payment(user, camp_year) is not None:
        raise CheckoutBlocked("A checkout session is already open for this year.")

    tax_tier = form.cleaned_data["tax_tier"]
    selected_add_ons = list(form.cleaned_data.get("add_ons") or [])
    tax_amount_cents = form.cleaned_data["tax_amount_cents"]
    add_on_amount_cents = form.cleaned_data["add_on_amount_cents"]
    total_amount_cents = form.cleaned_data["total_amount_cents"]
    effective_minimum_cents = form.cleaned_data["effective_minimum_cents"]
    now = timezone.now()

    with transaction.atomic():
        payment = Payment.objects.create(
            user=user,
            camp_year=camp_year,
            status=Payment.Status.CREATED,
            stripe_mode=SiteSettings.load().stripe_mode,
            tax_amount_cents=tax_amount_cents,
            add_on_amount_cents=add_on_amount_cents,
            total_amount_cents=total_amount_cents,
            tax_tier_name_snapshot=tax_tier.name,
            tax_tier_minimum_cents_snapshot=effective_minimum_cents,
            checkout_expires_at=now + timedelta(hours=1),
        )
        for add_on in selected_add_ons:
            PaymentAddOn.objects.create(
                payment=payment,
                tax_add_on=add_on,
                name_snapshot=add_on.name,
                amount_cents_snapshot=add_on.amount_cents,
            )

        PaymentLog.objects.create(
            payment=payment,
            level=PaymentLog.Level.INFO,
            event_type="checkout.create.request",
            stripe_mode=payment.stripe_mode,
            message="Creating Stripe Checkout session.",
        )

    session = stripe_client.create_checkout_session(
        payment=payment,
        line_items=_line_items(camp_year, payment, selected_add_ons),
        success_url=_success_url(camp_year),
        cancel_url=_cancel_url(camp_year),
        metadata=_metadata(payment),
    )
    session_id = stripe_client.get_stripe_value(session, "id")
    checkout_url = stripe_client.get_stripe_value(session, "url")
    expires_at = stripe_client.timestamp_to_datetime(
        stripe_client.get_stripe_value(session, "expires_at")
    )

    payment.stripe_checkout_session_id = session_id
    payment.checkout_created_at = now
    if expires_at is not None:
        payment.checkout_expires_at = expires_at
    payment.save(
        update_fields=[
            "stripe_checkout_session_id",
            "checkout_created_at",
            "checkout_expires_at",
            "updated_at",
        ]
    )
    PaymentLog.objects.create(
        payment=payment,
        level=PaymentLog.Level.INFO,
        event_type="checkout.create.success",
        stripe_mode=payment.stripe_mode,
        message="Stripe Checkout session created.",
        redacted_payload={"stripe_checkout_session_id": session_id},
    )
    return CheckoutResult(payment=payment, checkout_url=checkout_url)


def _line_items(
    camp_year: CampYear,
    payment: Payment,
    selected_add_ons: list[TaxAddOn],
) -> list[dict[str, object]]:
    line_items: list[dict[str, object]] = [
        {
            "price_data": {
                "currency": "usd",
                "product_data": {
                    "name": f"{camp_year.year} Camp Taxes - {payment.tax_tier_name_snapshot}",
                },
                "unit_amount": payment.tax_amount_cents,
            },
            "quantity": 1,
        }
    ]
    for add_on in selected_add_ons:
        line_items.append(
            {
                "price_data": {
                    "currency": "usd",
                    "product_data": {"name": add_on.name},
                    "unit_amount": add_on.amount_cents,
                },
                "quantity": 1,
            }
        )
    return line_items


def _metadata(payment: Payment) -> dict[str, str]:
    return {
        "payment_id": str(payment.id),
        "user_id": str(payment.user_id),
        "camp_year_id": str(payment.camp_year_id),
        "camp_year": str(payment.camp_year.year),
        "stripe_mode": payment.stripe_mode,
        "tax_tier_name": payment.tax_tier_name_snapshot,
        "tax_amount_cents": str(payment.tax_amount_cents),
        "add_on_amount_cents": str(payment.add_on_amount_cents),
        "total_amount_cents": str(payment.total_amount_cents),
    }


def _success_url(camp_year: CampYear) -> str:
    base_url = settings.CONFIG.site.base_url
    return f"{base_url}/{camp_year.year}/taxes/return/?session_id={{CHECKOUT_SESSION_ID}}"


def _cancel_url(camp_year: CampYear) -> str:
    return f"{settings.CONFIG.site.base_url}/{camp_year.year}/taxes/"
