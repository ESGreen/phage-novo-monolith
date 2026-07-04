from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

from content.models import ContentPage

pytestmark = pytest.mark.django_db


def create_user():
    return get_user_model().objects.create_user(
        email="member@example.com",
        password="test-password-1",
    )


def test_content_page_requires_login(client) -> None:
    ContentPage.objects.create(title="Arrival", slug="arrival", body_markdown="Welcome")

    response = client.get("/pages/arrival/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/pages/arrival/"


def test_content_page_renders_sanitized_markdown_for_member(client) -> None:
    user = create_user()
    client.force_login(user)
    ContentPage.objects.create(
        title="Arrival",
        slug="arrival",
        body_markdown="# Welcome\n\n<script>alert(1)</script>",
    )

    response = client.get("/pages/arrival/")

    assert response.status_code == 200
    assert b"Arrival" in response.content
    assert b"<h1>Welcome</h1>" in response.content
    assert b"<script" not in response.content


def test_missing_content_page_returns_404(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/pages/missing/")

    assert response.status_code == 404
