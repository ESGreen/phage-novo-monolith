from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django import forms

from .models import CampYear, TaxAddOn, TaxOverride
from .taxes import (
    available_tax_add_ons,
    available_tax_tiers,
    decimal_dollars_to_cents,
    get_tax_override,
)


@dataclass(frozen=True)
class TaxOption:
    key: str
    name: str
    description: str
    minimum_amount_cents: int
    kind: str


class TaxSelectionForm(forms.Form):
    tax_tier = forms.ChoiceField(widget=forms.RadioSelect)
    tax_amount_dollars = forms.DecimalField(
        label="Tax amount",
        min_value=0,
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "5.00", "data-tax-amount-input": "true"}),
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
        self.tax_options = build_tax_options(user, camp_year, now=now)
        initial = kwargs.pop("initial", {}).copy()
        if self.tax_options:
            selected_option = self.tax_options[0]
            initial.setdefault("tax_tier", selected_option.key)
            initial.setdefault(
                "tax_amount_dollars",
                cents_to_dollars(selected_option.minimum_amount_cents),
            )
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.fields["tax_tier"].choices = [
            (option.key, option.name) for option in self.tax_options
        ]
        self.fields["add_ons"].queryset = available_tax_add_ons(camp_year, now=now)
        self.fields["tax_amount_dollars"].widget.attrs["min"] = str(
            cents_to_dollars(self.selected_minimum_cents),
        )

    @property
    def selected_tax_option_key(self) -> str:
        value = self["tax_tier"].value()
        if value:
            return str(value)
        if self.tax_options:
            return self.tax_options[0].key
        return ""

    @property
    def selected_tax_option(self) -> TaxOption | None:
        return self._tax_option_by_key(self.selected_tax_option_key)

    @property
    def selected_minimum_cents(self) -> int:
        selected_option = self.selected_tax_option
        return selected_option.minimum_amount_cents if selected_option is not None else 0

    @property
    def selected_add_on_ids(self) -> set[int]:
        value = self["add_ons"].value() or []
        return {int(add_on_id) for add_on_id in value if str(add_on_id).isdigit()}

    def _tax_option_by_key(self, key: str) -> TaxOption | None:
        return next((option for option in self.tax_options if option.key == key), None)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        tax_tier_key = cleaned_data.get("tax_tier")
        tax_amount_dollars = cleaned_data.get("tax_amount_dollars")
        add_ons = cleaned_data.get("add_ons") or []

        if tax_tier_key is None or tax_amount_dollars is None:
            return cleaned_data

        tax_option = self._tax_option_by_key(str(tax_tier_key))
        if tax_option is None:
            return cleaned_data

        tax_amount_cents = decimal_dollars_to_cents(tax_amount_dollars)
        minimum_cents = tax_option.minimum_amount_cents
        if tax_amount_cents < minimum_cents:
            self.add_error(
                "tax_amount_dollars",
                f"Enter at least ${minimum_cents / 100:.2f}.",
            )

        add_on_amount_cents = sum(add_on.amount_cents for add_on in add_ons)
        total_amount_cents = tax_amount_cents + add_on_amount_cents
        if total_amount_cents <= 0:
            raise forms.ValidationError("No payment is needed unless you select an add-on.")

        cleaned_data["tax_amount_cents"] = tax_amount_cents
        cleaned_data["effective_minimum_cents"] = minimum_cents
        cleaned_data["add_on_amount_cents"] = add_on_amount_cents
        cleaned_data["total_amount_cents"] = total_amount_cents
        cleaned_data["tax_tier_name_snapshot"] = tax_option.name
        return cleaned_data


def build_tax_options(user: object, camp_year: CampYear, now=None) -> list[TaxOption]:
    tax_override = get_tax_override(user, camp_year)
    if tax_override is not None and tax_override.override_type == TaxOverride.OverrideType.WAIVED:
        return [
            TaxOption(
                key="waived",
                name="Waived Taxes",
                description=(
                    "Your camp taxes are covered for this year. You can still choose "
                    "optional add-ons."
                ),
                minimum_amount_cents=0,
                kind="waived",
            ),
        ]
    if (
        tax_override is not None
        and tax_override.override_type == TaxOverride.OverrideType.REDUCED_MINIMUM
    ):
        return [
            TaxOption(
                key="override",
                name="Reduced Minimum",
                description="Your adjusted minimum for this year.",
                minimum_amount_cents=tax_override.reduced_minimum_amount_cents or 0,
                kind="override",
            ),
        ]

    return [
        TaxOption(
            key=str(tax_tier.id),
            name=tax_tier.name,
            description=tax_tier.description,
            minimum_amount_cents=tax_tier.minimum_amount_cents,
            kind="standard",
        )
        for tax_tier in available_tax_tiers(camp_year, now=now)
    ]


def cents_to_dollars(amount_cents: int) -> Decimal:
    return (Decimal(amount_cents) / Decimal("100")).quantize(Decimal("0.01"))
