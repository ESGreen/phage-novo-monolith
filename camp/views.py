from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from accounts.permissions import member_required
from content.markdown import render_markdown
from payments.checkout import (
    CheckoutBlocked,
    create_tax_checkout,
    get_paid_payment,
    get_unexpired_created_payment,
)
from payments.models import Payment
from surveys.models import SurveyResponse

from .forms import TaxSelectionForm
from .models import CampYear
from .services import get_current_camp_year
from .taxes import get_tax_override, is_tax_waived


@member_required
def dashboard_redirect(request: HttpRequest) -> HttpResponse:
    camp_year = get_current_camp_year()
    if camp_year is None:
        return render(request, "camp/no_camp_year.html")
    return redirect("camp:dashboard", year=camp_year.year)


@member_required
def year_redirect(request: HttpRequest, year: int) -> HttpResponseRedirect:
    get_object_or_404(CampYear, year=year)
    return redirect("camp:dashboard", year=year)


@member_required
def dashboard(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(
        CampYear.objects.select_related(
            "camp_survey",
            "dashboard_pre_page",
            "dashboard_post_page",
        ),
        year=year,
    )
    pre_html = ""
    post_html = ""
    if camp_year.dashboard_pre_page:
        pre_html = render_markdown(camp_year.dashboard_pre_page.body_markdown)
    if camp_year.dashboard_post_page:
        post_html = render_markdown(camp_year.dashboard_post_page.body_markdown)
    dashboard_items = _dashboard_items(request.user, camp_year)

    return render(
        request,
        "camp/dashboard.html",
        {
            "camp_year": camp_year,
            "dashboard_items": dashboard_items,
            "is_fully_registered": all(item["complete"] for item in dashboard_items),
            "pre_html": pre_html,
            "post_html": post_html,
        },
    )


def _dashboard_items(user: object, camp_year: CampYear) -> list[dict[str, object]]:
    profile = user.profile
    profile_complete = bool(profile.photo_id and profile.bio_markdown.strip())
    taxes_complete = get_paid_payment(user, camp_year) is not None or is_tax_waived(user, camp_year)
    survey_complete = _camp_survey_complete(user, camp_year)
    items = [
        {
            "key": "profile",
            "title": "Profile",
            "complete": profile_complete,
            "complete_description": (
                "Check your picture / bio. You can always update them if you don't like "
                "the picture."
            ),
            "incomplete_description": "Add a picture and bio to your profile",
            "current_action_label": "Complete Profile",
            "complete_action_label": "Edit Profile",
            "action_url": reverse("accounts:profile"),
        },
    ]
    if camp_year.camp_survey_id:
        survey = camp_year.camp_survey
        survey_available = survey.is_active or survey_complete
        items.append(
            {
                "key": "camp_survey",
                "title": "Camp Survey",
                "complete": survey_complete,
                "complete_description": "Camp survey complete.",
                "incomplete_description": (
                    "Complete the camp survey before paying taxes."
                    if survey_available
                    else "The camp survey is not currently available. Contact an admin."
                ),
                "current_action_label": "Complete Survey" if survey_available else "",
                "complete_action_label": "Edit Survey" if survey.is_active else "",
                "action_url": survey.get_absolute_url() if survey_available else "",
            }
        )
    items.append(
        {
            "key": "taxes",
            "title": "Taxes",
            "complete": taxes_complete,
            "complete_description": "Taxes - Paid",
            "incomplete_description": "Please pay your camp taxes",
            "current_action_label": "Pay Taxes",
            "complete_action_label": "",
            "action_url": reverse("camp:taxes", kwargs={"year": camp_year.year}),
        },
    )
    current_assigned = False
    for item in items:
        if item["complete"]:
            item["state"] = "complete"
            item["symbol"] = "[x]"
            item["status_label"] = "Complete"
            item["description"] = item["complete_description"]
            item["action_label"] = item["complete_action_label"]
        elif not current_assigned:
            item["state"] = "current"
            item["symbol"] = "!"
            item["status_label"] = "Current Step"
            item["description"] = item["incomplete_description"]
            item["action_label"] = item["current_action_label"]
            current_assigned = True
        else:
            item["state"] = "locked"
            item["symbol"] = "[ ]"
            item["status_label"] = "Locked"
            item["description"] = item["incomplete_description"]
            item["action_label"] = ""
    return items


def _camp_survey_complete(user: object, camp_year: CampYear) -> bool:
    if not camp_year.camp_survey_id:
        return True
    return SurveyResponse.objects.filter(survey=camp_year.camp_survey, user=user).exists()


def _tax_prerequisites_complete(user: object, camp_year: CampYear) -> bool:
    profile = user.profile
    return bool(profile.photo_id and profile.bio_markdown.strip()) and _camp_survey_complete(
        user,
        camp_year,
    )


@member_required
def taxes(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear.objects.select_related("camp_survey"), year=year)
    if not _tax_prerequisites_complete(request.user, camp_year):
        messages.error(request, "Complete your registration checklist before paying taxes.")
        return redirect("camp:dashboard", year=camp_year.year)
    tax_override = get_tax_override(request.user, camp_year)
    paid_payment = get_paid_payment(request.user, camp_year)
    blocking_payment = get_unexpired_created_payment(request.user, camp_year)
    form = None

    if paid_payment is None and blocking_payment is None:
        if request.method == "POST":
            form = TaxSelectionForm(request.POST, user=request.user, camp_year=camp_year)
            if form.is_valid():
                try:
                    checkout_result = create_tax_checkout(request.user, camp_year, form)
                except CheckoutBlocked as error:
                    messages.error(request, str(error))
                    return redirect("camp:taxes", year=camp_year.year)
                return redirect(checkout_result.checkout_url)
        else:
            form = TaxSelectionForm(user=request.user, camp_year=camp_year)
        if not form.tax_options:
            form = None

    return render(
        request,
        "camp/taxes.html",
        {
            "camp_year": camp_year,
            "tax_override": tax_override,
            "paid_payment": paid_payment,
            "blocking_payment": blocking_payment,
            "available_add_ons": form.fields["add_ons"].queryset if form is not None else [],
            "form": form,
        },
    )


@member_required
def taxes_return(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear, year=year)
    session_id = request.GET.get("session_id", "")
    payment = None
    if session_id:
        payment = Payment.objects.filter(
            user=request.user,
            camp_year=camp_year,
            stripe_checkout_session_id=session_id,
        ).first()
    return render(
        request,
        "camp/taxes_return.html",
        {"camp_year": camp_year, "payment": payment, "session_id": session_id},
    )
