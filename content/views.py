from __future__ import annotations

from mimetypes import guess_type
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, render

from accounts.permissions import member_required

from .markdown import render_markdown
from .models import ContentPage, Menu


@member_required
def page_detail(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(ContentPage, slug=slug)
    return render(
        request,
        "content/page_detail.html",
        {"page": page, "body_html": render_markdown(page.body_markdown)},
    )


@member_required
def menu_detail(request: HttpRequest, menu_name: str) -> HttpResponse:
    menu = get_object_or_404(Menu, menu_name=menu_name)
    return render(
        request,
        "content/menu_detail.html",
        {"menu": menu, "items": menu.items.all()},
    )


@member_required
def derived_media(request: HttpRequest, file_path: str) -> FileResponse:
    derived_root = Path(settings.DERIVED_MEDIA_ROOT).resolve()
    requested_path = (derived_root / file_path).resolve()
    if not requested_path.is_relative_to(derived_root) or not requested_path.is_file():
        raise Http404("Derived media not found")

    content_type, _ = guess_type(requested_path.name)
    return FileResponse(
        requested_path.open("rb"),
        content_type=content_type or "application/octet-stream",
    )
