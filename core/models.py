from __future__ import annotations

from typing import Any

from django.core.exceptions import ValidationError
from django.db import models


class SiteSettings(models.Model):
    SINGLETON_PK = 1

    class StripeMode(models.TextChoices):
        TEST = "test", "Test"
        LIVE = "live", "Live"

    stripe_mode = models.CharField(
        max_length=10,
        choices=StripeMode.choices,
        default=StripeMode.TEST,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "site settings"

    def __str__(self) -> str:
        return "Site settings"

    @classmethod
    def load(cls) -> SiteSettings:
        settings, _ = cls.objects.get_or_create(pk=cls.SINGLETON_PK)
        return settings

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.pk = self.SINGLETON_PK
        super().save(*args, **kwargs)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        raise ValidationError("Site settings cannot be deleted.")
