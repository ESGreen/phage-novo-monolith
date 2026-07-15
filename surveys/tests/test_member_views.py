from __future__ import annotations

import json

import pytest
from django.contrib.auth import get_user_model

from surveys.models import Survey, SurveyAnswer, SurveyChoice, SurveyQuestion, SurveyResponse
from surveys.question_types import (
    QUESTION_TYPE_MULTI_CHOICE,
    QUESTION_TYPE_SINGLE_CHOICE,
    QUESTION_TYPE_TEXT,
    RENDER_HINT_CHECKBOXES,
    RENDER_HINT_DATE,
    RENDER_HINT_EMAIL,
    RENDER_HINT_LONG_TEXT,
    RENDER_HINT_NUMBER,
    RENDER_HINT_RADIO,
    RENDER_HINT_SELECT,
    RENDER_HINT_SHORT_TEXT,
)
from surveys.services import replace_conditions, submit_survey_response

pytestmark = pytest.mark.django_db


def create_user(email: str = "member@example.com"):
    return get_user_model().objects.create_user(email=email, password="test-password-1")


def create_survey(active: bool = True) -> Survey:
    return Survey.objects.create(
        name="Arrival Survey",
        slug="arrival-survey",
        description_markdown="# Welcome\n\n<script>bad()</script>",
        is_active=active,
    )


def create_question(
    survey: Survey,
    name: str,
    question_type: str = QUESTION_TYPE_TEXT,
    render_hint: str = RENDER_HINT_SHORT_TEXT,
    display_order: int = 1,
    required: bool = False,
    allows_other: bool = False,
) -> SurveyQuestion:
    return SurveyQuestion.objects.create(
        survey=survey,
        name=name,
        question_type=question_type,
        render_hint=render_hint,
        display_order=display_order,
        is_required=required,
        allows_other=allows_other,
    )


def create_choice(question: SurveyQuestion, label: str, display_order: int = 1) -> SurveyChoice:
    return SurveyChoice.objects.create(question=question, label=label, display_order=display_order)


class FakePost:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)

    def getlist(self, key: str) -> list[str]:
        value = self.values.get(key)
        return [value] if value is not None else []


def test_survey_requires_login(client) -> None:
    create_survey()

    response = client.get("/survey/arrival-survey/")

    assert response.status_code == 302
    assert response["Location"] == "/login/?next=/survey/arrival-survey/"


def test_unknown_or_inactive_survey_returns_404_for_member(client) -> None:
    user = create_user()
    client.force_login(user)
    create_survey(active=False)

    assert client.get("/survey/missing/").status_code == 404
    assert client.get("/survey/arrival-survey/").status_code == 404


def test_active_survey_renders_description_questions_and_controls(client) -> None:
    user = create_user()
    survey = create_survey()
    name = create_question(survey, "Name", render_hint=RENDER_HINT_SHORT_TEXT)
    bio = create_question(survey, "Bio", render_hint=RENDER_HINT_LONG_TEXT, display_order=2)
    create_question(survey, "Email", render_hint=RENDER_HINT_EMAIL, display_order=3)
    create_question(survey, "Date", render_hint=RENDER_HINT_DATE, display_order=4)
    create_question(survey, "Number", render_hint=RENDER_HINT_NUMBER, display_order=5)
    radio = create_question(
        survey,
        "Radio",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=6,
        allows_other=True,
    )
    select = create_question(
        survey,
        "Select",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_SELECT,
        display_order=7,
    )
    multi = create_question(
        survey,
        "Multi",
        QUESTION_TYPE_MULTI_CHOICE,
        RENDER_HINT_CHECKBOXES,
        display_order=8,
    )
    create_choice(radio, "Yes")
    create_choice(select, "Maybe")
    create_choice(multi, "A")
    client.force_login(user)

    response = client.get("/survey/arrival-survey/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Arrival Survey" in body
    assert "&lt;script&gt;" in body
    assert "<script>" not in body
    assert body.index("Name") < body.index("Bio") < body.index("Email")
    assert 'type="email"' in body
    assert 'type="date"' in body
    assert "textarea" in body
    assert "data-survey-question-card" in body
    assert "__other__" in body
    assert ">Answer</label>" not in body
    assert "<legend>Answer</legend>" not in body
    assert "<fieldset" not in body
    assert f'aria-labelledby="question-{name.id}-label"' in body
    assert f'aria-labelledby="question-{bio.id}-label"' in body
    other_start = body.index('class="survey-other-option"')
    other_block = body[other_start : body.index("</div>", other_start)]
    assert other_block.index("__other__") < other_block.index(f'id="id_question_{radio.id}_other"')
    assert f'id="id_question_{radio.id}_other" class="survey-other-text"' in other_block
    assert f'<label for="id_question_{radio.id}_other">' not in body


def test_submit_creates_response_then_resubmits_existing_response(client) -> None:
    user = create_user()
    survey = create_survey()
    question = create_question(survey, "Name")
    client.force_login(user)

    response = client.post("/survey/arrival-survey/", {f"question_{question.id}": "Alice"})

    assert response.status_code == 302
    assert response["Location"] == "/survey/arrival-survey/complete/"
    assert SurveyResponse.objects.count() == 1
    assert json.loads(SurveyAnswer.objects.get().value) == ["Alice"]

    response = client.post("/survey/arrival-survey/", {f"question_{question.id}": "Bob"})

    assert response.status_code == 302
    assert SurveyResponse.objects.count() == 1
    assert json.loads(SurveyAnswer.objects.get().value) == ["Bob"]


def test_submit_redirects_to_configured_internal_url(client) -> None:
    user = create_user()
    survey = create_survey()
    survey.redirect_after_submission_url = "/2026/dashboard/"
    survey.save(update_fields=["redirect_after_submission_url", "updated_at"])
    question = create_question(survey, "Name")
    client.force_login(user)

    response = client.post("/survey/arrival-survey/", {f"question_{question.id}": "Alice"})

    assert response.status_code == 302
    assert response["Location"] == "/2026/dashboard/"


def test_completion_page_loads_and_links_back(client) -> None:
    user = create_user()
    create_survey()
    client.force_login(user)

    response = client.get("/survey/arrival-survey/complete/")

    assert response.status_code == 200
    assert b"Survey Complete" in response.content
    assert b'href="/survey/arrival-survey/"' in response.content


def test_existing_response_prepopulates_current_answers_and_other(client) -> None:
    user = create_user()
    survey = create_survey()
    text = create_question(survey, "Name")
    choice_question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=2,
        allows_other=True,
    )
    choice = create_choice(choice_question, "Green")
    client.force_login(user)
    client.post(
        "/survey/arrival-survey/",
        {
            f"question_{text.id}": "Alice",
            f"question_{choice_question.id}": str(choice.id),
        },
    )

    response = client.get("/survey/arrival-survey/")
    body = response.content.decode()

    assert 'value="Alice"' in body
    assert f'value="{choice.id}" data-choice-input' in body
    assert "checked" in body


def test_member_submission_validates_required_visibility_and_clears_hidden_answer(client) -> None:
    user = create_user()
    survey = create_survey()
    parent = create_question(
        survey,
        "Years",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=1,
    )
    zero = create_choice(parent, "0")
    one = create_choice(parent, "1", display_order=2)
    child = create_question(survey, "Sponsor", display_order=2, required=True)
    replace_conditions(child, parent, [zero])
    client.force_login(user)

    response = client.post("/survey/arrival-survey/", {f"question_{parent.id}": str(zero.id)})
    assert response.status_code == 200
    assert b"This question is required." in response.content

    response = client.post(
        "/survey/arrival-survey/",
        {f"question_{parent.id}": str(one.id), f"question_{child.id}": "Stale"},
    )
    assert response.status_code == 302
    child_answer = SurveyAnswer.objects.get(question=child)
    assert json.loads(child_answer.value) == []


def test_submission_validates_email_date_number_choice_and_other(client) -> None:
    user = create_user()
    survey = create_survey()
    email = create_question(survey, "Email", render_hint=RENDER_HINT_EMAIL, display_order=1)
    date = create_question(survey, "Date", render_hint=RENDER_HINT_DATE, display_order=2)
    number = create_question(survey, "Number", render_hint=RENDER_HINT_NUMBER, display_order=3)
    choice_question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=4,
        required=True,
        allows_other=True,
    )
    client.force_login(user)

    response = client.post(
        "/survey/arrival-survey/",
        {
            f"question_{email.id}": "not-email",
            f"question_{date.id}": "bad-date",
            f"question_{number.id}": "abc",
            f"question_{choice_question.id}": "__other__",
        },
    )

    body = response.content.decode()
    assert "Enter a valid email address." in body
    assert "Enter a valid date." in body
    assert "Enter a valid number." in body
    assert "Enter a value for other." in body


def test_multichoice_condition_triggers_when_any_choice_matches(client) -> None:
    user = create_user()
    survey = create_survey()
    parent = create_question(
        survey,
        "Foods",
        QUESTION_TYPE_MULTI_CHOICE,
        RENDER_HINT_CHECKBOXES,
    )
    apples = create_choice(parent, "Apples")
    pears = create_choice(parent, "Pears", display_order=2)
    child = create_question(survey, "Why pears", display_order=2, required=True)
    replace_conditions(child, parent, [pears])
    client.force_login(user)

    response = client.post(
        "/survey/arrival-survey/",
        {f"question_{parent.id}": [str(apples.id), str(pears.id)]},
    )

    assert response.status_code == 200
    assert b"This question is required." in response.content


def test_deleted_historical_choice_is_not_forced_into_current_form(client) -> None:
    user = create_user()
    survey = create_survey()
    question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
    )
    choice = create_choice(question, "Green")
    submit_survey_response(survey, user, FakePost({f"question_{question.id}": str(choice.id)}))
    choice.delete()
    client.force_login(user)

    response = client.get("/survey/arrival-survey/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Green" not in body
    assert "Arrival Survey" in body
