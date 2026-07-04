from __future__ import annotations

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from django.utils import timezone


class Payment(models.Model):
    class Status(models.TextChoices):
        CREATED = "created", "Created"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"
        REQUIRES_REVIEW = "requires_review", "Requires review"

    class StripeMode(models.TextChoices):
        TEST = "test", "Test"
        LIVE = "live", "Live"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    camp_year = models.ForeignKey(
        "camp.CampYear", on_delete=models.PROTECT, related_name="payments"
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.CREATED)
    stripe_mode = models.CharField(max_length=10, choices=StripeMode.choices)
    tax_amount_cents = models.PositiveIntegerField()
    add_on_amount_cents = models.PositiveIntegerField(default=0)
    total_amount_cents = models.PositiveIntegerField()
    tax_tier_name_snapshot = models.CharField(max_length=120)
    tax_tier_minimum_cents_snapshot = models.PositiveIntegerField()
    stripe_checkout_session_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )
    stripe_payment_intent_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    checkout_created_at = models.DateTimeField(null=True, blank=True)
    checkout_expires_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["user", "camp_year"]),
            models.Index(fields=["status"]),
            models.Index(fields=["stripe_mode", "status"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "camp_year"],
                condition=Q(status="paid"),
                name="unique_paid_payment_user_year",
            ),
            models.CheckConstraint(
                condition=Q(total_amount_cents=F("tax_amount_cents") + F("add_on_amount_cents")),
                name="payment_total_matches_parts",
            ),
            models.CheckConstraint(
                condition=~Q(status="paid") | Q(paid_at__isnull=False),
                name="payment_paid_requires_paid_at",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.user} {self.camp_year} {self.status}"

    def blocks_new_checkout(self) -> bool:
        return (
            self.status == self.Status.CREATED
            and self.checkout_expires_at is not None
            and self.checkout_expires_at > timezone.now()
        )


class PaymentAddOn(models.Model):
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name="add_ons")
    tax_add_on = models.ForeignKey(
        "camp.TaxAddOn", on_delete=models.SET_NULL, null=True, blank=True
    )
    name_snapshot = models.CharField(max_length=120)
    amount_cents_snapshot = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self) -> str:
        return self.name_snapshot


class PaymentLog(models.Model):
    class Level(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        ERROR = "error", "Error"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="logs",
    )
    level = models.CharField(max_length=20, choices=Level.choices)
    event_type = models.CharField(max_length=120)
    stripe_mode = models.CharField(max_length=10, blank=True)
    stripe_event_id = models.CharField(max_length=255, blank=True)
    message = models.TextField(blank=True)
    redacted_payload = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.level}: {self.event_type}"
