from __future__ import annotations

from django.http import HttpRequest, HttpResponse
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
