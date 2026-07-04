from __future__ import annotations

from datetime import timedelta
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.utils import timezone
from PIL import Image

from camp.models import CampYear
from content.models import ContentPage, MediaItem, Menu, MenuItem
from core.models import SiteSettings
from payments.models import Payment

pytestmark = pytest.mark.django_db

ADMIN_SECTIONS = [
    "/admin/",
    "/admin/users/",
    "/admin/camp/",
    "/admin/payments/",
    "/admin/stripe/",
    "/admin/pages/",
    "/admin/menus/",
    "/admin/media/",
]


def create_user(email: str = "member@example.com", is_admin: bool = False):
    return get_user_model().objects.create_user(
        email=email,
        password="test-password-1",
        is_admin=is_admin,
    )


def png_upload(name: str = "image.png") -> SimpleUploadedFile:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format="PNG")
    return SimpleUploadedFile(name, output.getvalue(), content_type="image/png")


@pytest.mark.parametrize("url", ADMIN_SECTIONS)
def test_admin_sections_require_login(client, url: str) -> None:
    response = client.get(url)

    assert response.status_code == 302
    assert response["Location"] == f"/login/?next={url}"


@pytest.mark.parametrize("url", ADMIN_SECTIONS)
def test_admin_sections_reject_non_admin_members(client, url: str) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get(url)

    assert response.status_code == 403


@pytest.mark.parametrize("url", ADMIN_SECTIONS)
def test_admin_sections_load_for_admin(client, url: str) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.get(url)

    assert response.status_code == 200


def test_admin_can_create_user(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/users/",
        {
            "email": "NewMember@example.com",
            "first_name": "New",
            "last_name": "Member",
            "is_active": "on",
            "password": "test-password-1",
            "bio_markdown": "Bio",
        },
    )

    assert response.status_code == 302
    user = get_user_model().objects.get(email="newmember@example.com")
    assert user.first_name == "New"
    assert user.profile.bio_markdown == "Bio"


def test_admin_can_create_camp_year(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/camp/",
        {"action": "camp_year", "year": "2026"},
    )

    assert response.status_code == 302
    camp_year = CampYear.objects.get(year=2026)
    assert camp_year.created_by == admin
    assert camp_year.updated_by == admin


def test_admin_can_create_and_delete_content_page(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    create_response = client.post(
        "/admin/pages/",
        {
            "action": "create",
            "title": "Arrival",
            "slug": "arrival",
            "body_markdown": "# Arrival",
        },
    )
    page = ContentPage.objects.get(slug="arrival")
    delete_response = client.post(
        "/admin/pages/",
        {"action": "delete", "page_id": str(page.id)},
    )

    assert create_response.status_code == 302
    assert delete_response.status_code == 302
    assert not ContentPage.objects.filter(slug="arrival").exists()


def test_admin_can_create_menu_and_menu_item(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    create_menu_response = client.post(
        "/admin/menus/",
        {"action": "create_menu", "menu_name": "camp-info"},
    )
    menu = Menu.objects.get(menu_name="camp-info")
    create_item_response = client.post(
        "/admin/menus/",
        {
            "action": "create_item",
            "menu": str(menu.id),
            "label": "Arrival",
            "url": "/pages/arrival/",
            "display_order": "1",
        },
    )

    assert create_menu_response.status_code == 302
    assert create_item_response.status_code == 302
    assert MenuItem.objects.get(menu=menu).label == "Arrival"


def test_admin_cannot_delete_root_menu(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)
    root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)

    response = client.post(
        "/admin/menus/",
        {"action": "delete_menu", "menu_id": str(root_menu.id)},
        follow=True,
    )

    assert response.status_code == 200
    assert Menu.objects.filter(pk=root_menu.pk).exists()
    assert b"The root menu cannot be deleted." in response.content


def test_admin_can_upload_and_delete_media(client, settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    upload_response = client.post(
        "/admin/media/",
        {"action": "upload", "title": "Map", "image": png_upload()},
    )
    media_item = MediaItem.objects.get(title="Map")
    delete_response = client.post(
        "/admin/media/",
        {"action": "delete", "media_id": str(media_item.id)},
    )

    assert upload_response.status_code == 302
    assert delete_response.status_code == 302
    assert not MediaItem.objects.filter(title="Map").exists()


def test_admin_can_switch_stripe_mode(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    client.force_login(admin)

    response = client.post(
        "/admin/stripe/",
        {"action": "switch_mode", "stripe_mode": "live"},
    )

    assert response.status_code == 302
    assert SiteSettings.load().stripe_mode == SiteSettings.StripeMode.LIVE


def test_admin_test_payment_cleanup_leaves_live_payments(client) -> None:
    admin = create_user(email="admin@example.com", is_admin=True)
    member = create_user(email="member@example.com")
    camp_year = CampYear.objects.create(year=2026)
    client.force_login(admin)
    Payment.objects.create(
        user=member,
        camp_year=camp_year,
        status=Payment.Status.CREATED,
        stripe_mode=Payment.StripeMode.TEST,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )
    live_payment = Payment.objects.create(
        user=member,
        camp_year=camp_year,
        status=Payment.Status.CREATED,
        stripe_mode=Payment.StripeMode.LIVE,
        tax_amount_cents=10000,
        add_on_amount_cents=0,
        total_amount_cents=10000,
        tax_tier_name_snapshot="Standard",
        tax_tier_minimum_cents_snapshot=10000,
        checkout_expires_at=timezone.now() + timedelta(hours=1),
    )

    response = client.post(
        "/admin/stripe/",
        {"action": "delete_test_payments", "confirm": "delete"},
    )

    assert response.status_code == 302
    assert list(Payment.objects.values_list("id", flat=True)) == [live_payment.id]
