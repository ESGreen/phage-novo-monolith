from __future__ import annotations

from .models import CampYear


def get_current_camp_year() -> CampYear | None:
    return CampYear.objects.order_by("-year").first()
