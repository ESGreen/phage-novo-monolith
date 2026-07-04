from __future__ import annotations

from django.contrib.auth.password_validation import validate_password
from django.core.management.base import BaseCommand, CommandError

from accounts.models import User


class Command(BaseCommand):
    help = "Create the first active product admin user."

    def add_arguments(self, parser) -> None:
        parser.add_argument("--email", required=True)
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--password", required=True)

    def handle(self, *args, **options) -> None:
        email = User.objects.normalize_email(options["email"])
        if User.objects.filter(email=email).exists():
            raise CommandError(f"User already exists: {email}")

        validate_password(options["password"])
        user = User.objects.create_superuser(
            email=email,
            password=options["password"],
            first_name=options["first_name"],
            last_name=options["last_name"],
            is_active=True,
            is_admin=True,
        )
        self.stdout.write(self.style.SUCCESS(f"Created admin user: {user.email}"))
