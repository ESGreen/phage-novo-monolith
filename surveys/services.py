from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import transaction
from django.utils.dateparse import parse_date

from .models import Survey, SurveyAnswer, SurveyChoice, SurveyQuestion, SurveyQuestionCondition
from .question_types import (
    QUESTION_TYPE_SINGLE_CHOICE,
    QUESTION_TYPE_TEXT,
    RENDER_HINT_DATE,
    RENDER_HINT_EMAIL,
    RENDER_HINT_NUMBER,
)

OTHER_VALUE = "__other__"


@dataclass
class ParsedAnswer:
    values: list[str] = field(default_factory=list)
    choice_snapshot: list[dict[str, object]] = field(default_factory=list)
    selected_choice_ids: set[int] = field(default_factory=set)
    other_selected: bool = False
    other_value: str = ""


@dataclass
class SubmissionResult:
    success: bool
    errors: dict[int, list[str]] = field(default_factory=dict)


def answer_json(values: list[str]) -> str:
    return json.dumps(values)


def load_answer_json(value: str) -> list[str]:
    try:
        loaded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def load_choice_snapshot(value: str) -> list[dict[str, object]]:
    try:
        loaded = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(loaded, list):
        return []
    return [item for item in loaded if isinstance(item, dict)]


def validate_condition_graph(
    survey: Survey,
    proposed_question: SurveyQuestion | None = None,
    proposed_depends_on_question: SurveyQuestion | None = None,
) -> None:
    edges: dict[int, set[int]] = {}
    conditions = SurveyQuestionCondition.objects.filter(question__survey=survey).select_related(
        "question",
        "depends_on_question",
    )
    for condition in conditions:
        if proposed_question is not None and condition.question_id == proposed_question.id:
            continue
        edges.setdefault(condition.question_id, set()).add(condition.depends_on_question_id)

    if proposed_question is not None and proposed_depends_on_question is not None:
        edges.setdefault(proposed_question.id, set()).add(proposed_depends_on_question.id)

    visiting: set[int] = set()
    visited: set[int] = set()

    def visit(question_id: int) -> bool:
        if question_id in visiting:
            return True
        if question_id in visited:
            return False
        visiting.add(question_id)
        for parent_id in edges.get(question_id, set()):
            if visit(parent_id):
                return True
        visiting.remove(question_id)
        visited.add(question_id)
        return False

    for question_id in edges:
        if visit(question_id):
            raise ValidationError("Conditions cannot create a circular dependency.")


def validate_condition_update(
    question: SurveyQuestion,
    depends_on_question: SurveyQuestion,
    choices: list[SurveyChoice],
) -> None:
    if question.survey_id != depends_on_question.survey_id:
        raise ValidationError("Condition questions must be in the same survey.")
    if question.id == depends_on_question.id:
        raise ValidationError("A question cannot depend on itself.")
    if not depends_on_question.is_choice_based:
        raise ValidationError("Conditions can only depend on choice questions.")
    if not choices:
        raise ValidationError("Choose at least one choice for the condition.")
    for choice in choices:
        if choice.question_id != depends_on_question.id:
            raise ValidationError("Condition choices must belong to the controlling question.")

    validate_condition_graph(question.survey, question, depends_on_question)


def replace_conditions(
    question: SurveyQuestion,
    depends_on_question: SurveyQuestion | None,
    choices: list[SurveyChoice],
) -> None:
    if depends_on_question is None:
        with transaction.atomic():
            question.conditions.all().delete()
        return

    validate_condition_update(question, depends_on_question, choices)

    with transaction.atomic():
        question.conditions.all().delete()
        SurveyQuestionCondition.objects.bulk_create(
            [
                SurveyQuestionCondition(
                    question=question,
                    depends_on_question=depends_on_question,
                    visible_if_choice=choice,
                )
                for choice in choices
            ]
        )


def next_question_order(survey: Survey) -> int:
    max_order = (
        survey.questions.order_by("-display_order").values_list("display_order", flat=True).first()
    )
    return (max_order or 0) + 1


def next_choice_order(question: SurveyQuestion) -> int:
    max_order = (
        question.choices.order_by("-display_order").values_list("display_order", flat=True).first()
    )
    return (max_order or 0) + 1


def move_question(question: SurveyQuestion, direction: str) -> None:
    with transaction.atomic():
        questions = list(
            SurveyQuestion.objects.select_for_update()
            .filter(survey=question.survey)
            .order_by("display_order", "id")
        )
        _move_ordered_item(questions, question.id, direction)


def move_choice(choice: SurveyChoice, direction: str) -> None:
    with transaction.atomic():
        choices = list(
            SurveyChoice.objects.select_for_update()
            .filter(question=choice.question)
            .order_by("display_order", "id")
        )
        _move_ordered_item(choices, choice.id, direction)


def _move_ordered_item(items: list[Any], item_id: int, direction: str) -> None:
    current_index = next(index for index, item in enumerate(items) if item.id == item_id)
    if direction == "up" and current_index > 0:
        swap_index = current_index - 1
    elif direction == "down" and current_index < len(items) - 1:
        swap_index = current_index + 1
    else:
        swap_index = current_index
    items[current_index], items[swap_index] = items[swap_index], items[current_index]
    for display_order, item in enumerate(items, start=1):
        if item.display_order != display_order:
            item.display_order = display_order
            item.save(update_fields=["display_order", "updated_at"])


def submit_survey_response(survey: Survey, user: object, post_data: Any) -> SubmissionResult:
    questions = list(_questions_for_survey(survey))
    answers = {question.id: _parse_question_answer(question, post_data) for question in questions}
    visible_ids = _visible_question_ids(questions, answers)
    errors: dict[int, list[str]] = {}

    for question in questions:
        parsed = answers[question.id]
        if question.id not in visible_ids:
            continue
        _validate_answer(question, parsed, errors)

    if errors:
        return SubmissionResult(success=False, errors=errors)

    with transaction.atomic():
        response, _ = survey.responses.get_or_create(user=user)
        for question in questions:
            parsed = answers[question.id]
            if question.id not in visible_ids:
                parsed = ParsedAnswer()
            SurveyAnswer.objects.update_or_create(
                response=response,
                question=question,
                defaults={
                    "question_id_snapshot": question.id,
                    "question_name_snapshot": question.name,
                    "question_type_snapshot": question.question_type,
                    "render_hint_snapshot": question.render_hint,
                    "value": answer_json(parsed.values),
                    "choice_snapshot": json.dumps(parsed.choice_snapshot),
                },
            )
    return SubmissionResult(success=True)


def _questions_for_survey(survey: Survey):
    return survey.questions.prefetch_related(
        "choices",
        "conditions",
        "conditions__visible_if_choice",
    )


def _parse_question_answer(question: SurveyQuestion, post_data: Any) -> ParsedAnswer:
    if question.question_type == QUESTION_TYPE_TEXT:
        value = (post_data.get(_field_name(question)) or "").strip()
        return ParsedAnswer(values=[value] if value else [])

    choices_by_id = {choice.id: choice for choice in question.choices.all()}
    if question.question_type == QUESTION_TYPE_SINGLE_CHOICE:
        raw_values = [value for value in post_data.getlist(_field_name(question)) if value]
        return _parse_choice_values(question, choices_by_id, raw_values, post_data)

    raw_values = [value for value in post_data.getlist(_field_name(question)) if value]
    return _parse_choice_values(question, choices_by_id, raw_values, post_data)


def _parse_choice_values(
    question: SurveyQuestion,
    choices_by_id: dict[int, SurveyChoice],
    raw_values: list[str],
    post_data: Any,
) -> ParsedAnswer:
    parsed = ParsedAnswer()
    other_text = (post_data.get(_other_field_name(question)) or "").strip()
    for raw_value in raw_values:
        if raw_value == OTHER_VALUE:
            parsed.other_selected = True
            parsed.other_value = other_text
            if other_text:
                parsed.values.append(other_text)
                parsed.choice_snapshot.append(
                    {
                        "source": "other",
                        "label": question.other_label or "Other",
                        "value": other_text,
                    }
                )
            continue
        try:
            choice_id = int(raw_value)
        except ValueError:
            parsed.selected_choice_ids.add(-1)
            continue
        parsed.selected_choice_ids.add(choice_id)
        choice = choices_by_id.get(choice_id)
        if choice is None:
            continue
        parsed.values.append(choice.answer_value)
        parsed.choice_snapshot.append(
            {
                "source": "choice",
                "choice_id": choice.id,
                "label": choice.label,
                "value": choice.answer_value,
            }
        )
    return parsed


def _validate_answer(
    question: SurveyQuestion,
    parsed: ParsedAnswer,
    errors: dict[int, list[str]],
) -> None:
    question_errors: list[str] = []
    if question.is_required and not parsed.values:
        question_errors.append("This question is required.")

    if question.question_type == QUESTION_TYPE_TEXT and parsed.values:
        value = parsed.values[0]
        if question.render_hint == RENDER_HINT_EMAIL:
            try:
                validate_email(value)
            except ValidationError:
                question_errors.append("Enter a valid email address.")
        elif question.render_hint == RENDER_HINT_DATE and parse_date(value) is None:
            question_errors.append("Enter a valid date.")
        elif question.render_hint == RENDER_HINT_NUMBER:
            try:
                Decimal(value)
            except InvalidOperation:
                question_errors.append("Enter a valid number.")

    if (
        question.question_type == QUESTION_TYPE_SINGLE_CHOICE
        and len(parsed.selected_choice_ids) > 1
    ):
        question_errors.append("Choose only one answer.")

    if question.is_choice_based:
        valid_choice_ids = {choice.id for choice in question.choices.all()}
        invalid_ids = parsed.selected_choice_ids - valid_choice_ids
        if invalid_ids:
            question_errors.append("Choose a valid answer.")
        if parsed.other_selected and not question.allows_other:
            question_errors.append("Other is not allowed for this question.")
        if parsed.other_selected and not parsed.other_value:
            question_errors.append("Enter a value for other.")

    if question_errors:
        errors[question.id] = question_errors


def _visible_question_ids(
    questions: list[SurveyQuestion],
    answers: dict[int, ParsedAnswer],
) -> set[int]:
    questions_by_id = {question.id: question for question in questions}
    condition_map: dict[int, list[SurveyQuestionCondition]] = {
        question.id: list(question.conditions.all()) for question in questions
    }
    visible_cache: dict[int, bool] = {}

    def is_visible(question_id: int, visiting: set[int] | None = None) -> bool:
        if question_id in visible_cache:
            return visible_cache[question_id]
        if visiting is None:
            visiting = set()
        if question_id in visiting:
            visible_cache[question_id] = False
            return False
        visiting.add(question_id)
        conditions = condition_map.get(question_id, [])
        if not conditions:
            visible_cache[question_id] = True
            return True
        parent_id = conditions[0].depends_on_question_id
        if parent_id not in questions_by_id or not is_visible(parent_id, visiting):
            visible_cache[question_id] = False
            return False
        selected_ids = answers.get(parent_id, ParsedAnswer()).selected_choice_ids
        visible_cache[question_id] = any(
            condition.visible_if_choice_id in selected_ids for condition in conditions
        )
        return visible_cache[question_id]

    return {question.id for question in questions if is_visible(question.id)}


def _field_name(question: SurveyQuestion) -> str:
    return f"question_{question.id}"


def _other_field_name(question: SurveyQuestion) -> str:
    return f"question_{question.id}_other"
