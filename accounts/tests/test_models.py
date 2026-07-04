import pytest
from django.contrib.auth import authenticate, get_user_model

from accounts.models import MemberProfile

pytestmark = pytest.mark.django_db


def test_user_uses_lowercase_email_as_login_identity() -> None:
    user = get_user_model().objects.create_user(
        email="Member@Example.COM",
        password="test-password",
        first_name="Test",
        last_name="Member",
    )

    assert user.email == "member@example.com"
    assert user.get_full_name() == "Test Member"
    assert user.get_short_name() == "Test"
    assert not hasattr(user, "username")


def test_authenticate_matches_email_case_insensitively() -> None:
    get_user_model().objects.create_user(email="member@example.com", password="test-password")

    user = authenticate(email="MEMBER@example.com", password="test-password")

    assert user is not None
    assert user.email == "member@example.com"


def test_inactive_user_cannot_authenticate() -> None:
    get_user_model().objects.create_user(
        email="inactive@example.com",
        password="test-password",
        is_active=False,
    )

    user = authenticate(email="inactive@example.com", password="test-password")

    assert user is None


def test_profile_is_created_with_user() -> None:
    user = get_user_model().objects.create_user(
        email="profile@example.com",
        password="test-password",
    )

    assert isinstance(user.profile, MemberProfile)
    assert user.profile.bio_markdown == ""


def test_create_superuser_sets_admin_flag_without_staff_fields() -> None:
    user = get_user_model().objects.create_superuser(
        email="admin@example.com",
        password="test-password",
    )

    assert user.is_active is True
    assert user.is_admin is True
    assert not hasattr(user, "is_staff")
    assert not hasattr(user, "is_superuser")
