from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.http import QueryDict

from surveys.models import Survey, SurveyAnswer, SurveyChoice, SurveyQuestion, SurveyResponse
from surveys.question_types import (
    QUESTION_TYPE_MULTI_CHOICE,
    QUESTION_TYPE_SINGLE_CHOICE,
    QUESTION_TYPE_TEXT,
    RENDER_HINT_CHECKBOXES,
    RENDER_HINT_RADIO,
    RENDER_HINT_SHORT_TEXT,
)
from surveys.services import (
    answer_json,
    move_choice,
    move_question,
    next_choice_order,
    next_question_order,
    replace_conditions,
    submit_survey_response,
    validate_condition_graph,
)

pytestmark = pytest.mark.django_db


def create_user(email: str = "member@example.com"):
    return get_user_model().objects.create_user(email=email, password="test-password-1")


def create_survey(name: str = "Arrival Survey", slug: str = "arrival-survey") -> Survey:
    return Survey.objects.create(name=name, slug=slug, description_markdown="# Hello")


def create_question(
    survey: Survey,
    name: str,
    question_type: str = QUESTION_TYPE_TEXT,
    render_hint: str = RENDER_HINT_SHORT_TEXT,
    display_order: int = 1,
) -> SurveyQuestion:
    return SurveyQuestion.objects.create(
        survey=survey,
        name=name,
        question_type=question_type,
        render_hint=render_hint,
        display_order=display_order,
    )


def create_choice(question: SurveyQuestion, label: str, display_order: int = 1) -> SurveyChoice:
    return SurveyChoice.objects.create(question=question, label=label, display_order=display_order)


def post_data(values: dict[str, str | list[str]]) -> QueryDict:
    data = QueryDict(mutable=True)
    for key, value in values.items():
        if isinstance(value, list):
            for item in value:
                data.appendlist(key, item)
        else:
            data[key] = value
    return data


def test_survey_defaults_and_sorting() -> None:
    second = Survey.objects.create(name="Beta", slug="beta")
    first = Survey.objects.create(name="Alpha", slug="alpha")

    assert first.is_active is True
    assert list(Survey.objects.all()) == [first, second]


def test_survey_name_and_slug_are_unique() -> None:
    create_survey()

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Survey.objects.create(name="Arrival Survey", slug="other")
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Survey.objects.create(name="Other", slug="arrival-survey")


def test_invalid_slug_is_rejected_by_full_clean() -> None:
    survey = Survey(name="Bad", slug="bad slug")

    with pytest.raises(ValidationError):
        survey.full_clean()


def test_question_render_hint_matrix_is_validated() -> None:
    survey = create_survey()
    question = create_question(
        survey,
        "Name",
        question_type=QUESTION_TYPE_TEXT,
        render_hint=RENDER_HINT_CHECKBOXES,
    )

    with pytest.raises(ValidationError):
        question.full_clean()


def test_allows_other_is_only_valid_for_choice_questions() -> None:
    survey = create_survey()
    question = create_question(survey, "Name")
    question.allows_other = True

    with pytest.raises(ValidationError):
        question.full_clean()


def test_question_and_choice_order_helpers_and_moves() -> None:
    survey = create_survey()
    first = create_question(survey, "First", display_order=1)
    second = create_question(survey, "Second", display_order=2)
    create_choice(first, "One", display_order=1)
    choice_two = create_choice(first, "Two", display_order=2)

    assert next_question_order(survey) == 3
    assert next_choice_order(first) == 3

    move_question(second, "up")
    move_choice(choice_two, "up")

    assert list(survey.questions.values_list("name", flat=True)) == ["Second", "First"]
    assert list(first.choices.values_list("label", flat=True)) == ["Two", "One"]
    assert SurveyQuestion.objects.get(pk=second.pk).display_order == 1
    assert SurveyChoice.objects.get(pk=choice_two.pk).display_order == 1


def test_choice_value_falls_back_to_label() -> None:
    survey = create_survey()
    question = create_question(
        survey,
        "Color",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
    )
    choice = create_choice(question, "Green")

    assert choice.answer_value == "Green"


def test_conditions_validate_same_survey_choice_question_and_choice() -> None:
    survey = create_survey()
    other_survey = create_survey(name="Other", slug="other")
    text_question = create_question(survey, "Name", display_order=1)
    parent = create_question(
        survey,
        "Color",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
        display_order=2,
    )
    child = create_question(survey, "Why", display_order=3)
    other_parent = create_question(
        other_survey,
        "Other color",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
    )
    choice = create_choice(parent, "Green")
    other_choice = create_choice(other_parent, "Blue")

    with pytest.raises(ValidationError):
        replace_conditions(child, text_question, [choice])
    with pytest.raises(ValidationError):
        replace_conditions(child, other_parent, [other_choice])
    with pytest.raises(ValidationError):
        replace_conditions(child, parent, [other_choice])


def test_condition_cycle_detection_rejects_self_two_and_three_question_cycles() -> None:
    survey = create_survey()
    q1 = create_question(
        survey,
        "One",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
        display_order=1,
    )
    q2 = create_question(
        survey,
        "Two",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
        display_order=2,
    )
    q3 = create_question(
        survey,
        "Three",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
        display_order=3,
    )
    c1 = create_choice(q1, "A")
    c2 = create_choice(q2, "B")
    c3 = create_choice(q3, "C")

    with pytest.raises(ValidationError):
        replace_conditions(q1, q1, [c1])

    replace_conditions(q2, q1, [c1])
    with pytest.raises(ValidationError):
        replace_conditions(q1, q2, [c2])

    replace_conditions(q3, q2, [c2])
    with pytest.raises(ValidationError):
        replace_conditions(q1, q3, [c3])


def test_valid_condition_chains_branches_and_multiple_choices_are_allowed() -> None:
    survey = create_survey()
    parent = create_question(
        survey,
        "Parent",
        question_type=QUESTION_TYPE_MULTI_CHOICE,
        render_hint=RENDER_HINT_CHECKBOXES,
    )
    child = create_question(survey, "Child", display_order=2)
    sibling = create_question(survey, "Sibling", display_order=3)
    choice_one = create_choice(parent, "One")
    choice_two = create_choice(parent, "Two", display_order=2)

    replace_conditions(child, parent, [choice_one, choice_two])
    replace_conditions(sibling, parent, [choice_one])

    validate_condition_graph(survey)
    assert child.conditions.count() == 2
    assert sibling.conditions.count() == 1


def test_one_response_per_user_survey() -> None:
    user = create_user()
    survey = create_survey()
    SurveyResponse.objects.create(user=user, survey=survey)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            SurveyResponse.objects.create(user=user, survey=survey)

    SurveyResponse.objects.create(user=create_user("other@example.com"), survey=survey)
    SurveyResponse.objects.create(user=user, survey=create_survey(name="Other", slug="other"))


def test_answer_json_serializes_arrays_of_strings() -> None:
    assert answer_json(["green", "pink"]) == '["green", "pink"]'


def test_submit_snapshots_answers_and_delete_question_preserves_history() -> None:
    user = create_user()
    survey = create_survey()
    question = create_question(survey, "Name")
    result = submit_survey_response(survey, user, post_data({f"question_{question.id}": "Alice"}))

    assert result.success is True
    answer = SurveyAnswer.objects.get()
    assert json.loads(answer.value) == ["Alice"]
    assert answer.question_id_snapshot == question.id
    assert answer.question_name_snapshot == "Name"

    question.delete()
    answer.refresh_from_db()
    assert answer.question is None
    assert answer.question_name_snapshot == "Name"


def test_choice_snapshot_survives_choice_delete_but_condition_blocks_delete() -> None:
    user = create_user()
    survey = create_survey()
    parent = create_question(
        survey,
        "Color",
        question_type=QUESTION_TYPE_SINGLE_CHOICE,
        render_hint=RENDER_HINT_RADIO,
    )
    child = create_question(survey, "Why", display_order=2)
    choice = create_choice(parent, "Green")
    result = submit_survey_response(
        survey,
        user,
        post_data({f"question_{parent.id}": str(choice.id)}),
    )
    assert result.success is True

    replace_conditions(child, parent, [choice])
    with pytest.raises(ValidationError):
        choice.delete()

    child.conditions.all().delete()
    choice.delete()
    answer = SurveyAnswer.objects.get(question=parent)
    assert json.loads(answer.choice_snapshot)[0]["label"] == "Green"


def test_deleting_survey_cascades_everything() -> None:
    user = create_user()
    survey = create_survey()
    question = create_question(survey, "Name")
    submit_survey_response(survey, user, post_data({f"question_{question.id}": "Alice"}))

    survey.delete()

    assert Survey.objects.count() == 0
    assert SurveyQuestion.objects.count() == 0
    assert SurveyResponse.objects.count() == 0
    assert SurveyAnswer.objects.count() == 0
