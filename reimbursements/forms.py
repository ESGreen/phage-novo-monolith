from __future__ import annotations

from decimal import Decimal

from django import forms
from django.db.models.functions import Lower

from .models import (
    Reimbursement,
    ReimbursementExpenseCategory,
    ReimbursementPayoutProfile,
)
from .services import dollars_to_cents


class ReimbursementPayoutProfileForm(forms.ModelForm):
    class Meta:
        model = ReimbursementPayoutProfile
        fields = [
            "method",
            "zelle_email",
            "check_payee_name",
            "check_address_line_1",
            "check_address_line_2",
            "check_city",
            "check_state",
            "check_postal_code",
        ]

    def __init__(self, *args: object, user, **kwargs: object) -> None:
        self.user = user
        initial = kwargs.pop("initial", {})
        if kwargs.get("instance") is None or kwargs["instance"].pk is None:
            initial.setdefault("method", ReimbursementPayoutProfile.Method.PAPER_CHECK)
        kwargs["initial"] = initial
        super().__init__(*args, **kwargs)
        self.fields["method"].empty_label = None
        self.fields["method"].choices = ReimbursementPayoutProfile.Method.choices
        self.fields["method"].widget.attrs["data-payout-method"] = "true"

    def save(self, commit: bool = True):
        profile = super().save(commit=False)
        profile.user = self.user
        profile.normalize_payout_fields()
        if commit:
            profile.save()
        return profile


class ReimbursementExpenseCreateForm(forms.Form):
    category = forms.ModelChoiceField(queryset=ReimbursementExpenseCategory.objects.none())
    description = forms.CharField(
        max_length=2_000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    amount_dollars = forms.DecimalField(
        label="Amount",
        min_value=Decimal("0.01"),
        max_value=Decimal("1000000.00"),
        max_digits=9,
        decimal_places=2,
    )

    def __init__(self, *args: object, reimbursement: Reimbursement, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["category"].queryset = ReimbursementExpenseCategory.objects.filter(
            camp_year=reimbursement.camp_year
        ).order_by(Lower("name"), "id")

    @property
    def amount_cents(self) -> int:
        return dollars_to_cents(self.cleaned_data["amount_dollars"])


class ReimbursementReceiptUploadForm(forms.Form):
    file = forms.FileField()
    explanation = forms.CharField(
        label="Notes / description",
        max_length=10_000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean_explanation(self) -> str:
        return self.cleaned_data["explanation"].strip()


class ReimbursementReceiptExplanationForm(forms.Form):
    explanation = forms.CharField(
        label="Explanation",
        max_length=10_000,
        widget=forms.Textarea(attrs={"rows": 2}),
    )

    def clean_explanation(self) -> str:
        explanation = self.cleaned_data["explanation"].strip()
        if not explanation:
            raise forms.ValidationError("Explanation is required.")
        return explanation


class ReimbursementRequesterNotesForm(forms.Form):
    requester_notes = forms.CharField(
        max_length=10_000,
        required=False,
        widget=forms.Textarea(attrs={"rows": 4}),
    )


class ReimbursementDeleteForm(forms.Form):
    confirmation = forms.CharField(
        label="Confirmation",
        help_text='Type "delete" to permanently delete this reimbursement.',
    )


class ReimbursementExpenseCategoryCreateForm(forms.Form):
    name = forms.CharField(max_length=120)

    def __init__(self, *args: object, camp_year, **kwargs: object) -> None:
        self.camp_year = camp_year
        super().__init__(*args, **kwargs)

    def clean_name(self) -> str:
        name = self.cleaned_data["name"].strip()
        if ReimbursementExpenseCategory.objects.filter(
            camp_year=self.camp_year,
            name__iexact=name,
        ).exists():
            raise forms.ValidationError("This reimbursement category already exists.")
        return name

    def save(self) -> ReimbursementExpenseCategory:
        return ReimbursementExpenseCategory.objects.create(
            camp_year=self.camp_year,
            name=self.cleaned_data["name"],
        )


class ReimbursementPayerNotesForm(forms.Form):
    payer_notes = forms.CharField(max_length=10_000, required=False, widget=forms.Textarea)


class ReimbursementPaymentForm(ReimbursementPayerNotesForm):
    pass


class ReimbursementSplitForm(forms.Form):
    expenses = forms.ModelMultipleChoiceField(
        queryset=None,
        widget=forms.CheckboxSelectMultiple,
    )
    rationale = forms.CharField(
        max_length=10_000,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args: object, reimbursement: Reimbursement, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        self.fields["expenses"].queryset = reimbursement.expenses.all()
