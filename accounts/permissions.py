from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from django.conf import settings
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest, HttpResponseBase


def member_required(view_func: Callable[..., HttpResponseBase]) -> Callable[..., HttpResponseBase]:
    @wraps(view_func)
    def wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if request.user.is_authenticated and request.user.is_active:
            return view_func(request, *args, **kwargs)

        return redirect_to_login(request.get_full_path(), settings.LOGIN_URL, REDIRECT_FIELD_NAME)

    return wrapped_view


def admin_required(view_func: Callable[..., HttpResponseBase]) -> Callable[..., HttpResponseBase]:
    @wraps(view_func)
    def wrapped_view(request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponseBase:
        if not request.user.is_authenticated or not request.user.is_active:
            return redirect_to_login(
                request.get_full_path(),
                settings.LOGIN_URL,
                REDIRECT_FIELD_NAME,
            )

        if not request.user.is_admin:
            raise PermissionDenied

        return view_func(request, *args, **kwargs)

    return wrapped_view
