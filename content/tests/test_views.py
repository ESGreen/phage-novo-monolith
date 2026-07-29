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


def test_derived_media_requires_login(client, settings, tmp_path) -> None:
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    image_path = settings.DERIVED_MEDIA_ROOT / "profile_photos" / "1-768.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"jpeg")

    response = client.get("/derived-media/profile_photos/1-768.jpg")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/derived-media/profile_photos/1-768.jpg"


def test_member_can_view_derived_media(client, settings, tmp_path) -> None:
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    image_path = settings.DERIVED_MEDIA_ROOT / "profile_photos" / "1-768.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"jpeg")
    client.force_login(create_user())

    response = client.get("/derived-media/profile_photos/1-768.jpg")

    assert response.status_code == 200
    assert response["Content-Type"] == "image/jpeg"
    assert b"".join(response.streaming_content) == b"jpeg"


def test_derived_media_blocks_path_traversal(client, settings, tmp_path) -> None:
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    settings.DERIVED_MEDIA_ROOT.mkdir()
    (tmp_path / "secret.jpg").write_bytes(b"secret")
    client.force_login(create_user())

    response = client.get("/derived-media/../secret.jpg")

    assert response.status_code == 404
