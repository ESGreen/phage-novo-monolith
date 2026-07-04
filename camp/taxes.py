from __future__ import annotations

from decimal import Decimal

from django.db.models import QuerySet
from django.utils import timezone

from .models import CampYear, TaxAddOn, TaxOverride, TaxTier


def available_tax_tiers(camp_year: CampYear, now=None) -> QuerySet[TaxTier]:
    current_time = now or timezone.now()
    return TaxTier.objects.filter(
        camp_year=camp_year,
        start_date__lte=current_time,
        expiration_date__gt=current_time,
    ).order_by("display_order", "minimum_amount_cents", "name")


def available_tax_add_ons(camp_year: CampYear, now=None) -> QuerySet[TaxAddOn]:
    current_time = now or timezone.now()
    return TaxAddOn.objects.filter(
        camp_year=camp_year,
        start_date__lte=current_time,
        expiration_date__gt=current_time,
    ).order_by("display_order", "amount_cents", "name")


def get_tax_override(user: object, camp_year: CampYear) -> TaxOverride | None:
    return TaxOverride.objects.filter(user=user, camp_year=camp_year).first()


def is_tax_waived(user: object, camp_year: CampYear) -> bool:
    tax_override = get_tax_override(user, camp_year)
    return (
        tax_override is not None
        and tax_override.override_type == TaxOverride.OverrideType.WAIVED
    )


def effective_minimum_cents(user: object, camp_year: CampYear, tier: TaxTier) -> int:
    tax_override = get_tax_override(user, camp_year)
    if (
        tax_override is not None
        and tax_override.override_type == TaxOverride.OverrideType.REDUCED_MINIMUM
    ):
        return tax_override.reduced_minimum_amount_cents or tier.minimum_amount_cents
    return tier.minimum_amount_cents


def decimal_dollars_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1")))
