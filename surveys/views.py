from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

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
from .services import (
    OTHER_VALUE,
    ParsedAnswer,
    load_answer_json,
    load_choice_snapshot,
    submit_survey_response,
)


@member_required
def survey_detail(request: HttpRequest, slug: str) -> HttpResponse:
    survey = get_object_or_404(Survey, slug=slug, is_active=True)
    response = SurveyResponse.objects.filter(survey=survey, user=request.user).first()
    errors: dict[int, list[str]] = {}
    parsed_answers: dict[int, ParsedAnswer] | None = None
    if request.method == "POST":
        result = submit_survey_response(survey, request.user, request.POST)
        if result.success:
            return redirect(_survey_success_url(survey))
        errors = result.errors
        parsed_answers = result.answers

    response = SurveyResponse.objects.filter(survey=survey, user=request.user).first()
    question_cards = _question_cards(survey, response, errors, parsed_answers)
    return render(
        request,
        "surveys/survey_detail.html",
        {
            "description_html": render_markdown(survey.description_markdown),
            "question_cards": question_cards,
            "survey": survey,
            "survey_has_errors": bool(errors),
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
    parsed_answers: dict[int, ParsedAnswer] | None = None,
) -> list[dict[str, object]]:
    answers = {}
    if response is not None:
        answers = {
            answer.question_id: answer
            for answer in response.answers.filter(question__isnull=False).select_related("question")
        }

    cards = []
    for question in survey.questions.prefetch_related("choices", "conditions"):
        if parsed_answers is not None and question.id in parsed_answers:
            values, selected_choice_ids, other_selected, other_value = _parsed_answer_state(
                parsed_answers[question.id]
            )
        else:
            values, selected_choice_ids, other_selected, other_value = _stored_answer_state(
                answers.get(question.id)
            )
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
                "other_selected": other_selected,
                "other_value": other_value,
                "other_value_key": OTHER_VALUE,
                "question": question,
                "selected_choice_ids": selected_choice_ids,
                "text_value": values[0] if values else "",
            }
        )
    return cards


def _parsed_answer_state(parsed: ParsedAnswer) -> tuple[list[str], set[int], bool, str]:
    return (
        parsed.values,
        {choice_id for choice_id in parsed.selected_choice_ids if choice_id > 0},
        parsed.other_selected,
        parsed.other_value,
    )


def _stored_answer_state(answer) -> tuple[list[str], set[int], bool, str]:
    if answer is None:
        return [], set(), False, ""
    values = load_answer_json(answer.value)
    snapshot = load_choice_snapshot(answer.choice_snapshot)
    selected_choice_ids = {
        int(item["choice_id"])
        for item in snapshot
        if item.get("source") == "choice" and str(item.get("choice_id", "")).isdigit()
    }
    other_values = [
        str(item.get("value", "")) for item in snapshot if item.get("source") == "other"
    ]
    return values, selected_choice_ids, bool(other_values), other_values[0] if other_values else ""


def _survey_success_url(survey: Survey) -> str:
    return survey.redirect_after_submission_url or reverse(
        "surveys:survey-complete",
        kwargs={"slug": survey.slug},
    )


def _input_type(render_hint: str) -> str:
    return {
        RENDER_HINT_EMAIL: "email",
        RENDER_HINT_PHONE: "tel",
        RENDER_HINT_NUMBER: "text",
        RENDER_HINT_DATE: "date",
    }.get(render_hint, "text")
