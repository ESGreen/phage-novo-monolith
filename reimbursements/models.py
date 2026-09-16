from __future__ import annotations

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q, Sum
from django.db.models.functions import Lower

US_STATE_AND_TERRITORY_CODES = {
    "AA",
    "AE",
    "AK",
    "AL",
    "AP",
    "AR",
    "AS",
    "AZ",
    "CA",
    "CO",
    "CT",
    "DC",
    "DE",
    "FL",
    "FM",
    "GA",
    "GU",
    "HI",
    "IA",
    "ID",
    "IL",
    "IN",
    "KS",
    "KY",
    "LA",
    "MA",
    "MD",
    "ME",
    "MH",
    "MI",
    "MN",
    "MO",
    "MP",
    "MS",
    "MT",
    "NC",
    "ND",
    "NE",
    "NH",
    "NJ",
    "NM",
    "NV",
    "NY",
    "OH",
    "OK",
    "OR",
    "PA",
    "PR",
    "PW",
    "RI",
    "SC",
    "SD",
    "TN",
    "TX",
    "UT",
    "VA",
    "VI",
    "VT",
    "WA",
    "WI",
    "WV",
    "WY",
}
ZIP_CODE_RE = re.compile(r"^\d{5}(?:-\d{4})?$")
MAX_EXPENSE_AMOUNT_CENTS = 100_000_000


class Reimbursement(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SUBMITTED = "submitted", "Submitted"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    reimbursement_number = models.CharField(max_length=20, unique=True)
    camp_year = models.ForeignKey(
        "camp.CampYear",
        on_delete=models.CASCADE,
        related_name="reimbursements",
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reimbursements",
    )
    split_from = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        related_name="split_reimbursements",
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    requester_notes = models.TextField(blank=True, max_length=10_000)
    payer_notes = models.TextField(blank=True, max_length=10_000)
    created_at = models.DateTimeField(auto_now_add=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    paid_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="paid_reimbursements",
        null=True,
        blank=True,
    )
    rejected_at = models.DateTimeField(null=True, blank=True)
    rejected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="rejected_reimbursements",
        null=True,
        blank=True,
    )

    class Meta:
        indexes = [
            models.Index(fields=["camp_year", "status"]),
            models.Index(fields=["requester", "camp_year", "created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(status="paid", paid_at__isnull=False, paid_by__isnull=False)
                    | (~Q(status="paid") & Q(paid_at__isnull=True, paid_by__isnull=True))
                ),
                name="reimbursement_paid_metadata_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    Q(status="rejected", rejected_at__isnull=False, rejected_by__isnull=False)
                    | (
                        ~Q(status="rejected")
                        & Q(rejected_at__isnull=True, rejected_by__isnull=True)
                    )
                ),
                name="reimbursement_rejected_metadata_consistent",
            ),
        ]

    def __str__(self) -> str:
        return self.reimbursement_number

    @property
    def total_amount_cents(self) -> int:
        return self.expenses.aggregate(total=Sum("amount_cents"))["total"] or 0

    def clean(self) -> None:
        super().clean()
        if self.split_from_id:
            if self.pk and self.split_from_id == self.pk:
                raise ValidationError({"split_from": "A reimbursement cannot split from itself."})
            if self.split_from.requester_id != self.requester_id:
                raise ValidationError(
                    {"split_from": "Split reimbursements must have the same requester."}
                )
            if self.split_from.camp_year_id != self.camp_year_id:
                raise ValidationError(
                    {"split_from": "Split reimbursements must use the same camp year."}
                )


class ReimbursementExpenseCategory(models.Model):
    camp_year = models.ForeignKey(
        "camp.CampYear",
        on_delete=models.CASCADE,
        related_name="reimbursement_expense_categories",
    )
    name = models.CharField(max_length=120)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                "camp_year",
                name="unique_reimbursement_category_name_ci_year",
            )
        ]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        super().clean()
        self.name = self.name.strip()
        if not self.name:
            raise ValidationError({"name": "Category name is required."})

    def save(self, *args: object, **kwargs: object) -> None:
        self.name = self.name.strip()
        super().save(*args, **kwargs)


class ReimbursementExpense(models.Model):
    reimbursement = models.ForeignKey(
        Reimbursement,
        on_delete=models.CASCADE,
        related_name="expenses",
    )
    category = models.ForeignKey(
        ReimbursementExpenseCategory,
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    description = models.TextField(max_length=2_000)
    amount_cents = models.PositiveBigIntegerField()

    class Meta:
        ordering = ["id"]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount_cents__gt=0),
                name="reimbursement_expense_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(amount_cents__lte=MAX_EXPENSE_AMOUNT_CENTS),
                name="reimbursement_expense_amount_maximum",
            ),
        ]

    def __str__(self) -> str:
        return self.description[:80]

    def clean(self) -> None:
        super().clean()
        self.description = self.description.strip()
        if not self.description:
            raise ValidationError({"description": "Expense description is required."})
        if self.category_id and self.reimbursement_id:
            if self.category.camp_year_id != self.reimbursement.camp_year_id:
                raise ValidationError({"category": "Category must belong to the camp year."})


class ReimbursementPayoutDetails(models.Model):
    class Method(models.TextChoices):
        PAPER_CHECK = "paper_check", "Paper check"
        ZELLE = "zelle", "Zelle"

    method = models.CharField(max_length=20, choices=Method.choices)
    zelle_email = models.EmailField(blank=True)
    check_payee_name = models.CharField(max_length=200, blank=True)
    check_address_line_1 = models.CharField(max_length=200, blank=True)
    check_address_line_2 = models.CharField(max_length=200, blank=True)
    check_city = models.CharField(max_length=200, blank=True)
    check_state = models.CharField(max_length=2, blank=True)
    check_postal_code = models.CharField(max_length=10, blank=True)

    class Meta:
        abstract = True

    def normalize_payout_fields(self) -> None:
        for field in (
            "zelle_email",
            "check_payee_name",
            "check_address_line_1",
            "check_address_line_2",
            "check_city",
            "check_state",
            "check_postal_code",
        ):
            setattr(self, field, getattr(self, field).strip())
        self.zelle_email = self.zelle_email.lower()
        self.check_state = self.check_state.upper()
        if self.method == self.Method.ZELLE:
            self.check_payee_name = ""
            self.check_address_line_1 = ""
            self.check_address_line_2 = ""
            self.check_city = ""
            self.check_state = ""
            self.check_postal_code = ""
        elif self.method == self.Method.PAPER_CHECK:
            self.zelle_email = ""

    def clean(self) -> None:
        super().clean()
        self.normalize_payout_fields()
        if self.method == self.Method.ZELLE:
            if not self.zelle_email:
                raise ValidationError({"zelle_email": "Zelle email is required."})
            return
        if self.method == self.Method.PAPER_CHECK:
            errors = {}
            for field in (
                "check_payee_name",
                "check_address_line_1",
                "check_city",
                "check_state",
                "check_postal_code",
            ):
                if not getattr(self, field):
                    errors[field] = "This field is required for paper checks."
            if self.check_state and self.check_state not in US_STATE_AND_TERRITORY_CODES:
                errors["check_state"] = "Enter a two-letter US state or territory code."
            if self.check_postal_code and not ZIP_CODE_RE.fullmatch(self.check_postal_code):
                errors["check_postal_code"] = "Enter a ZIP code such as 12345 or 12345-6789."
            if errors:
                raise ValidationError(errors)

    def clean_fields(self, exclude=None) -> None:
        self.normalize_payout_fields()
        super().clean_fields(exclude=exclude)

    def payout_summary(self) -> str:
        if self.method == self.Method.ZELLE:
            return f"Zelle to {self.zelle_email}"
        return f"Paper check to {self.check_payee_name}"


class ReimbursementPayoutProfile(ReimbursementPayoutDetails):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reimbursement_payout_profile",
    )


class ReimbursementPayoutSnapshot(ReimbursementPayoutDetails):
    reimbursement = models.OneToOneField(
        Reimbursement,
        on_delete=models.CASCADE,
        related_name="payout_snapshot",
    )


class ReimbursementReceipt(models.Model):
    class ReceiptType(models.TextChoices):
        IMAGE = "image", "Image"
        PDF = "pdf", "PDF"
        EXPLANATION = "explanation", "Explanation"

    reimbursement = models.ForeignKey(
        Reimbursement,
        on_delete=models.CASCADE,
        related_name="receipts",
    )
    receipt_type = models.CharField(max_length=20, choices=ReceiptType.choices)
    original_filename = models.CharField(max_length=255, blank=True)
    file_path = models.CharField(max_length=500, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size_bytes = models.PositiveBigIntegerField(null=True, blank=True)
    explanation = models.TextField(blank=True, max_length=10_000)

    def __str__(self) -> str:
        return self.original_filename or self.explanation[:80]

    def clean(self) -> None:
        super().clean()
        self.explanation = self.explanation.strip()
        if self.receipt_type == self.ReceiptType.EXPLANATION:
            if not self.explanation:
                raise ValidationError({"explanation": "Explanation is required."})
            if any((self.original_filename, self.file_path, self.content_type, self.size_bytes)):
                raise ValidationError("Explanation receipts cannot contain file metadata.")
            return
        if not all((self.original_filename, self.file_path, self.content_type, self.size_bytes)):
            raise ValidationError("File receipts require complete file metadata.")
