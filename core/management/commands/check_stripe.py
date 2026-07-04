from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core.models import SiteSettings


class Command(BaseCommand):
    help = "Validate Stripe configuration without calling Stripe or printing secrets."

    def handle(self, *args, **options) -> None:
        stripe_config = settings.CONFIG.stripe
        required_values = [
            stripe_config.test_secret_key,
            stripe_config.test_publishable_key,
            stripe_config.test_webhook_secret,
            stripe_config.live_secret_key,
            stripe_config.live_publishable_key,
            stripe_config.live_webhook_secret,
        ]
        if any(not value for value in required_values):
            raise CommandError("Stripe config is incomplete.")

        site_settings = SiteSettings.load()
        if site_settings.stripe_mode not in SiteSettings.StripeMode.values:
            raise CommandError("Stored Stripe mode is invalid.")

        self.stdout.write(self.style.SUCCESS("Stripe config OK."))
        self.stdout.write(f"Current Stripe mode: {site_settings.stripe_mode}")
