from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from camp.models import CampYear, TaxOverride
from camp.services import get_current_camp_year
from content.models import ContentPage, MediaItem
from payments.models import Payment

pytestmark = pytest.mark.django_db


def create_user():
    return get_user_model().objects.create_user(
        email="member@example.com",
        password="test-password-1",
    )


def create_profile_photo(user) -> MediaItem:
    return MediaItem.objects.create(
        title="Profile photo",
        original_filename="profile.png",
        file_path=f"profile-{user.id}.png",
        content_type="image/png",
        size_bytes=1,
    )


def complete_profile(user) -> None:
    user.profile.photo = create_profile_photo(user)
    user.profile.bio_markdown = "Ready for camp."
    user.profile.save(update_fields=["photo", "bio_markdown", "updated_at"])


def mark_taxes_paid(user, camp_year: CampYear) -> None:
    Payment.objects.create(
        user=user,
        camp_year=camp_year,
        status=Payment.Status.PAID,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        paid_at=timezone.now(),
    )


def test_current_camp_year_is_max_configured_year() -> None:
    CampYear.objects.create(year=2025)
    current = CampYear.objects.create(year=2026)

    assert get_current_camp_year() == current


def test_dashboard_requires_login(client) -> None:
    CampYear.objects.create(year=2026)

    response = client.get("/dashboard/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/dashboard/"


def test_year_dashboard_requires_login(client) -> None:
    CampYear.objects.create(year=2026)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/2026/dashboard/"


def test_dashboard_without_camp_year_shows_empty_state(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/dashboard/")

    assert response.status_code == 200
    assert b"No camp year is configured." in response.content


def test_dashboard_redirects_to_current_year(client) -> None:
    user = create_user()
    client.force_login(user)
    CampYear.objects.create(year=2025)
    CampYear.objects.create(year=2026)

    response = client.get("/dashboard/")

    assert response.status_code == 302
    assert response["Location"] == "/2026/dashboard/"


def test_short_year_url_redirects_to_canonical_dashboard(client) -> None:
    user = create_user()
    client.force_login(user)
    CampYear.objects.create(year=2026)

    response = client.get("/2026/")

    assert response.status_code == 302
    assert response["Location"] == "/2026/dashboard/"


def test_year_dashboard_loads_for_existing_year(client) -> None:
    user = create_user()
    client.force_login(user)
    CampYear.objects.create(year=2026)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"2026 Dashboard" in response.content
    assert b"Registration Checklist" in response.content
    assert b"Profile" in response.content
    assert b"Add a picture and bio to your profile" in response.content
    assert b"Complete Profile" in response.content
    assert b"Please pay your camp taxes" in response.content
    assert b"Locked" in response.content
    assert b"Pay Taxes" not in response.content
    assert b"Quick Links" not in response.content


def test_old_year_dashboard_remains_accessible(client) -> None:
    user = create_user()
    client.force_login(user)
    CampYear.objects.create(year=2025)
    CampYear.objects.create(year=2026)

    response = client.get("/2025/dashboard/")

    assert response.status_code == 200
    assert b"2025 Dashboard" in response.content


def test_unknown_year_dashboard_returns_404(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 404


def test_dashboard_renders_pre_and_post_content_safely(client) -> None:
    user = create_user()
    client.force_login(user)
    pre_page = ContentPage.objects.create(
        title="Pre",
        slug="dashboard-pre",
        body_markdown="# Before Camp\n\n<script>alert(1)</script>",
    )
    post_page = ContentPage.objects.create(
        title="Post",
        slug="dashboard-post",
        body_markdown="## After Camp\n\nRemember cleanup.",
    )
    CampYear.objects.create(
        year=2026,
        dashboard_pre_page=pre_page,
        dashboard_post_page=post_page,
    )

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"<h1>Before Camp</h1>" in response.content
    assert b"<h2>After Camp</h2>" in response.content
    assert b"Remember cleanup." in response.content
    assert b"<script" not in response.content


def test_dashboard_requires_profile_photo_and_bio_before_taxes_are_current(client) -> None:
    user = create_user()
    user.profile.photo = create_profile_photo(user)
    user.profile.save(update_fields=["photo", "updated_at"])
    client.force_login(user)
    CampYear.objects.create(year=2026)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"Add a picture and bio to your profile" in response.content
    assert b"Complete Profile" in response.content
    assert b"Pay Taxes" not in response.content


def test_dashboard_makes_taxes_current_after_profile_is_complete(client) -> None:
    user = create_user()
    complete_profile(user)
    client.force_login(user)
    CampYear.objects.create(year=2026)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"Check your picture / bio." in response.content
    assert b"Edit Profile" in response.content
    assert b"Please pay your camp taxes" in response.content
    assert b"Pay Taxes" in response.content
    assert b'href="/2026/taxes/"' in response.content


def test_dashboard_shows_fully_registered_message_after_paid_taxes(client) -> None:
    user = create_user()
    complete_profile(user)
    camp_year = CampYear.objects.create(year=2026)
    mark_taxes_paid(user, camp_year)
    client.force_login(user)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"Taxes - Paid" in response.content
    assert b"Pay Taxes" not in response.content
    assert b"You are fully registered. Now all that's left is to get packing." in response.content


def test_dashboard_treats_waived_taxes_as_paid(client) -> None:
    user = create_user()
    complete_profile(user)
    camp_year = CampYear.objects.create(year=2026)
    TaxOverride.objects.create(
        user=user,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    client.force_login(user)

    response = client.get("/2026/dashboard/")

    assert response.status_code == 200
    assert b"Taxes - Paid" in response.content
    assert b"You are fully registered. Now all that's left is to get packing." in response.content
