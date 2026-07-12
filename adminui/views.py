from __future__ import annotations

import csv
import io

from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min, ProtectedError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.forms import ProfileBioForm, ProfilePhotoForm
from accounts.models import User
from accounts.permissions import admin_required
from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from camp.services import get_current_camp_year
from content.models import ContentPage, MediaItem, Menu, MenuItem
from core.models import SiteSettings
from payments.models import Payment, PaymentLog
from surveys.forms import (
    SurveyAdminForm,
    SurveyChoiceCreateForm,
    SurveyChoiceForm,
    SurveyConditionForm,
    SurveyCreateForm,
    SurveyQuestionAdminForm,
    SurveyQuestionCreateForm,
    SurveyQuestionOptionsForm,
)
from surveys.models import Survey, SurveyAnswer, SurveyChoice, SurveyQuestion
from surveys.question_types import is_choice_question_type
from surveys.services import (
    load_answer_json,
    move_choice,
    move_question,
    next_choice_order,
    next_question_order,
)

from .forms import (
    AdminUserCreateForm,
    AdminUserEmailForm,
    AdminUserFlagsForm,
    CampYearCreateForm,
    CampYearDashboardSetupForm,
    ContentPageForm,
    MediaUploadAdminForm,
    MenuForm,
    MenuItemForm,
    TaxAddOnCreateForm,
    TaxOverrideCreateForm,
    TaxTierCreateForm,
)


@admin_required
def home(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "adminui/home.html",
        {
            "site_settings": SiteSettings.load(),
            "current_camp_year": get_current_camp_year(),
        },
    )


@admin_required
def users(request: HttpRequest) -> HttpResponse:
    form = AdminUserCreateForm(request.POST or None)
    create_user_status_message = ""
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User created.")
        return redirect("adminui:users")
    if request.method == "POST":
        create_user_status_message = _first_form_error_message(form)
    return render(
        request,
        "adminui/users.html",
        {
            "create_user_status_message": create_user_status_message,
            "users": User.objects.all(),
            "form": form,
        },
    )


@admin_required
@require_POST
def user_intro_email(request: HttpRequest) -> JsonResponse:
    form = AdminUserCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "message": _first_form_error_message(form),
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    first_name = form.cleaned_data["first_name"]
    last_name = form.cleaned_data["last_name"]
    email = form.cleaned_data["account_address"]
    full_name = f"{first_name} {last_name}".strip() or email
    body = render_to_string(
        "adminui/emails/new_user_intro.txt",
        {
            "email": email,
            "first_name": first_name,
            "full_name": full_name,
            "last_name": last_name,
            "login_url": request.build_absolute_uri("/login/"),
            "password": form.cleaned_data["initial_secret"],
        },
    )
    return JsonResponse({"body": body})


def _first_form_error_message(form: AdminUserCreateForm) -> str:
    for field_name, errors in form.errors.items():
        if not errors:
            continue
        if field_name == "__all__":
            return str(errors[0])
        field = form.fields.get(field_name)
        label = field.label if field is not None else field_name.replace("_", " ").title()
        return f"{label}: {errors[0]}"
    return "Fix the create user fields before continuing."


@admin_required
def user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    edited_user = get_object_or_404(User, pk=user_id)
    if edited_user.pk == request.user.pk:
        raise PermissionDenied("Current user cannot be edited.")

    flags_form = AdminUserFlagsForm(user=edited_user)
    email_form = AdminUserEmailForm(user=edited_user)
    password_form = SetPasswordForm(user=edited_user)
    photo_form = ProfilePhotoForm(user=edited_user)
    bio_form = ProfileBioForm(user=edited_user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "flags":
            flags_form = AdminUserFlagsForm(request.POST, user=edited_user)
            if flags_form.is_valid():
                flags_form.save()
                messages.success(request, "User flags updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "email":
            email_form = AdminUserEmailForm(request.POST, user=edited_user)
            if email_form.is_valid():
                email_form.save()
                messages.success(request, "User email updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "password":
            password_form = SetPasswordForm(user=edited_user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "User password updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "photo":
            photo_form = ProfilePhotoForm(request.POST, request.FILES, user=edited_user)
            if photo_form.is_valid():
                photo_form.save()
                messages.success(request, "User photo updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "bio":
            bio_form = ProfileBioForm(request.POST, user=edited_user)
            if bio_form.is_valid():
                bio_form.save()
                messages.success(request, "User bio updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)

    heading = edited_user.get_full_name() or edited_user.email
    return render(
        request,
        "adminui/user_edit.html",
        {
            "edited_user": edited_user,
            "heading": heading,
            "flags_form": flags_form,
            "email_form": email_form,
            "password_form": password_form,
            "photo_form": photo_form,
            "bio_form": bio_form,
        },
    )


@admin_required
def camp(request: HttpRequest) -> HttpResponse:
    form = CampYearCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        camp_year = form.save(commit=False)
        camp_year.created_by = request.user
        camp_year.updated_by = request.user
        camp_year.save()
        messages.success(request, "Camp year created.")
        return redirect(_camp_year_section_url(camp_year, "dashboard-setup"))

    return render(
        request,
        "adminui/camp.html",
        {
            "camp_year_form": form,
            "camp_years": _camp_year_summaries(),
        },
    )


@admin_required
def camp_year_edit(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(
        CampYear.objects.select_related(
            "camp_survey",
            "dashboard_pre_page",
            "dashboard_post_page",
        ),
        year=year,
    )
    pages_form = CampYearDashboardSetupForm(instance=camp_year)
    tax_tier_form = TaxTierCreateForm(camp_year=camp_year)
    tax_add_on_form = TaxAddOnCreateForm(camp_year=camp_year)
    tax_override_form = TaxOverrideCreateForm(camp_year=camp_year)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "dashboard_setup":
            pages_form = CampYearDashboardSetupForm(request.POST, instance=camp_year)
            if pages_form.is_valid():
                updated_year = pages_form.save(commit=False)
                updated_year.updated_by = request.user
                updated_year.save()
                messages.success(request, "Dashboard setup updated.")
                return redirect(_camp_year_section_url(camp_year, "dashboard-setup"))
        elif action == "tax_tier":
            tax_tier_form = TaxTierCreateForm(request.POST, camp_year=camp_year)
            if tax_tier_form.is_valid():
                tax_tier = tax_tier_form.save(commit=False)
                tax_tier.created_by = request.user
                tax_tier.display_order = _next_display_order(TaxTier, camp_year)
                tax_tier.updated_by = request.user
                tax_tier.save()
                messages.success(request, "Tax tier created.")
                return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        elif action == "tax_tier_move_up":
            _move_ordered_item(TaxTier, camp_year, request.POST.get("item_id"), "up")
            return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        elif action == "tax_tier_move_down":
            _move_ordered_item(TaxTier, camp_year, request.POST.get("item_id"), "down")
            return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        elif action == "tax_add_on":
            tax_add_on_form = TaxAddOnCreateForm(request.POST, camp_year=camp_year)
            if tax_add_on_form.is_valid():
                tax_add_on = tax_add_on_form.save(commit=False)
                tax_add_on.created_by = request.user
                tax_add_on.display_order = _next_display_order(TaxAddOn, camp_year)
                tax_add_on.updated_by = request.user
                tax_add_on.save()
                messages.success(request, "Tax add-on created.")
                return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        elif action == "tax_add_on_move_up":
            _move_ordered_item(TaxAddOn, camp_year, request.POST.get("item_id"), "up")
            return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        elif action == "tax_add_on_move_down":
            _move_ordered_item(TaxAddOn, camp_year, request.POST.get("item_id"), "down")
            return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        elif action == "tax_override":
            tax_override_form = TaxOverrideCreateForm(request.POST, camp_year=camp_year)
            if tax_override_form.is_valid():
                tax_override = tax_override_form.save(commit=False)
                tax_override.created_by = request.user
                tax_override.updated_by = request.user
                tax_override.save()
                messages.success(request, "Tax override created.")
                return redirect(_camp_year_section_url(camp_year, "tax-overrides"))
        elif action == "tax_override_delete":
            tax_override = get_object_or_404(
                TaxOverride,
                pk=request.POST.get("override_id"),
                camp_year=camp_year,
            )
            tax_override.delete()
            messages.success(request, "Tax override deleted.")
            return redirect(_camp_year_section_url(camp_year, "tax-overrides"))

    return render(
        request,
        "adminui/camp_year_edit.html",
        {
            "camp_year": camp_year,
            "pages_form": pages_form,
            "tax_add_on_form": tax_add_on_form,
            "tax_add_ons": camp_year.tax_add_ons.order_by("display_order", "id"),
            "tax_override_form": tax_override_form,
            "tax_overrides": TaxOverride.objects.filter(camp_year=camp_year)
            .select_related("user")
            .order_by("user__email"),
            "tax_tier_form": tax_tier_form,
            "tax_tiers": camp_year.tax_tiers.order_by("display_order", "id"),
        },
    )


@admin_required
def camp_tax_tier_edit(request: HttpRequest, year: int, tier_id: int) -> HttpResponse:
    tax_tier = get_object_or_404(
        TaxTier.objects.select_related("camp_year"),
        pk=tier_id,
        camp_year__year=year,
    )
    form = TaxTierCreateForm(
        request.POST or None,
        camp_year=tax_tier.camp_year,
        instance=tax_tier,
    )
    if request.method == "POST":
        if request.POST.get("action") == "delete":
            camp_year = tax_tier.camp_year
            tax_tier.delete()
            messages.success(request, "Tax tier deleted.")
            return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        if form.is_valid():
            updated_tier = form.save(commit=False)
            updated_tier.updated_by = request.user
            updated_tier.save()
            messages.success(request, "Tax tier updated.")
            return redirect(_camp_year_section_url(tax_tier.camp_year, "tax-tiers"))

    return render(
        request,
        "adminui/camp_tax_tier_edit.html",
        {
            "camp_year": tax_tier.camp_year,
            "form": form,
            "tax_tier": tax_tier,
        },
    )


@admin_required
def camp_tax_add_on_edit(request: HttpRequest, year: int, add_on_id: int) -> HttpResponse:
    tax_add_on = get_object_or_404(
        TaxAddOn.objects.select_related("camp_year"),
        pk=add_on_id,
        camp_year__year=year,
    )
    form = TaxAddOnCreateForm(
        request.POST or None,
        camp_year=tax_add_on.camp_year,
        instance=tax_add_on,
    )
    if request.method == "POST":
        if request.POST.get("action") == "delete":
            camp_year = tax_add_on.camp_year
            tax_add_on.delete()
            messages.success(request, "Tax add-on deleted.")
            return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        if form.is_valid():
            updated_add_on = form.save(commit=False)
            updated_add_on.updated_by = request.user
            updated_add_on.save()
            messages.success(request, "Tax add-on updated.")
            return redirect(_camp_year_section_url(tax_add_on.camp_year, "tax-add-ons"))

    return render(
        request,
        "adminui/camp_tax_add_on_edit.html",
        {
            "camp_year": tax_add_on.camp_year,
            "form": form,
            "tax_add_on": tax_add_on,
        },
    )


@admin_required
def payments(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "adminui/payments.html",
        {
            "payments": Payment.objects.select_related("user", "camp_year"),
            "logs": PaymentLog.objects.select_related("payment", "payment__user")[:50],
        },
    )


@admin_required
def stripe(request: HttpRequest) -> HttpResponse:
    site_settings = SiteSettings.load()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "switch_mode":
            site_settings.stripe_mode = request.POST.get(
                "stripe_mode",
                SiteSettings.StripeMode.TEST,
            )
            site_settings.save(update_fields=["stripe_mode", "updated_at"])
            messages.success(request, "Stripe mode switched.")
            return redirect("adminui:stripe")
        if action == "delete_test_payments" and request.POST.get("confirm") == "delete":
            test_payments = Payment.objects.filter(stripe_mode=Payment.StripeMode.TEST)
            count = test_payments.count()
            PaymentLog.objects.filter(payment__in=test_payments).delete()
            test_payments.delete()
            messages.success(request, f"Deleted {count} test payments.")
            return redirect("adminui:stripe")

    return render(
        request,
        "adminui/stripe.html",
        {
            "site_settings": site_settings,
            "logs": PaymentLog.objects.all()[:50],
            "test_payment_count": Payment.objects.filter(
                stripe_mode=Payment.StripeMode.TEST,
            ).count(),
        },
    )


@admin_required
def pages(request: HttpRequest) -> HttpResponse:
    form = ContentPageForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = ContentPageForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Page saved.")
                return redirect("adminui:pages")
    return render(
        request,
        "adminui/pages.html",
        {"pages": ContentPage.objects.all(), "form": form},
    )


@admin_required
def page_edit(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(ContentPage, slug=slug)
    form = ContentPageForm(request.POST or None, instance=page)

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            try:
                page.delete()
                messages.success(request, "Page deleted.")
                return redirect("adminui:pages")
            except ProtectedError:
                messages.error(request, "Page is in use and cannot be deleted.")
                return redirect("adminui:page-edit", slug=page.slug)

        if form.is_valid():
            updated_page = form.save()
            messages.success(request, "Page updated.")
            if request.POST.get("redirect_to") == "view":
                return redirect(updated_page.get_absolute_url())
            return redirect("adminui:pages")

    return render(
        request,
        "adminui/page_edit.html",
        {"form": form, "page": page},
    )


@admin_required
def surveys(request: HttpRequest) -> HttpResponse:
    form = SurveyCreateForm()

    if request.method == "POST" and request.POST.get("action") == "create_survey":
        form = SurveyCreateForm(request.POST)
        if form.is_valid():
            survey = form.save()
            messages.success(request, "Survey created.")
            return redirect("adminui:survey-edit", slug=survey.slug)

    all_surveys = list(
        Survey.objects.annotate(response_count=Count("responses")).order_by("name", "slug"),
    )
    return render(
        request,
        "adminui/surveys.html",
        {
            "form": form,
            "survey_rows": [
                {
                    "edit_url": reverse("adminui:survey-edit", kwargs={"slug": survey.slug}),
                    "is_active": survey.is_active,
                    "name": survey.name,
                    "response_count": survey.response_count,
                    "responses_url": reverse(
                        "adminui:survey-responses",
                        kwargs={"slug": survey.slug},
                    ),
                    "slug": survey.slug,
                }
                for survey in all_surveys
            ],
            "surveys": [survey for survey in all_surveys if survey.is_active],
        },
    )


@admin_required
def survey_edit(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    survey_form = SurveyAdminForm(instance=survey)
    question_create_form = SurveyQuestionCreateForm(survey=survey)
    bound_question_forms = {}
    bound_option_forms = {}
    bound_choice_forms = {}
    bound_choice_create_forms = {}

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_survey":
            survey_form = SurveyAdminForm(request.POST, instance=survey)
            if survey_form.is_valid():
                updated_survey = survey_form.save()
                messages.success(request, "Survey updated.")
                return redirect(_survey_section_url(updated_survey, "survey-details"))
        elif action == "create_question":
            question_create_form = SurveyQuestionCreateForm(request.POST, survey=survey)
            if question_create_form.is_valid():
                question = question_create_form.save(display_order=next_question_order(survey))
                messages.success(request, "Question created.")
                return redirect(_survey_section_url(survey, f"question-{question.id}"))
        elif action in {
            "update_question",
            "edit_question",
            "question_move_up",
            "question_move_down",
        }:
            question = get_object_or_404(
                SurveyQuestion,
                pk=request.POST.get("question_id"),
                survey=survey,
            )
            question_form = SurveyQuestionAdminForm(request.POST, instance=question)
            option_form = SurveyQuestionOptionsForm(request.POST, question=question)
            if question_form.is_valid() and option_form.is_valid():
                question_form.save()
                option_form.save()
                if action == "question_move_up":
                    move_question(question, "up")
                elif action == "question_move_down":
                    move_question(question, "down")
                elif action == "edit_question":
                    messages.success(request, "Question updated.")
                    return redirect(
                        "adminui:survey-question-edit",
                        slug=survey.slug,
                        question_id=question.id,
                    )
                messages.success(request, "Question updated.")
                return redirect(_survey_section_url(survey, f"question-{question.id}"))
            bound_question_forms[question.id] = question_form
            bound_option_forms[question.id] = option_form
        elif action == "create_choice":
            question = get_object_or_404(
                SurveyQuestion,
                pk=request.POST.get("question_id"),
                survey=survey,
            )
            question_form = SurveyQuestionAdminForm(request.POST, instance=question)
            option_form = SurveyQuestionOptionsForm(request.POST, question=question)
            choice_form = SurveyChoiceCreateForm(request.POST, question=question)
            question_forms_valid = question_form.is_valid() and option_form.is_valid()
            if question_forms_valid:
                question_form.save()
                option_form.save()
            if question_forms_valid and choice_form.is_valid():
                choice = choice_form.save(commit=False)
                choice.display_order = next_choice_order(question)
                choice.save()
                messages.success(request, "Choice created.")
                return redirect(_survey_section_url(survey, f"question-{question.id}"))
            bound_question_forms[question.id] = question_form
            bound_option_forms[question.id] = option_form
            bound_choice_create_forms[question.id] = choice_form
        elif action == "update_choice":
            choice = get_object_or_404(
                SurveyChoice.objects.select_related("question", "question__survey"),
                pk=request.POST.get("choice_id"),
                question__survey=survey,
            )
            choice_form = SurveyChoiceForm(request.POST, instance=choice)
            if choice_form.is_valid():
                choice_form.save()
                messages.success(request, "Choice updated.")
                return redirect(_survey_section_url(survey, f"question-{choice.question_id}"))
            bound_choice_forms[choice.id] = choice_form
        elif action in {"choice_move_up", "choice_move_down"}:
            choice = get_object_or_404(
                SurveyChoice.objects.select_related("question", "question__survey"),
                pk=request.POST.get("choice_id"),
                question__survey=survey,
            )
            move_choice(choice, "up" if action == "choice_move_up" else "down")
            return redirect(_survey_section_url(survey, f"question-{choice.question_id}"))
        elif action == "delete_choice":
            choice = get_object_or_404(
                SurveyChoice.objects.select_related("question", "question__survey"),
                pk=request.POST.get("choice_id"),
                question__survey=survey,
            )
            question_id = choice.question_id
            try:
                choice.delete()
                messages.success(request, "Choice deleted.")
            except ValidationError as error:
                messages.error(request, error.messages[0])
            return redirect(_survey_section_url(survey, f"question-{question_id}"))
        elif action == "delete_survey":
            confirmation = request.POST.get("confirm", "")
            answer_count = SurveyAnswer.objects.filter(response__survey=survey).count()
            response_count = survey.responses.count()
            if (answer_count or response_count) and confirmation != "delete":
                messages.error(
                    request,
                    "Type delete to confirm deleting this survey and its responses.",
                )
                return redirect(_survey_section_url(survey, "delete-survey"))
            survey.delete()
            messages.success(request, "Survey deleted.")
            return redirect("adminui:surveys")

    return render(
        request,
        "adminui/survey_edit.html",
        {
            "question_cards": _survey_question_cards(
                survey,
                bound_question_forms,
                bound_option_forms,
                bound_choice_forms,
                bound_choice_create_forms,
            ),
            "question_create_form": question_create_form,
            "survey": survey,
            "survey_form": survey_form,
            "survey_answer_count": SurveyAnswer.objects.filter(response__survey=survey).count(),
            "survey_response_count": survey.responses.count(),
        },
    )


@admin_required
def survey_question_edit(request: HttpRequest, slug: str, question_id: int) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    question = get_object_or_404(SurveyQuestion, pk=question_id, survey=survey)
    question_form = SurveyQuestionAdminForm(instance=question)
    option_form = SurveyQuestionOptionsForm(question=question)
    condition_form = SurveyConditionForm(question=question)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "update_question":
            question_form = SurveyQuestionAdminForm(request.POST, instance=question)
            option_form = SurveyQuestionOptionsForm(request.POST, question=question)
            if question_form.is_valid() and option_form.is_valid():
                question_form.save()
                option_form.save()
                messages.success(request, "Question updated.")
                return redirect(_survey_question_section_url(survey, question, "question-details"))
        elif action == "update_conditions":
            condition_form = SurveyConditionForm(request.POST, question=question)
            if condition_form.is_valid():
                condition_form.save()
                messages.success(request, "Conditions updated.")
                return redirect(_survey_question_section_url(survey, question, "conditional"))
        elif action == "delete_question":
            question.delete()
            messages.success(request, "Question deleted.")
            return redirect(_survey_section_url(survey, "create-question"))

    _set_form_attr(question_form, f"question-detail-form-{question.id}")
    _set_form_attr(option_form, f"question-detail-form-{question.id}")
    return render(
        request,
        "adminui/survey_question_edit.html",
        {
            "condition_form": condition_form,
            "question": question,
            "question_form": question_form,
            "option_form": option_form,
            "survey": survey,
        },
    )


@admin_required
def survey_responses(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    response_matrix = _survey_response_matrix(survey)
    return render(
        request,
        "adminui/survey_responses.html",
        {
            "response_rows": response_matrix["rows"],
            "questions": response_matrix["questions"],
            "survey": survey,
        },
    )


@admin_required
def survey_export(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    response_matrix = _survey_response_matrix(survey)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["Name", "Email"] + [question.name for question in response_matrix["questions"]],
    )
    for response_row in response_matrix["rows"]:
        row = [response_row["name"], response_row["email"], *response_row["answers"]]
        writer.writerow(row)
    response = HttpResponse(output.getvalue(), content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{survey.slug}-responses.csv"'
    return response


def _survey_response_matrix(survey: Survey) -> dict[str, object]:
    questions = list(survey.questions.order_by("display_order", "id"))
    rows = []
    for response in survey.responses.select_related("user").prefetch_related("answers"):
        answers = {
            answer.question_id: answer for answer in response.answers.all() if answer.question_id
        }
        rows.append(
            {
                "answers": [
                    _survey_answer_display(answers.get(question.id)) for question in questions
                ],
                "email": response.user.email,
                "name": response.user.get_full_name(),
            }
        )
    return {"questions": questions, "rows": rows}


def _survey_answer_display(answer: SurveyAnswer | None) -> str:
    if answer is None:
        return ""
    return "; ".join(load_answer_json(answer.value))


@admin_required
def menus(request: HttpRequest) -> HttpResponse:
    Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
    menu_form = MenuForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_menu":
            menu_form = MenuForm(request.POST)
            if menu_form.is_valid():
                menu = menu_form.save()
                messages.success(request, "Menu saved.")
                return redirect("adminui:menu-edit", menu_name=menu.menu_name)
    return render(
        request,
        "adminui/menus.html",
        {
            "menus": _menus_with_item_summaries(),
            "menu_form": menu_form,
        },
    )


@admin_required
def menu_edit(request: HttpRequest, menu_name: str) -> HttpResponse:
    menu = get_object_or_404(Menu, menu_name=menu_name)
    item_form = MenuItemForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_item":
            item_form = MenuItemForm(request.POST)
            if item_form.is_valid():
                item = item_form.save(commit=False)
                item.menu = menu
                item.display_order = _next_menu_item_display_order(menu)
                item.save()
                messages.success(request, "Menu item saved.")
                return redirect(_menu_section_url(menu, "menu-items"))
        elif action == "menu_item_move_up":
            _move_menu_item(menu, request.POST.get("item_id"), "up")
            return redirect(_menu_section_url(menu, "menu-items"))
        elif action == "menu_item_move_down":
            _move_menu_item(menu, request.POST.get("item_id"), "down")
            return redirect(_menu_section_url(menu, "menu-items"))
        elif action == "delete_menu":
            try:
                menu.delete()
                messages.success(request, "Menu deleted.")
                return redirect("adminui:menus")
            except ValidationError as error:
                messages.error(request, error.messages[0])
                return redirect("adminui:menu-edit", menu_name=menu.menu_name)

    return render(
        request,
        "adminui/menu_edit.html",
        {
            "item_form": item_form,
            "menu": menu,
            "menu_items": menu.items.order_by("display_order", "id"),
            "url_suggestions": _menu_url_suggestions(),
        },
    )


@admin_required
def menu_item_edit(request: HttpRequest, item_id: int) -> HttpResponse:
    menu_item = get_object_or_404(MenuItem.objects.select_related("menu"), pk=item_id)
    form = MenuItemForm(request.POST or None, instance=menu_item)

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            menu = menu_item.menu
            menu_item.delete()
            messages.success(request, "Menu item deleted.")
            return redirect(_menu_section_url(menu, "menu-items"))
        if form.is_valid():
            form.save()
            messages.success(request, "Menu item updated.")
            return redirect(_menu_section_url(menu_item.menu, "menu-items"))

    return render(
        request,
        "adminui/menu_item_edit.html",
        {
            "form": form,
            "menu": menu_item.menu,
            "menu_item": menu_item,
            "url_suggestions": _menu_url_suggestions(),
        },
    )


@admin_required
def media(request: HttpRequest) -> HttpResponse:
    form = MediaUploadAdminForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "upload":
            form = MediaUploadAdminForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                messages.success(request, "Media uploaded.")
                return redirect("adminui:media")
        elif action == "delete":
            media_item = get_object_or_404(MediaItem, pk=request.POST.get("media_id"))
            media_item.delete()
            messages.success(request, "Media deleted.")
            return redirect("adminui:media")
    return render(
        request,
        "adminui/media.html",
        {"media_items": MediaItem.objects.all(), "form": form},
    )


def _camp_year_summaries() -> list[CampYear]:
    camp_years = list(
        CampYear.objects.annotate(
            override_count=Count("tax_overrides", distinct=True),
            tax_add_on_count=Count("tax_add_ons", distinct=True),
            tax_closes_at=Max("tax_tiers__expiration_date"),
            tax_opens_at=Min("tax_tiers__start_date"),
            tax_tier_count=Count("tax_tiers", distinct=True),
        ).order_by("-year"),
    )
    camp_year_ids = [camp_year.id for camp_year in camp_years]
    paid_user_ids = _user_ids_by_camp_year(
        Payment.objects.filter(
            camp_year_id__in=camp_year_ids,
            status=Payment.Status.PAID,
        ),
    )
    override_user_ids = _user_ids_by_camp_year(
        TaxOverride.objects.filter(camp_year_id__in=camp_year_ids),
    )
    waived_user_ids = _user_ids_by_camp_year(
        TaxOverride.objects.filter(
            camp_year_id__in=camp_year_ids,
            override_type=TaxOverride.OverrideType.WAIVED,
        ),
    )

    for camp_year in camp_years:
        paid_users = paid_user_ids.get(camp_year.id, set())
        override_users = override_user_ids.get(camp_year.id, set())
        camp_year.paid_count = len(paid_users)
        camp_year.people_count = len(paid_users | override_users)
        camp_year.waived_count = len(waived_user_ids.get(camp_year.id, set()))

    return camp_years


def _user_ids_by_camp_year(queryset) -> dict[int, set[int]]:
    user_ids: dict[int, set[int]] = {}
    for camp_year_id, user_id in queryset.values_list("camp_year_id", "user_id").distinct():
        user_ids.setdefault(camp_year_id, set()).add(user_id)
    return user_ids


def _camp_year_section_url(camp_year: CampYear, section_id: str) -> str:
    return reverse("adminui:camp-year-edit", kwargs={"year": camp_year.year}) + f"#{section_id}"


def _menu_section_url(menu: Menu, section_id: str) -> str:
    return reverse("adminui:menu-edit", kwargs={"menu_name": menu.menu_name}) + f"#{section_id}"


def _survey_section_url(survey: Survey, section_id: str) -> str:
    return reverse("adminui:survey-edit", kwargs={"slug": survey.slug}) + f"#{section_id}"


def _survey_question_section_url(
    survey: Survey,
    question: SurveyQuestion,
    section_id: str,
) -> str:
    return (
        reverse(
            "adminui:survey-question-edit",
            kwargs={"slug": survey.slug, "question_id": question.id},
        )
        + f"#{section_id}"
    )


def _set_form_attr(form, form_id: str) -> None:
    for field in form.fields.values():
        field.widget.attrs["form"] = form_id


def _survey_question_cards(
    survey: Survey,
    bound_question_forms: dict[int, SurveyQuestionAdminForm] | None = None,
    bound_option_forms: dict[int, SurveyQuestionOptionsForm] | None = None,
    bound_choice_forms: dict[int, SurveyChoiceForm] | None = None,
    bound_choice_create_forms: dict[int, SurveyChoiceCreateForm] | None = None,
) -> list[dict[str, object]]:
    bound_question_forms = bound_question_forms or {}
    bound_option_forms = bound_option_forms or {}
    bound_choice_forms = bound_choice_forms or {}
    bound_choice_create_forms = bound_choice_create_forms or {}
    cards = []
    questions = list(survey.questions.prefetch_related("choices").order_by("display_order", "id"))
    for index, question in enumerate(questions):
        form_id = f"question-form-{question.id}"
        question_form = bound_question_forms.get(
            question.id,
            SurveyQuestionAdminForm(instance=question),
        )
        option_form = bound_option_forms.get(
            question.id,
            SurveyQuestionOptionsForm(question=question),
        )
        _set_form_attr(question_form, form_id)
        _set_form_attr(option_form, form_id)
        choice_create_form = bound_choice_create_forms.get(
            question.id,
            SurveyChoiceCreateForm(question=question),
        )
        _set_form_attr(choice_create_form, form_id)
        choices = []
        for choice in question.choices.all():
            choices.append(
                {
                    "choice": choice,
                    "form": bound_choice_forms.get(choice.id, SurveyChoiceForm(instance=choice)),
                }
            )
        cards.append(
            {
                "choice_create_form": choice_create_form,
                "choices": choices,
                "form_id": form_id,
                "is_choice_based": is_choice_question_type(question.question_type),
                "is_first": index == 0,
                "is_last": index == len(questions) - 1,
                "option_form": option_form,
                "question": question,
                "question_form": question_form,
            }
        )
    return cards


def _menus_with_item_summaries() -> list[Menu]:
    menus = list(Menu.objects.prefetch_related("items").order_by("menu_name"))
    for menu in menus:
        labels = [item.label for item in menu.items.all()]
        menu.item_summary = ", ".join(labels) if labels else "----"
    return menus


def _menu_url_suggestions() -> list[str]:
    suggestions = ["/dashboard/", "/phagebook/", "/profile/"]
    current_year = get_current_camp_year()
    if current_year is not None:
        suggestions.extend(
            [
                reverse("camp:dashboard", kwargs={"year": current_year.year}),
                reverse("camp:phagebook", kwargs={"year": current_year.year}),
                reverse("camp:taxes", kwargs={"year": current_year.year}),
            ],
        )
    suggestions.extend(page.get_absolute_url() for page in ContentPage.objects.order_by("slug"))
    suggestions.extend(
        reverse("content:menu-detail", kwargs={"menu_name": menu.menu_name})
        for menu in Menu.objects.order_by("menu_name")
    )
    return list(dict.fromkeys(suggestions))


def _next_menu_item_display_order(menu: Menu) -> int:
    max_order = menu.items.aggregate(Max("display_order"))["display_order__max"]
    return (max_order or 0) + 1


def _move_menu_item(menu: Menu, item_id: str | None, direction: str) -> None:
    with transaction.atomic():
        item = get_object_or_404(
            MenuItem.objects.select_for_update(),
            pk=item_id,
            menu=menu,
        )
        items = list(
            MenuItem.objects.select_for_update()
            .filter(menu=menu)
            .order_by("display_order", "id"),
        )
        current_index = next(
            index for index, candidate in enumerate(items) if candidate.pk == item.pk
        )
        if direction == "up" and current_index > 0:
            swap_index = current_index - 1
        elif direction == "down" and current_index < len(items) - 1:
            swap_index = current_index + 1
        else:
            swap_index = current_index

        items[current_index], items[swap_index] = items[swap_index], items[current_index]
        for display_order, ordered_item in enumerate(items, start=1):
            if ordered_item.display_order != display_order:
                ordered_item.display_order = display_order
                ordered_item.save(update_fields=["display_order", "updated_at"])


def _next_display_order(model, camp_year: CampYear) -> int:
    max_order = model.objects.filter(camp_year=camp_year).aggregate(Max("display_order"))[
        "display_order__max"
    ]
    return (max_order or 0) + 1


def _move_ordered_item(model, camp_year: CampYear, item_id: str | None, direction: str) -> None:
    with transaction.atomic():
        item = get_object_or_404(
            model.objects.select_for_update(),
            pk=item_id,
            camp_year=camp_year,
        )
        items = list(
            model.objects.select_for_update()
            .filter(camp_year=camp_year)
            .order_by("display_order", "id"),
        )
        current_index = next(
            index for index, candidate in enumerate(items) if candidate.pk == item.pk
        )
        if direction == "up" and current_index > 0:
            swap_index = current_index - 1
        elif direction == "down" and current_index < len(items) - 1:
            swap_index = current_index + 1
        else:
            swap_index = current_index

        items[current_index], items[swap_index] = items[swap_index], items[current_index]
        for display_order, ordered_item in enumerate(items, start=1):
            if ordered_item.display_order != display_order:
                ordered_item.display_order = display_order
                ordered_item.save(update_fields=["display_order", "updated_at"])
