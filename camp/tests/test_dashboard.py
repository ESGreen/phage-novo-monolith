from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from camp.models import CampYear
from camp.services import get_current_camp_year
from content.models import ContentPage

pytestmark = pytest.mark.django_db


def create_user():
    return get_user_model().objects.create_user(
        email="member@example.com",
        password="test-password-1",
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
    assert b"Checklist" in response.content
    assert b"Profile" in response.content
    assert b"Complete" in response.content
    assert b'href="/2026/taxes/"' in response.content


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
