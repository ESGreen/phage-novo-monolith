from __future__ import annotations

import html

import bleach
import markdown
from django.utils.safestring import SafeString, mark_safe

ALLOWED_TAGS = [
    "a",
    "p",
    "br",
    "strong",
    "em",
    "b",
    "ul",
    "ol",
    "li",
    "blockquote",
    "code",
    "pre",
    "hr",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "img",
    "table",
    "tr",
    "th",
    "td",
]


def _is_safe_media_or_https_image(value: str) -> bool:
    return value.startswith("/media/") or value.startswith("https://")


def _allowed_attribute(tag: str, name: str, value: str) -> bool:
    if tag == "a" and name in {"href", "title", "rel", "target"}:
        return True
    if tag == "img" and name in {"alt", "title"}:
        return True
    if tag == "img" and name == "src":
        return _is_safe_media_or_https_image(value)
    if tag in {"th", "td"} and name == "align":
        return True
    return False


CLEANER = bleach.Cleaner(
    tags=ALLOWED_TAGS,
    attributes=_allowed_attribute,
    protocols=["http", "https", "mailto"],
    strip=True,
)


def render_markdown(markdown_text: str) -> SafeString:
    escaped_text = html.escape(markdown_text or "")
    rendered_html = markdown.markdown(
        escaped_text,
        extensions=["fenced_code", "tables"],
        output_format="html",
    )
    return mark_safe(CLEANER.clean(rendered_html))
