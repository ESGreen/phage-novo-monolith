from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import member_required
from content.markdown import render_markdown

from .models import Survey, SurveyResponse
from .question_types import (
    QUESTION_TYPE_MULTI_CHOICE,
    QUESTION_TYPE_TEXT,
    RENDER_HINT_CHECKBOXES,
    RENDER_HINT_DATE,
    RENDER_HINT_EMAIL,
    RENDER_HINT_LONG_TEXT,
    RENDER_HINT_NUMBER,
    RENDER_HINT_PHONE,
    RENDER_HINT_RADIO,
    RENDER_HINT_SCALE,
    RENDER_HINT_SELECT,
)
from .services import OTHER_VALUE, load_answer_json, load_choice_snapshot, submit_survey_response


@member_required
def survey_detail(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug, is_active=True)
    response = SurveyResponse.objects.filter(survey=survey, user=request.user).first()
    errors: dict[int, list[str]] = {}
    if request.method == "POST":
        result = submit_survey_response(survey, request.user, request.POST)
        if result.success:
            return redirect("surveys:survey-complete", slug=survey.slug)
        errors = result.errors

    response = SurveyResponse.objects.filter(survey=survey, user=request.user).first()
    return render(
        request,
        "surveys/survey_detail.html",
        {
            "description_html": render_markdown(survey.description_markdown),
            "question_cards": _question_cards(survey, response, errors),
            "survey": survey,
        },
    )


@member_required
def survey_complete(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug)
    return render(request, "surveys/survey_complete.html", {"survey": survey})


def _question_cards(
    survey: Survey,
    response: SurveyResponse | None,
    errors: dict[int, list[str]],
) -> list[dict[str, object]]:
    answers = {}
    if response is not None:
        answers = {
            answer.question_id: answer
            for answer in response.answers.filter(question__isnull=False).select_related("question")
        }

    cards = []
    for question in survey.questions.prefetch_related("choices", "conditions"):
        answer = answers.get(question.id)
        values = load_answer_json(answer.value) if answer is not None else []
        snapshot = load_choice_snapshot(answer.choice_snapshot) if answer is not None else []
        selected_choice_ids = {
            int(item["choice_id"])
            for item in snapshot
            if item.get("source") == "choice" and str(item.get("choice_id", "")).isdigit()
        }
        other_values = [
            str(item.get("value", "")) for item in snapshot if item.get("source") == "other"
        ]
        conditions = list(question.conditions.all())
        condition_parent_id = conditions[0].depends_on_question_id if conditions else ""
        condition_choice_ids = [str(condition.visible_if_choice_id) for condition in conditions]
        cards.append(
            {
                "condition_choice_ids": ",".join(condition_choice_ids),
                "condition_parent_id": condition_parent_id,
                "description_html": render_markdown(question.description_markdown),
                "errors": errors.get(question.id, []),
                "field_name": f"question_{question.id}",
                "input_type": _input_type(question.render_hint),
                "is_checkboxes": question.render_hint == RENDER_HINT_CHECKBOXES,
                "is_date": question.render_hint == RENDER_HINT_DATE,
                "is_long_text": question.render_hint == RENDER_HINT_LONG_TEXT,
                "is_multi_choice": question.question_type == QUESTION_TYPE_MULTI_CHOICE,
                "is_radio": question.render_hint in {RENDER_HINT_RADIO, RENDER_HINT_SCALE},
                "is_select": question.render_hint == RENDER_HINT_SELECT,
                "is_text": question.question_type == QUESTION_TYPE_TEXT,
                "other_name": f"question_{question.id}_other",
                "other_selected": bool(other_values),
                "other_value": other_values[0] if other_values else "",
                "other_value_key": OTHER_VALUE,
                "question": question,
                "selected_choice_ids": selected_choice_ids,
                "text_value": values[0] if values else "",
            }
        )
    return cards


def _input_type(render_hint: str) -> str:
    return {
        RENDER_HINT_EMAIL: "email",
        RENDER_HINT_PHONE: "tel",
        RENDER_HINT_NUMBER: "text",
        RENDER_HINT_DATE: "date",
    }.get(render_hint, "text")
