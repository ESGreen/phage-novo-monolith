from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError

from content.models import Menu, MenuItem

pytestmark = pytest.mark.django_db


def create_user():
    return get_user_model().objects.create_user(
        email="member@example.com",
        password="test-password-1",
    )


def test_menu_items_sort_by_display_order_then_label() -> None:
    menu = Menu.objects.create(menu_name="camp-info")
    MenuItem.objects.create(menu=menu, label="Packing List", url="/pages/packing/", display_order=2)
    MenuItem.objects.create(menu=menu, label="Camp Map", url="/pages/map/", display_order=1)
    MenuItem.objects.create(menu=menu, label="Arrival", url="/pages/arrival/", display_order=1)

    assert list(menu.items.values_list("label", flat=True)) == [
        "Arrival",
        "Camp Map",
        "Packing List",
    ]


def test_root_menu_cannot_be_deleted() -> None:
    root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)

    with pytest.raises(ValidationError):
        root_menu.delete()

    assert Menu.objects.filter(pk=root_menu.pk).exists()


def test_menu_page_requires_login(client) -> None:
    Menu.objects.create(menu_name="camp-info")

    response = client.get("/menu/camp-info/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/menu/camp-info/"


def test_missing_menu_returns_404_for_member(client) -> None:
    user = create_user()
    client.force_login(user)

    response = client.get("/menu/missing/")

    assert response.status_code == 404


def test_non_root_menu_page_renders_sorted_items_and_links(client) -> None:
    user = create_user()
    client.force_login(user)
    menu = Menu.objects.create(menu_name="camp-info")
    MenuItem.objects.create(menu=menu, label="External", url="https://example.com", display_order=3)
    MenuItem.objects.create(menu=menu, label="Packing List", url="/pages/packing/", display_order=2)
    MenuItem.objects.create(menu=menu, label="More Camp", url="/menu/more-camp/", display_order=4)
    MenuItem.objects.create(menu=menu, label="Arrival", url="/pages/arrival/", display_order=1)

    response = client.get("/menu/camp-info/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Camp Info" in body
    assert body.index("Arrival") < body.index("Packing List")
    assert body.index("Packing List") < body.index("External")
    assert body.index("External") < body.index("More Camp")
    assert 'href="/pages/arrival/"' in body
    assert 'href="https://example.com"' in body
    assert 'href="/menu/more-camp/"' in body


def test_root_menu_is_used_for_member_navigation(client) -> None:
    user = create_user()
    client.force_login(user)
    root_menu, _ = Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
    MenuItem.objects.create(
        menu=root_menu,
        label="Camp Info",
        url="/menu/camp-info/",
        display_order=1,
    )
    MenuItem.objects.create(menu=root_menu, label="Profile", url="/profile/", display_order=2)

    response = client.get("/profile/")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'href="/menu/camp-info/"' in body
    assert "Camp Info" in body
    assert 'href="/profile/"' in body
