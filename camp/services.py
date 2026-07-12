from __future__ import annotations

from payments.checkout import get_paid_payment
from surveys.models import SurveyResponse

from .models import CampYear
from .taxes import is_tax_waived


def get_current_camp_year() -> CampYear | None:
    return CampYear.objects.order_by("-year").first()


def is_profile_complete(user: object) -> bool:
    profile = user.profile
    return bool(
        user.first_name.strip()
        and user.last_name.strip()
        and profile.photo_id
        and profile.bio_markdown.strip()
    )


def is_camp_survey_complete(user: object, camp_year: CampYear) -> bool:
    if not camp_year.camp_survey_id:
        return True
    return SurveyResponse.objects.filter(survey=camp_year.camp_survey, user=user).exists()


def are_taxes_complete(user: object, camp_year: CampYear) -> bool:
    return get_paid_payment(user, camp_year) is not None or is_tax_waived(user, camp_year)


def is_registration_complete(user: object, camp_year: CampYear) -> bool:
    return (
        is_profile_complete(user)
        and is_camp_survey_complete(user, camp_year)
        and are_taxes_complete(user, camp_year)
    )
