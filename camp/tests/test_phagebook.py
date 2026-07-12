from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone

from camp.models import CampYear, TaxOverride
from content.models import MediaItem
from payments.models import Payment
from surveys.models import Survey, SurveyResponse

pytestmark = pytest.mark.django_db


def create_user(
    email: str = "member@example.com",
    first_name: str = "Ada",
    last_name: str = "Lovelace",
):
    return get_user_model().objects.create_user(
        email=email,
        password="test-password-1",
        first_name=first_name,
        last_name=last_name,
    )


def create_profile_photo(user) -> MediaItem:
    return MediaItem.objects.create(
        title="Profile photo",
        original_filename="profile.png",
        file_path=f"profile-{user.id}.png",
        content_type="image/png",
        size_bytes=1,
    )


def complete_profile(user, bio: str = "Ready for camp.") -> None:
    user.profile.photo = create_profile_photo(user)
    user.profile.bio_markdown = bio
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


def test_phagebook_requires_login(client) -> None:
    CampYear.objects.create(year=2026)

    response = client.get("/2026/phagebook/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/2026/phagebook/"


def test_current_phagebook_redirects_to_current_year(client) -> None:
    user = create_user()
    client.force_login(user)
    CampYear.objects.create(year=2025)
    CampYear.objects.create(year=2026)

    response = client.get("/phagebook/")

    assert response.status_code == 302
    assert response["Location"] == "/2026/phagebook/"


def test_unknown_phagebook_year_returns_404(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/2026/phagebook/")

    assert response.status_code == 404


def test_any_member_can_view_but_only_fully_registered_members_appear(client) -> None:
    viewer = create_user(email="viewer@example.com", first_name="View", last_name="Only")
    registered = create_user(email="registered@example.com", first_name="Grace", last_name="Hopper")
    incomplete = create_user(
        email="incomplete@example.com",
        first_name="Missing",
        last_name="Taxes",
    )
    camp_year = CampYear.objects.create(year=2026)
    complete_profile(registered, bio="Registered bio.")
    complete_profile(incomplete, bio="Incomplete bio.")
    mark_taxes_paid(registered, camp_year)
    client.force_login(viewer)

    response = client.get("/2026/phagebook/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "2026 Phagebook" in body
    assert "Grace Hopper" in body
    assert "registered@example.com" in body
    assert "Registered bio." in body
    assert "viewer@example.com" not in body
    assert "incomplete@example.com" not in body


def test_phagebook_includes_tax_waived_members(client) -> None:
    viewer = create_user(email="viewer@example.com", first_name="View", last_name="Only")
    waived = create_user(email="waived@example.com", first_name="Tax", last_name="Waived")
    camp_year = CampYear.objects.create(year=2026)
    complete_profile(waived, bio="Waived bio.")
    TaxOverride.objects.create(
        user=waived,
        camp_year=camp_year,
        override_type=TaxOverride.OverrideType.WAIVED,
    )
    client.force_login(viewer)

    response = client.get("/2026/phagebook/")

    assert response.status_code == 200
    assert b"Tax Waived" in response.content
    assert b"waived@example.com" in response.content


@pytest.mark.parametrize(
    ("missing_field", "email"),
    [
        ("first_name", "missing-first@example.com"),
        ("last_name", "missing-last@example.com"),
        ("photo", "missing-photo@example.com"),
        ("bio", "missing-bio@example.com"),
    ],
)
def test_phagebook_excludes_incomplete_profiles(client, missing_field: str, email: str) -> None:
    viewer = create_user(email="viewer@example.com", first_name="View", last_name="Only")
    member = create_user(email=email, first_name="Complete", last_name="Member")
    camp_year = CampYear.objects.create(year=2026)
    complete_profile(member)
    if missing_field == "first_name":
        member.first_name = ""
        member.save(update_fields=["first_name", "updated_at"])
    elif missing_field == "last_name":
        member.last_name = ""
        member.save(update_fields=["last_name", "updated_at"])
    elif missing_field == "photo":
        member.profile.photo = None
        member.profile.save(update_fields=["photo", "updated_at"])
    elif missing_field == "bio":
        member.profile.bio_markdown = ""
        member.profile.save(update_fields=["bio_markdown", "updated_at"])
    mark_taxes_paid(member, camp_year)
    client.force_login(viewer)

    response = client.get("/2026/phagebook/")

    assert response.status_code == 200
    assert email.encode() not in response.content
    assert b"No one is fully registered for 2026 yet." in response.content


def test_phagebook_requires_configured_camp_survey_response(client) -> None:
    viewer = create_user(email="viewer@example.com", first_name="View", last_name="Only")
    incomplete = create_user(email="incomplete@example.com", first_name="No", last_name="Survey")
    complete = create_user(email="complete@example.com", first_name="Has", last_name="Survey")
    survey = Survey.objects.create(name="Camp Survey", slug="camp-survey")
    camp_year = CampYear.objects.create(year=2026, camp_survey=survey)
    complete_profile(incomplete)
    complete_profile(complete)
    mark_taxes_paid(incomplete, camp_year)
    mark_taxes_paid(complete, camp_year)
    SurveyResponse.objects.create(user=complete, survey=survey)
    client.force_login(viewer)

    response = client.get("/2026/phagebook/")

    assert response.status_code == 200
    assert b"complete@example.com" in response.content
    assert b"incomplete@example.com" not in response.content


def test_phagebook_renders_bio_markdown_safely(client) -> None:
    viewer = create_user(email="viewer@example.com", first_name="View", last_name="Only")
    member = create_user(email="safe@example.com", first_name="Safe", last_name="Bio")
    camp_year = CampYear.objects.create(year=2026)
    complete_profile(member, bio="# Bio\n\n<script>alert(1)</script>")
    mark_taxes_paid(member, camp_year)
    client.force_login(viewer)

    response = client.get("/2026/phagebook/")

    assert response.status_code == 200
    assert b"<h1>Bio</h1>" in response.content
    assert b"&lt;script&gt;" in response.content
    assert b"<script" not in response.content
