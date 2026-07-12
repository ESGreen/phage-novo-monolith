from __future__ import annotations

from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError

from content.models import Menu
from core.models import SiteSettings
from payments.models import Payment

pytestmark = pytest.mark.django_db


def test_initial_data_exists() -> None:
    assert SiteSettings.objects.get(pk=SiteSettings.SINGLETON_PK).stripe_mode == "test"
    root_menu = Menu.objects.get(menu_name=Menu.ROOT_MENU_NAME)
    assert list(root_menu.items.values_list("label", "url", "display_order")) == [
        ("Dashboard", "/dashboard/", 1),
        ("Phage Book", "/phagebook/", 2),
        ("Profile", "/profile/", 3),
    ]


def test_create_admin_creates_active_admin_user_with_profile() -> None:
    output = StringIO()

    call_command(
        "create_admin",
        email="Admin@Example.COM",
        first_name="Admin",
        last_name="User",
        password="test-password-1",
        stdout=output,
    )

    user = get_user_model().objects.get(email="admin@example.com")
    assert user.is_active is True
    assert user.is_admin is True
    assert user.profile.bio_markdown == ""
    assert "Created admin user: admin@example.com" in output.getvalue()


def test_create_admin_refuses_duplicate_email() -> None:
    get_user_model().objects.create_user(email="admin@example.com", password="test-password-1")

    with pytest.raises(CommandError):
        call_command(
            "create_admin",
            email="ADMIN@example.com",
            first_name="Admin",
            last_name="User",
            password="test-password-1",
        )


def test_check_config_validates_required_sections(tmp_path) -> None:
    bad_config = tmp_path / "bad.toml"
    bad_config.write_text(
        "[site]\n"
        'base_url = "http://example.com"\n'
        'secret_key = "secret"\n'
        "debug = true\n"
        'allowed_hosts = ["example.com"]\n'
        'timezone = "UTC"\n'
    )

    with pytest.raises(CommandError):
        call_command("check_config", config=str(bad_config))


def test_check_config_does_not_print_secrets() -> None:
    output = StringIO()

    call_command("check_config", config="tests/fixtures/thephage.test.toml", stdout=output)

    command_output = output.getvalue()
    assert "Config OK" in command_output
    assert "test-secret-key-not-for-production" not in command_output
    assert "sk_test_dummy" not in command_output
    assert "whsec_test_dummy" not in command_output


def test_check_stripe_validates_config_without_printing_secrets_or_creating_payments() -> None:
    output = StringIO()

    call_command("check_stripe", stdout=output)

    command_output = output.getvalue()
    assert "Stripe config OK" in command_output
    assert "Current Stripe mode: test" in command_output
    assert "sk_test_dummy" not in command_output
    assert "whsec_test_dummy" not in command_output
    assert Payment.objects.count() == 0
