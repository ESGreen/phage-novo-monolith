from __future__ import annotations

from django import template

register = template.Library()


@register.filter
def cents(amount_cents: int | None) -> str:
    if amount_cents is None:
        return ""
    return f"${amount_cents / 100:.2f}"
