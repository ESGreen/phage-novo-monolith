from __future__ import annotations

from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from content.media import create_media_item

pytestmark = pytest.mark.django_db

PASSWORD = "test-password-1"


def create_user(email: str = "member@example.com", password: str = PASSWORD, **kwargs: object):
    return get_user_model().objects.create_user(email=email, password=password, **kwargs)


def png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    return output.getvalue()


def png_upload(name: str = "avatar.png") -> SimpleUploadedFile:
    return SimpleUploadedFile(name, png_bytes(), content_type="image/png")


def test_login_page_renders(client) -> None:
    response = client.get("/login/")

    assert response.status_code == 200
    assert b"name=\"email\"" in response.content


def test_logged_in_user_visiting_login_redirects_to_dashboard(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/login/")

    assert response.status_code == 302
    assert response["Location"] == "/dashboard/"


def test_login_with_email_redirects_to_dashboard(client) -> None:
    create_user(email="member@example.com")

    response = client.post(
        "/login/",
        {"email": "MEMBER@example.com", "password": PASSWORD},
    )

    assert response.status_code == 302
    assert response["Location"] == "/dashboard/"


def test_login_respects_safe_next_url(client) -> None:
    create_user(email="member@example.com")

    response = client.post(
        "/login/?next=/profile/",
        {"email": "member@example.com", "password": PASSWORD, "next": "/profile/"},
    )

    assert response.status_code == 302
    assert response["Location"] == "/profile/"


def test_login_rejects_bad_credentials_with_generic_error(client) -> None:
    create_user(email="member@example.com")

    response = client.post(
        "/login/",
        {"email": "member@example.com", "password": "wrong-password"},
    )

    assert response.status_code == 200
    assert b"Please enter a correct email and password." in response.content


def test_inactive_user_cannot_log_in(client) -> None:
    create_user(email="inactive@example.com", is_active=False)

    response = client.post(
        "/login/",
        {"email": "inactive@example.com", "password": PASSWORD},
    )

    assert response.status_code == 200
    assert b"Please enter a correct email and password." in response.content


def test_profile_requires_login(client) -> None:
    response = client.get("/profile/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/profile/"


def test_profile_page_renders_for_member(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/profile/")

    assert response.status_code == 200
    assert b"Photo" in response.content
    assert b"No photo present" in response.content
    assert b"Load Photo" in response.content
    assert b"Basic Bio" in response.content
    assert b"Email" in response.content
    assert b"Change Password" in response.content


def test_logout_redirects_to_public_site(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.post("/logout/")

    assert response.status_code == 302
    assert response["Location"] == "/public/"
    assert client.get("/profile/").status_code == 302


def test_member_can_update_name_and_bio(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "bio",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "bio_markdown": "# Bio\n\nWrites notes.",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.profile.bio_markdown == "# Bio\n\nWrites notes."


def test_email_change_requires_confirmation(client) -> None:
    user = create_user(email="member@example.com")
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "email",
            "new_email": "new@example.com",
            "confirm_new_email": "other@example.com",
        },
    )

    assert response.status_code == 200
    assert b"Email addresses do not match." in response.content
    user.refresh_from_db()
    assert user.email == "member@example.com"


def test_confirmed_email_change_updates_email_lowercase(client) -> None:
    user = create_user(email="member@example.com")
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "email",
            "new_email": "NEW@example.COM",
            "confirm_new_email": "new@example.com",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.email == "new@example.com"


def test_email_change_rejects_duplicate_email(client) -> None:
    user = create_user(email="member@example.com")
    create_user(email="taken@example.com")
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "email",
            "new_email": "taken@example.com",
            "confirm_new_email": "taken@example.com",
        },
    )

    assert response.status_code == 200
    assert b"Another account already uses this email address." in response.content
    user.refresh_from_db()
    assert user.email == "member@example.com"


def test_member_can_replace_profile_photo(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    user = create_user()
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "photo",
            "photo": png_upload(),
        },
    )

    assert response.status_code == 302
    user.profile.refresh_from_db()
    media_item = user.profile.photo
    assert media_item is not None
    assert media_item.file_path.startswith(f"{media_item.id}-avatar")
    assert "/" not in media_item.file_path
    assert default_storage.exists(media_item.file_path)
    response = client.get("/profile/")
    assert b"Replace Photo" in response.content


def test_profile_save_without_photo_keeps_existing_photo(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    user = create_user()
    media_item = create_media_item(png_upload("existing.png"), title="Existing photo")
    user.profile.photo = media_item
    user.profile.save(update_fields=["photo", "updated_at"])
    original_photo_id = media_item.id
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "bio",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "bio_markdown": "Updated bio",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.profile.photo_id == original_photo_id
    assert user.profile.bio_markdown == "Updated bio"


def test_profile_bio_requires_name_and_bio(client) -> None:
    user = create_user(first_name="Ada", last_name="Lovelace")
    user.profile.bio_markdown = "Existing bio"
    user.profile.save(update_fields=["bio_markdown", "updated_at"])
    client.force_login(user)

    response = client.post(
        "/profile/",
        {"action": "bio", "first_name": "", "last_name": "", "bio_markdown": ""},
    )

    assert response.status_code == 200
    assert response.content.count(b"This field is required.") == 3
    user.refresh_from_db()
    user.profile.refresh_from_db()
    assert user.first_name == "Ada"
    assert user.last_name == "Lovelace"
    assert user.profile.bio_markdown == "Existing bio"


def test_member_can_change_password_and_stay_logged_in(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "password",
            "old_password": PASSWORD,
            "new_password1": "better-password-1",
            "new_password2": "better-password-1",
        },
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("better-password-1")
    assert client.get("/profile/").status_code == 200


def test_password_change_rejects_wrong_old_password(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "password",
            "old_password": "wrong-password",
            "new_password1": "better-password-1",
            "new_password2": "better-password-1",
        },
    )

    assert response.status_code == 200
    assert b"Your old password was entered incorrectly." in response.content
    user.refresh_from_db()
    assert user.check_password(PASSWORD)


def test_password_change_rejects_weak_password(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.post(
        "/profile/",
        {
            "action": "password",
            "old_password": PASSWORD,
            "new_password1": "aaaaaaaaaa",
            "new_password2": "aaaaaaaaaa",
        },
    )

    assert response.status_code == 200
    assert b"This password must contain at least two character classes." in response.content
    user.refresh_from_db()
    assert user.check_password(PASSWORD)
