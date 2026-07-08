from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone

from camp.forms import TaxSelectionForm
from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from camp.taxes import (
    available_tax_add_ons,
    available_tax_tiers,
    effective_minimum_cents,
    is_tax_waived,
)

pytestmark = pytest.mark.django_db


def create_user(email: str = "member@example.com"):
    return get_user_model().objects.create_user(email=email, password="test-password-1")


def create_camp_year(year: int = 2026) -> CampYear:
    return CampYear.objects.create(year=year)


def create_tax_tier(
    camp_year: CampYear,
    name: str = "Standard",
    minimum_amount_cents: int = 10000,
    start_offset_days: int = -1,
    expiration_offset_days: int = 1,
    display_order: int = 0,
) -> TaxTier:
    now = timezone.now()
    return TaxTier.objects.create(
        camp_year=camp_year,
        name=name,
        minimum_amount_cents=minimum_amount_cents,
        start_date=now + timedelta(days=start_offset_days),
        expiration_date=now + timedelta(days=expiration_offset_days),
        display_order=display_order,
    )


def create_tax_add_on(
    camp_year: CampYear,
    name: str = "Hoodie",
    amount_cents: int = 2500,
    start_offset_days: int = -1,
    expiration_offset_days: int = 1,
    display_order: int = 0,
) -> TaxAddOn:
    now = timezone.now()
    return TaxAddOn.objects.create(
        camp_year=camp_year,
        name=name,
        amount_cents=amount_cents,
        start_date=now + timedelta(days=start_offset_days),
        expiration_date=now + timedelta(days=expiration_offset_days),
        display_order=display_order,
    )


def test_tax_tiers_are_available_only_inside_window() -> None:
    camp_year = create_camp_year()
    available = create_tax_tier(camp_year, name="Available")
    create_tax_tier(camp_year, name="Future", start_offset_days=1, expiration_offset_days=2)
    create_tax_tier(camp_year, name="Expired", start_offset_days=-2, expiration_offset_days=-1)

    assert list(available_tax_tiers(camp_year)) == [available]


def test_multiple_available_tax_tiers_are_sorted() -> None:
    camp_year = create_camp_year()
    second = create_tax_tier(camp_year, name="Second", minimum_amount_cents=20000, display_order=2)
    first = create_tax_tier(camp_year, name="First", minimum_amount_cents=10000, display_order=1)
    also_first = create_tax_tier(
        camp_year,
        name="Also First",
        minimum_amount_cents=15000,
        display_order=1,
    )

    assert list(available_tax_tiers(camp_year)) == [first, also_first, second]


def test_tax_add_ons_are_available_only_inside_window() -> None:
    camp_year = create_camp_year()
    available = create_tax_add_on(camp_year, name="Available")
    create_tax_add_on(camp_year, name="Future", start_offset_days=1, expiration_offset_days=2)
    create_tax_add_on(camp_year, name="Expired", start_offset_days=-2, expiration_offset_days=-1)

    assert list(available_tax_add_ons(camp_year)) == [available]


def test_reduced_minimum_override_changes_only_matching_user_and_year() -> None:
    user = create_user()
    other_user = create_user(email="other@example.com")
    camp_year = create_camp_year()
    other_year = create_camp_year(year=2027)
    tier = create_tax_tier(camp_year, minimum_amount_cents=10000)
    other_year_tier = create_tax_tier(other_year, minimum_amount_cents=10000)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.REDUCED_MINIMUM,
        reduced_minimum_amount_cents=5000,
    )

    assert effective_minimum_cents(user, camp_year, tier) == 5000
    assert effective_minimum_cents(other_user, camp_year, tier) == 10000
    assert effective_minimum_cents(user, other_year, other_year_tier) == 10000


def test_tax_waived_override_marks_tax_waived_for_matching_user_and_year() -> None:
    user = create_user()
    other_user = create_user(email="other@example.com")
    camp_year = create_camp_year()
    other_year = create_camp_year(year=2027)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )

    assert is_tax_waived(user, camp_year) is True
    assert is_tax_waived(other_user, camp_year) is False
    assert is_tax_waived(user, other_year) is False


def test_tax_override_validation_requires_consistent_amount() -> None:
    user = create_user()
    camp_year = create_camp_year()
    reduced = TaxOverride(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.REDUCED_MINIMUM,
    )
    waived = TaxOverride(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
        reduced_minimum_amount_cents=5000,
    )

    with pytest.raises(ValidationError):
        reduced.full_clean()
    with pytest.raises(ValidationError):
        waived.full_clean()


def test_tax_override_is_unique_per_user_and_year() -> None:
    user = create_user()
    camp_year = create_camp_year()
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )

    with pytest.raises(IntegrityError):
        TaxOverride.objects.create(
            user=user,
            camp_year=camp_year,
            override_type=TaxOverride.OverrideType.WAIVED,
        )


def test_tax_selection_form_accepts_amount_above_minimum_and_add_ons() -> None:
    user = create_user()
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year, minimum_amount_cents=10000)
    add_on = create_tax_add_on(camp_year, amount_cents=2500)
    form = TaxSelectionForm(
        {
            "tax_tier": str(tier.id),
            "tax_amount_dollars": "125.00",
            "add_ons": [str(add_on.id)],
        },
        user=user,
        camp_year=camp_year,
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["tax_amount_cents"] == 12500
    assert form.cleaned_data["effective_minimum_cents"] == 10000
    assert form.cleaned_data["add_on_amount_cents"] == 2500
    assert form.cleaned_data["total_amount_cents"] == 15000


def test_tax_selection_form_accepts_non_step_amount_above_minimum() -> None:
    user = create_user()
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year, minimum_amount_cents=10000)
    form = TaxSelectionForm(
        {"tax_tier": str(tier.id), "tax_amount_dollars": "127.43", "add_ons": []},
        user=user,
        camp_year=camp_year,
    )

    assert form.is_valid(), form.errors
    assert form.fields["tax_amount_dollars"].widget.attrs["step"] == "5.00"
    assert form.cleaned_data["tax_amount_cents"] == 12743
    assert form.cleaned_data["total_amount_cents"] == 12743


def test_tax_selection_form_rejects_amount_below_minimum() -> None:
    user = create_user()
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year, minimum_amount_cents=10000)
    form = TaxSelectionForm(
        {"tax_tier": str(tier.id), "tax_amount_dollars": "99.99", "add_ons": []},
        user=user,
        camp_year=camp_year,
    )

    assert not form.is_valid()
    assert "Enter at least $100.00." in form.errors["tax_amount_dollars"]


def test_tax_selection_form_honors_reduced_minimum() -> None:
    user = create_user()
    camp_year = create_camp_year()
    create_tax_tier(camp_year, minimum_amount_cents=10000)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.REDUCED_MINIMUM,
        reduced_minimum_amount_cents=5000,
    )
    valid_form = TaxSelectionForm(
        {"tax_tier": "override", "tax_amount_dollars": "75.00", "add_ons": []},
        user=user,
        camp_year=camp_year,
    )
    invalid_form = TaxSelectionForm(
        {"tax_tier": "override", "tax_amount_dollars": "49.99", "add_ons": []},
        user=user,
        camp_year=camp_year,
    )

    assert valid_form.is_valid(), valid_form.errors
    assert valid_form.cleaned_data["effective_minimum_cents"] == 5000
    assert valid_form.cleaned_data["tax_tier_name_snapshot"] == "Reduced Minimum"
    assert not invalid_form.is_valid()
    assert "Enter at least $50.00." in invalid_form.errors["tax_amount_dollars"]


def test_tax_selection_form_allows_waived_taxes_with_add_ons() -> None:
    user = create_user()
    camp_year = create_camp_year()
    add_on = create_tax_add_on(camp_year, amount_cents=2500)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    form = TaxSelectionForm(
        {"tax_tier": "waived", "tax_amount_dollars": "0.00", "add_ons": [str(add_on.id)]},
        user=user,
        camp_year=camp_year,
    )

    assert form.is_valid(), form.errors
    assert form.cleaned_data["tax_amount_cents"] == 0
    assert form.cleaned_data["effective_minimum_cents"] == 0
    assert form.cleaned_data["add_on_amount_cents"] == 2500
    assert form.cleaned_data["total_amount_cents"] == 2500
    assert form.cleaned_data["tax_tier_name_snapshot"] == "Waived Taxes"


def test_tax_selection_form_rejects_zero_total_waived_checkout() -> None:
    user = create_user()
    camp_year = create_camp_year()
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    form = TaxSelectionForm(
        {"tax_tier": "waived", "tax_amount_dollars": "0.00", "add_ons": []},
        user=user,
        camp_year=camp_year,
    )

    assert not form.is_valid()
    assert "No payment is needed unless you select an add-on." in form.non_field_errors()


def test_unavailable_add_on_cannot_be_selected() -> None:
    user = create_user()
    camp_year = create_camp_year()
    tier = create_tax_tier(camp_year)
    expired_add_on = create_tax_add_on(
        camp_year,
        start_offset_days=-2,
        expiration_offset_days=-1,
    )
    form = TaxSelectionForm(
        {
            "tax_tier": str(tier.id),
            "tax_amount_dollars": "100.00",
            "add_ons": [str(expired_add_on.id)],
        },
        user=user,
        camp_year=camp_year,
    )

    assert not form.is_valid()
    assert "add_ons" in form.errors
