from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from thephage.config import ConfigError, load_config


class Command(BaseCommand):
    help = "Validate TOML configuration without printing secrets."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--config", default=None, help="Optional TOML config path to validate.")

    def handle(self, *args, **options) -> None:
        try:
            config = load_config(options["config"]) if options["config"] else settings.CONFIG
        except ConfigError as error:
            raise CommandError(str(error)) from error

        if not config.site.debug:
            if not config.site.allowed_hosts:
                raise CommandError("Production config requires allowed hosts.")
            if "change-me" in config.site.secret_key.lower():
                raise CommandError("Production config requires a real secret key.")

        self.stdout.write(self.style.SUCCESS(f"Config OK: {config.path}"))
        self.stdout.write("Sections OK: site, database, paths, stripe, backups")
