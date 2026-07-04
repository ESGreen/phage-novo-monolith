from __future__ import annotations

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class CampYear(models.Model):
    year = models.PositiveSmallIntegerField(unique=True)
    dashboard_pre_page = models.ForeignKey(
        "content.ContentPage",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="camp_years_as_dashboard_pre_page",
    )
    dashboard_post_page = models.ForeignKey(
        "content.ContentPage",
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name="camp_years_as_dashboard_post_page",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_camp_years",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_camp_years",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-year"]

    def __str__(self) -> str:
        return str(self.year)

    def get_absolute_url(self) -> str:
        return reverse("camp:dashboard", kwargs={"year": self.year})


class TaxTier(models.Model):
    camp_year = models.ForeignKey(CampYear, on_delete=models.CASCADE, related_name="tax_tiers")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    minimum_amount_cents = models.PositiveIntegerField()
    start_date = models.DateTimeField()
    expiration_date = models.DateTimeField()
    display_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_tax_tiers",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_tax_tiers",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "minimum_amount_cents", "name"]
        indexes = [
            models.Index(fields=["camp_year", "start_date", "expiration_date"]),
            models.Index(fields=["camp_year", "display_order"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expiration_date__gt=models.F("start_date")),
                name="tax_tier_expiration_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(minimum_amount_cents__gt=0),
                name="tax_tier_minimum_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class TaxAddOn(models.Model):
    camp_year = models.ForeignKey(CampYear, on_delete=models.CASCADE, related_name="tax_add_ons")
    name = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    amount_cents = models.PositiveIntegerField()
    start_date = models.DateTimeField()
    expiration_date = models.DateTimeField()
    display_order = models.PositiveIntegerField(default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_tax_add_ons",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_tax_add_ons",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "amount_cents", "name"]
        indexes = [
            models.Index(fields=["camp_year", "start_date", "expiration_date"]),
            models.Index(fields=["camp_year", "display_order"]),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(expiration_date__gt=models.F("start_date")),
                name="tax_add_on_expiration_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(amount_cents__gt=0),
                name="tax_add_on_amount_positive",
            ),
        ]

    def __str__(self) -> str:
        return self.name


class TaxOverride(models.Model):
    class OverrideType(models.TextChoices):
        REDUCED_MINIMUM = "reduced_minimum", "Reduced minimum"
        WAIVED = "waived", "Waived"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    camp_year = models.ForeignKey(CampYear, on_delete=models.CASCADE, related_name="tax_overrides")
    override_type = models.CharField(max_length=30, choices=OverrideType.choices)
    reduced_minimum_amount_cents = models.PositiveIntegerField(blank=True, null=True)
    note = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="created_tax_overrides",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="updated_tax_overrides",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "camp_year"],
                name="unique_tax_override_user_year",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        override_type="reduced_minimum",
                        reduced_minimum_amount_cents__isnull=False,
                    )
                    | models.Q(override_type="waived", reduced_minimum_amount_cents__isnull=True)
                ),
                name="tax_override_type_amount_consistent",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(reduced_minimum_amount_cents__isnull=True)
                    | models.Q(reduced_minimum_amount_cents__gt=0)
                ),
                name="tax_override_reduced_minimum_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.camp_year} {self.override_type}"

    def clean(self) -> None:
        if (
            self.override_type == self.OverrideType.REDUCED_MINIMUM
            and self.reduced_minimum_amount_cents is None
        ):
            raise ValidationError(
                {"reduced_minimum_amount_cents": "Reduced minimum overrides require an amount."}
            )
        if (
            self.override_type == self.OverrideType.WAIVED
            and self.reduced_minimum_amount_cents is not None
        ):
            raise ValidationError(
                {"reduced_minimum_amount_cents": "Waived overrides cannot have an amount."}
            )
