from __future__ import annotations

from django import forms

from .models import CampYear, TaxAddOn, TaxTier
from .taxes import (
    available_tax_add_ons,
    available_tax_tiers,
    decimal_dollars_to_cents,
    effective_minimum_cents,
)


class TaxSelectionForm(forms.Form):
    tax_tier = forms.ModelChoiceField(queryset=TaxTier.objects.none(), widget=forms.RadioSelect)
    tax_amount_dollars = forms.DecimalField(
        label="Tax amount",
        min_value=0,
        max_digits=8,
        decimal_places=2,
    )
    add_ons = forms.ModelMultipleChoiceField(
        queryset=TaxAddOn.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    def __init__(
        self,
        *args: object,
        user: object,
        camp_year: CampYear,
        now=None,
        **kwargs: object,
    ):
        self.user = user
        self.camp_year = camp_year
        self.now = now
        super().__init__(*args, **kwargs)
        self.fields["tax_tier"].queryset = available_tax_tiers(camp_year, now=now)
        self.fields["add_ons"].queryset = available_tax_add_ons(camp_year, now=now)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        tax_tier = cleaned_data.get("tax_tier")
        tax_amount_dollars = cleaned_data.get("tax_amount_dollars")
        add_ons = cleaned_data.get("add_ons") or []

        if tax_tier is None or tax_amount_dollars is None:
            return cleaned_data

        tax_amount_cents = decimal_dollars_to_cents(tax_amount_dollars)
        minimum_cents = effective_minimum_cents(self.user, self.camp_year, tax_tier)
        if tax_amount_cents < minimum_cents:
            self.add_error(
                "tax_amount_dollars",
                f"Enter at least ${minimum_cents / 100:.2f}.",
            )

        add_on_amount_cents = sum(add_on.amount_cents for add_on in add_ons)
        cleaned_data["tax_amount_cents"] = tax_amount_cents
        cleaned_data["effective_minimum_cents"] = minimum_cents
        cleaned_data["add_on_amount_cents"] = add_on_amount_cents
        cleaned_data["total_amount_cents"] = tax_amount_cents + add_on_amount_cents
        return cleaned_data
