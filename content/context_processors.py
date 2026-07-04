from __future__ import annotations

from django.http import HttpRequest

from .models import Menu, MenuItem


def root_menu(request: HttpRequest) -> dict[str, object]:
    if not request.user.is_authenticated:
        return {"root_menu_items": []}

    return {
        "root_menu_items": MenuItem.objects.filter(menu__menu_name=Menu.ROOT_MENU_NAME).order_by(
            "display_order",
            "label",
        )
    }
