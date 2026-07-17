from __future__ import annotations

import json
import re

import pytest
from django.contrib.auth import get_user_model

from surveys.models import Survey, SurveyAnswer, SurveyChoice, SurveyQuestion, SurveyResponse
from surveys.question_types import (
    QUESTION_TYPE_MULTI_CHOICE,
    QUESTION_TYPE_SINGLE_CHOICE,
    QUESTION_TYPE_TEXT,
    RENDER_HINT_CHECKBOXES,
    RENDER_HINT_RADIO,
    RENDER_HINT_SHORT_TEXT,
)
from surveys.services import replace_conditions, submit_survey_response

pytestmark = pytest.mark.django_db


def create_user(email: str = "admin@example.com", is_admin: bool = True):
    return get_user_model().objects.create_user(
        email=email,
        password="test-password-1",
        is_admin=is_admin,
    )


def create_survey(
    name: str = "Arrival Survey",
    slug: str = "arrival-survey",
    is_active: bool = True,
) -> Survey:
    return Survey.objects.create(name=name, slug=slug, is_active=is_active)


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


def json_script_data(body: str, element_id: str) -> object:
    match = re.search(
        rf'<script id="{element_id}" type="application/json">(.*?)</script>',
        body,
    )
    assert match is not None
    return json.loads(match.group(1))


class FakePost:
    def __init__(self, values: dict[str, str]) -> None:
        self.values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        return self.values.get(key, default)

    def getlist(self, key: str) -> list[str]:
        value = self.values.get(key)
        return [value] if value is not None else []


def test_admin_home_and_nav_include_surveys_between_pages_and_menus(client) -> None:
    admin = create_user()
    client.force_login(admin)

    response = client.get("/admin/")
    body = response.content.decode()

    assert response.status_code == 200
    assert body.index("Pages") < body.index("Surveys") < body.index("Menus")
    assert 'href="/admin/surveys/"' in body


def test_surveys_overview_embeds_json_for_client_side_active_filter(client) -> None:
    admin = create_user()
    beta = create_survey(name="Beta", slug="beta", is_active=True)
    create_survey(name="Alpha", slug="alpha", is_active=False)
    beta.responses.create(user=create_user("member@example.com", is_admin=False))
    client.force_login(admin)

    response = client.get("/admin/surveys/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "checked" in body
    assert "Apply" not in body
    assert 'data-fallback-survey-row="beta"' in body
    assert 'data-fallback-survey-row="alpha"' not in body
    assert "View Responses" in body
    assert 'href="/admin/surveys/beta/responses/"' in body
    assert "responses_url" in body
    assert "response_count" in body
    assert 'id="survey-list-data"' in body
    assert 'src="/static/js/admin-surveys.js"' in body
    assert body.index("Alpha") < body.index("Beta")


def test_admin_can_create_survey_and_validation_errors_stay_on_page(client) -> None:
    admin = create_user()
    Survey.objects.create(name="Taken", slug="taken")
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/",
        {
            "action": "create_survey",
            "name": "Arrival",
            "slug": "arrival-survey",
            "description_markdown": "# Arrival",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/surveys/arrival-survey/"
    survey = Survey.objects.get(slug="arrival-survey")
    assert survey.name == "Arrival"
    assert survey.description_markdown == "# Arrival"
    assert survey.is_active is True

    duplicate = client.post(
        "/admin/surveys/",
        {
            "action": "create_survey",
            "name": "Taken",
            "slug": "bad slug",
            "description_markdown": "",
        },
    )
    assert duplicate.status_code == 200
    assert b"Survey with this Name already exists." in duplicate.content
    assert b"Enter a valid" in duplicate.content


def test_survey_edit_updates_details_and_rejects_duplicate_slug(client) -> None:
    admin = create_user()
    Survey.objects.create(name="Other", slug="other")
    survey = create_survey()
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "update_survey",
            "name": "Updated",
            "slug": "updated-survey",
            "description_markdown": "Updated body",
            "is_active": "on",
            "redirect_after_submission_url": "/2026/dashboard/",
        },
    )

    assert response.status_code == 302
    assert response["Location"] == "/admin/surveys/updated-survey/#survey-details"
    survey.refresh_from_db()
    assert survey.name == "Updated"
    assert survey.redirect_after_submission_url == "/2026/dashboard/"

    response = client.post(
        "/admin/surveys/updated-survey/",
        {
            "action": "update_survey",
            "name": "Updated",
            "slug": "other",
            "description_markdown": "Updated body",
            "is_active": "on",
            "redirect_after_submission_url": "/2026/dashboard/",
        },
    )
    assert response.status_code == 200
    assert b"Survey with this Slug already exists." in response.content

    response = client.post(
        "/admin/surveys/updated-survey/",
        {
            "action": "update_survey",
            "name": "Updated",
            "slug": "updated-survey",
            "description_markdown": "Updated body",
            "is_active": "on",
            "redirect_after_submission_url": "https://example.com",
        },
    )
    assert response.status_code == 200
    assert b"Enter an internal path starting with /." in response.content


def test_admin_can_create_questions_with_default_hints_and_question_cards(client) -> None:
    admin = create_user()
    survey = create_survey()
    client.force_login(admin)

    for question_type, expected_hint in [
        (QUESTION_TYPE_TEXT, RENDER_HINT_SHORT_TEXT),
        (QUESTION_TYPE_SINGLE_CHOICE, RENDER_HINT_RADIO),
        (QUESTION_TYPE_MULTI_CHOICE, RENDER_HINT_CHECKBOXES),
    ]:
        response = client.post(
            "/admin/surveys/arrival-survey/",
            {"action": "create_question", "name": question_type, "question_type": question_type},
        )
        question = SurveyQuestion.objects.get(name=question_type)
        assert response.status_code == 302
        assert response["Location"] == f"/admin/surveys/arrival-survey/#question-{question.id}"
        assert question.render_hint == expected_hint

    response = client.get("/admin/surveys/arrival-survey/")
    body = response.content.decode()
    text_question = SurveyQuestion.objects.get(name=QUESTION_TYPE_TEXT)
    assert "Redirect after submission" in body
    assert "Leave blank to show /survey/arrival-survey/complete/ after submission." in body
    assert "Question: text" in body
    assert "Create Choice" in body
    assert 'value="duplicate_question"' in body
    assert (
        f'id="question-{text_question.id}" class="content-card" data-survey-question-card'
        in body
    )
    assert 'class="collapsible-card-toggle"' in body
    assert (
        f'name="action" value="edit_question" form="question-form-{text_question.id}" '
        'class="secondary-button collapsible-card-edit"'
        in body
    )
    assert f'aria-controls="question-{text_question.id}-body"' in body
    assert 'aria-expanded="true"' in body
    assert f'id="question-{text_question.id}-body" data-collapsible-body' in body
    assert "▾" in body
    assert 'src="/static/js/admin-surveys.js"' in body
    assert survey.questions.count() == 3


def test_question_update_edit_and_move_actions_save_dirty_fields(client) -> None:
    admin = create_user()
    survey = create_survey()
    first = create_question(survey, "First", display_order=1)
    second = create_question(survey, "Second", display_order=2)
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "question_move_up",
            "question_id": second.id,
            "name": "Moved Second",
            "description_markdown": "Moved description",
            "render_hint": RENDER_HINT_SHORT_TEXT,
            "is_required": "on",
        },
    )

    assert response.status_code == 302
    second.refresh_from_db()
    first.refresh_from_db()
    assert second.name == "Moved Second"
    assert second.is_required is True
    assert second.display_order < first.display_order

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "edit_question",
            "question_id": second.id,
            "name": "Edited Before Detail",
            "description_markdown": "Moved description",
            "render_hint": RENDER_HINT_SHORT_TEXT,
        },
    )
    assert response.status_code == 302
    assert response["Location"] == f"/admin/surveys/arrival-survey/{second.id}/"
    second.refresh_from_db()
    assert second.name == "Edited Before Detail"


def test_question_duplicate_copies_question_choices_and_conditions_after_source(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    survey = create_survey()
    parent = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=1,
    )
    parent_choice = create_choice(parent, "Green")
    source = create_question(
        survey,
        "Reason",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=2,
    )
    source.description_markdown = "Original description"
    source.is_required = True
    source.allows_other = True
    source.other_label = "Something else"
    source.save(
        update_fields=[
            "description_markdown",
            "is_required",
            "allows_other",
            "other_label",
            "updated_at",
        ]
    )
    SurveyChoice.objects.create(question=source, label="Yes", value="yes", display_order=1)
    SurveyChoice.objects.create(question=source, label="No", value="no", display_order=2)
    replace_conditions(source, parent, [parent_choice])
    later = create_question(survey, "Later", display_order=3)
    response = SurveyResponse.objects.create(survey=survey, user=member)
    SurveyAnswer.objects.create(
        response=response,
        question=source,
        question_id_snapshot=source.id,
        question_name_snapshot=source.name,
        question_type_snapshot=source.question_type,
        render_hint_snapshot=source.render_hint,
        value='["Saved"]',
    )
    client.force_login(admin)

    duplicate_response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "duplicate_question",
            "question_id": source.id,
            "name": "Reason updated",
            "description_markdown": "Updated description",
            "render_hint": RENDER_HINT_RADIO,
            "is_required": "on",
            "allows_other": "on",
            "other_label": "A different answer",
        },
    )

    source.refresh_from_db()
    duplicate = SurveyQuestion.objects.get(name="Reason updated copy")
    later.refresh_from_db()
    assert duplicate_response.status_code == 302
    assert duplicate_response["Location"] == (
        f"/admin/surveys/arrival-survey/#question-{duplicate.id}"
    )
    assert source.name == "Reason updated"
    assert duplicate.description_markdown == "Updated description"
    assert duplicate.question_type == source.question_type
    assert duplicate.render_hint == source.render_hint
    assert duplicate.is_required is True
    assert duplicate.allows_other is True
    assert duplicate.other_label == "A different answer"
    ordered_names = list(
        survey.questions.order_by("display_order", "id").values_list("name", flat=True)
    )
    assert ordered_names == [
        "Color",
        "Reason updated",
        "Reason updated copy",
        "Later",
    ]
    assert list(
        survey.questions.order_by("display_order", "id").values_list("display_order", flat=True)
    ) == [1, 2, 3, 4]
    assert later.display_order == 4
    assert list(
        duplicate.choices.order_by("display_order", "id").values_list(
            "label",
            "value",
            "display_order",
        )
    ) == [("Yes", "yes", 1), ("No", "no", 2)]
    assert list(
        duplicate.conditions.values_list("depends_on_question_id", "visible_if_choice_id")
    ) == [(parent.id, parent_choice.id)]
    assert SurveyAnswer.objects.filter(question=source).count() == 1
    assert not SurveyAnswer.objects.filter(question=duplicate).exists()


def test_choice_create_update_move_delete_and_other_options(client) -> None:
    admin = create_user()
    survey = create_survey()
    question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "create_choice",
            "question_id": question.id,
            "name": "Updated Color",
            "description_markdown": "Pick one.",
            "render_hint": RENDER_HINT_RADIO,
            "allows_other": "on",
            "other_label": "Something else",
            "label": "Green",
            "value": "green",
        },
    )
    choice = SurveyChoice.objects.get()
    assert response.status_code == 302
    assert choice.label == "Green"
    question.refresh_from_db()
    assert question.name == "Updated Color"
    assert question.description_markdown == "Pick one."
    assert question.allows_other is True
    assert question.other_label == "Something else"

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {"action": "update_choice", "choice_id": choice.id, "label": "Pink", "value": "pink"},
    )
    assert response.status_code == 302
    choice.refresh_from_db()
    assert choice.label == "Pink"

    second = create_choice(question, "Blue", display_order=2)
    response = client.post(
        "/admin/surveys/arrival-survey/",
        {"action": "choice_move_up", "choice_id": second.id},
    )
    assert response.status_code == 302
    assert list(question.choices.values_list("label", flat=True)) == ["Blue", "Pink"]

    response = client.get("/admin/surveys/arrival-survey/")
    body = response.content.decode()
    row_start = body.index(f'id="choice-form-{choice.id}"')
    choice_row = body[row_start : body.index("</tr>", row_start)]
    assert "<th>Label</th>" in body
    assert "<th>Value</th>" in body
    assert "<th>Update</th>" in body
    assert "Label And Value" not in body
    assert f'form="choice-form-{choice.id}"' in choice_row
    assert f'id="id_choice_{choice.id}_label"' in choice_row
    assert f'id="id_choice_{choice.id}_value"' in choice_row
    assert 'aria-label="Choice label"' in choice_row
    assert 'aria-label="Choice value"' in choice_row
    assert "<label" not in choice_row

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "update_question",
            "question_id": question.id,
            "name": "Color",
            "description_markdown": "",
            "render_hint": RENDER_HINT_RADIO,
            "allows_other": "on",
            "other_label": "Something else",
        },
    )
    assert response.status_code == 302
    question.refresh_from_db()
    assert question.allows_other is True
    assert question.other_label == "Something else"

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {"action": "delete_choice", "choice_id": second.id},
    )
    assert response.status_code == 302
    assert not SurveyChoice.objects.filter(pk=second.pk).exists()


def test_question_detail_renders_choices_for_choice_questions_only(client) -> None:
    admin = create_user()
    survey = create_survey()
    choice_question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
    )
    choice = create_choice(choice_question, "Green")
    text_question = create_question(survey, "Name", display_order=2)
    client.force_login(admin)

    response = client.get(f"/admin/surveys/arrival-survey/{choice_question.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'id="choices"' in body
    assert "Create Choice" in body
    assert "<th>Label</th>" in body
    assert "<th>Value</th>" in body
    assert f'id="choice-form-{choice.id}"' in body
    assert f'formaction="/admin/surveys/arrival-survey/{choice_question.id}/#choices"' in body

    response = client.get(f"/admin/surveys/arrival-survey/{text_question.id}/")
    body = response.content.decode()

    assert response.status_code == 200
    assert 'id="choices"' not in body
    assert "Create Choice" not in body


def test_question_detail_choice_create_update_move_delete(client) -> None:
    admin = create_user()
    survey = create_survey()
    question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
    )
    client.force_login(admin)

    response = client.post(
        f"/admin/surveys/arrival-survey/{question.id}/",
        {
            "action": "create_choice",
            "name": "Updated Color",
            "description_markdown": "Pick one.",
            "render_hint": RENDER_HINT_RADIO,
            "label": "Green",
            "value": "green",
        },
    )

    choice = SurveyChoice.objects.get()
    assert response.status_code == 302
    assert response["Location"] == f"/admin/surveys/arrival-survey/{question.id}/#choices"
    assert choice.label == "Green"
    assert choice.display_order == 1
    question.refresh_from_db()
    assert question.name == "Updated Color"
    assert question.description_markdown == "Pick one."

    response = client.post(
        f"/admin/surveys/arrival-survey/{question.id}/",
        {"action": "update_choice", "choice_id": choice.id, "label": "Pink", "value": "pink"},
    )
    assert response.status_code == 302
    assert response["Location"] == f"/admin/surveys/arrival-survey/{question.id}/#choices"
    choice.refresh_from_db()
    assert choice.label == "Pink"

    second = create_choice(question, "Blue", display_order=2)
    response = client.post(
        f"/admin/surveys/arrival-survey/{question.id}/",
        {"action": "choice_move_up", "choice_id": second.id},
    )
    assert response.status_code == 302
    assert list(question.choices.values_list("label", flat=True)) == ["Blue", "Pink"]

    response = client.post(
        f"/admin/surveys/arrival-survey/{question.id}/",
        {"action": "delete_choice", "choice_id": second.id},
    )
    assert response.status_code == 302
    assert not SurveyChoice.objects.filter(pk=second.pk).exists()


def test_create_choice_does_not_create_choice_when_question_update_is_invalid(client) -> None:
    admin = create_user()
    survey = create_survey()
    question = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
    )
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {
            "action": "create_choice",
            "question_id": question.id,
            "name": "",
            "description_markdown": "Dirty text",
            "render_hint": RENDER_HINT_RADIO,
            "label": "Green",
            "value": "green",
        },
    )

    assert response.status_code == 200
    assert b"This field is required." in response.content
    assert SurveyChoice.objects.count() == 0
    question.refresh_from_db()
    assert question.name == "Color"
    assert question.description_markdown == ""


def test_choice_delete_used_by_condition_is_rejected(client) -> None:
    admin = create_user()
    survey = create_survey()
    parent = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
    )
    child = create_question(survey, "Why", display_order=2)
    choice = create_choice(parent, "Green")
    replace_conditions(child, parent, [choice])
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {"action": "delete_choice", "choice_id": choice.id},
        follow=True,
    )

    assert response.status_code == 200
    assert SurveyChoice.objects.filter(pk=choice.pk).exists()
    assert b"Choice is used by a condition" in response.content


def test_question_detail_caches_condition_choices_for_selected_parent(client) -> None:
    admin = create_user()
    survey = create_survey()
    parent = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=1,
    )
    green = create_choice(parent, "Green")
    blue = create_choice(parent, "Blue", display_order=2)
    child = create_question(survey, "Why", display_order=2)
    replace_conditions(child, parent, [blue])
    client.force_login(admin)

    response = client.get(f"/admin/surveys/arrival-survey/{child.id}/")
    body = response.content.decode()
    cache = json_script_data(body, "condition-choice-cache")
    list_start = body.index('data-condition-choice-list')
    choice_list = body[list_start : body.index("</div>", list_start)]

    assert response.status_code == 200
    assert cache[str(parent.id)] == [
        {"id": str(green.id), "label": "Green"},
        {"id": str(blue.id), "label": "Blue"},
    ]
    assert 'data-condition-parent=""' in body
    assert 'data-choice-name="visible_if_choices"' in body
    assert 'src="/static/js/admin-surveys.js"' in body
    assert 'class="condition-choice-option"' in choice_list
    assert choice_list.index('type="checkbox"') < choice_list.index("Green")
    assert f'value="{blue.id}"' in choice_list
    assert "checked" in choice_list[choice_list.index(f'value="{blue.id}"') :]


def test_question_detail_conditions_create_replace_clear_and_reject_cycles(client) -> None:
    admin = create_user()
    survey = create_survey()
    parent = create_question(
        survey,
        "Color",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=1,
    )
    child = create_question(
        survey,
        "Why",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=2,
    )
    parent_choice = create_choice(parent, "Green")
    child_choice = create_choice(child, "Because")
    replace_conditions(parent, child, [child_choice])
    client.force_login(admin)

    response = client.post(
        f"/admin/surveys/arrival-survey/{child.id}/",
        {
            "action": "update_conditions",
            "has_conditions": "on",
            "depends_on_question": parent.id,
            "visible_if_choices": [parent_choice.id],
        },
    )
    assert response.status_code == 200
    assert b"circular dependency" in response.content
    assert child.conditions.count() == 0

    response = client.post(
        f"/admin/surveys/arrival-survey/{parent.id}/",
        {"action": "update_conditions"},
    )
    assert response.status_code == 302
    assert parent.conditions.count() == 0

    response = client.post(
        f"/admin/surveys/arrival-survey/{child.id}/",
        {
            "action": "update_conditions",
            "has_conditions": "on",
            "depends_on_question": parent.id,
            "visible_if_choices": [parent_choice.id],
        },
    )
    assert response.status_code == 302
    assert child.conditions.count() == 1

    response = client.post(
        f"/admin/surveys/arrival-survey/{child.id}/",
        {"action": "update_conditions"},
    )
    assert response.status_code == 302
    assert child.conditions.count() == 0


def test_question_detail_preserves_late_parent_and_delete_preserves_answers(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    survey = create_survey()
    parent = create_question(
        survey,
        "Later Parent",
        QUESTION_TYPE_SINGLE_CHOICE,
        RENDER_HINT_RADIO,
        display_order=2,
    )
    child = create_question(survey, "Earlier Child", display_order=1)
    choice = create_choice(parent, "Yes")
    replace_conditions(child, parent, [choice])
    submit_survey_response(survey, member, FakePost({f"question_{child.id}": "Saved"}))
    client.force_login(admin)

    response = client.get(f"/admin/surveys/arrival-survey/{child.id}/")
    assert response.status_code == 200
    assert b"appears later in the survey" in response.content

    response = client.post(
        f"/admin/surveys/arrival-survey/{child.id}/",
        {"action": "delete_question"},
    )
    assert response.status_code == 302
    answer = SurveyAnswer.objects.get(question__isnull=True)
    assert answer.question is None
    assert answer.question_name_snapshot == "Earlier Child"


def test_survey_delete_requires_confirmation_when_answers_exist(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    survey = create_survey()
    question = create_question(survey, "Name")
    submit_survey_response(survey, member, FakePost({f"question_{question.id}": "Alice"}))
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {"action": "delete_survey", "confirm": "wrong"},
        follow=True,
    )
    assert response.status_code == 200
    assert Survey.objects.filter(pk=survey.pk).exists()
    assert b"Type delete to confirm" in response.content

    response = client.post(
        "/admin/surveys/arrival-survey/",
        {"action": "delete_survey", "confirm": "delete"},
    )
    assert response.status_code == 302
    assert response["Location"] == "/admin/surveys/"
    assert not Survey.objects.filter(pk=survey.pk).exists()
    assert SurveyAnswer.objects.count() == 0


def test_survey_responses_page_renders_answer_matrix(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    member.first_name = "Ada"
    member.last_name = "Lovelace"
    member.save(update_fields=["first_name", "last_name", "updated_at"])
    survey = create_survey()
    question = create_question(survey, "Bio")
    create_question(survey, "Missing", display_order=2)
    deleted_question = create_question(survey, "Deleted", display_order=3)
    submit_survey_response(
        survey,
        member,
        FakePost({f"question_{question.id}": 'Hello, "camp"\nthere'}),
    )
    survey_response = SurveyResponse.objects.get(survey=survey, user=member)
    deleted_question.delete()
    client.force_login(admin)

    response = client.get("/admin/surveys/arrival-survey/responses/")
    body = response.content.decode()

    assert response.status_code == 200
    assert "Ada Lovelace" in body
    assert "member@example.com" in body
    assert "Bio" in body
    assert "Missing" in body
    assert "Deleted" not in body
    assert 'Hello, &quot;camp&quot;' in body
    assert "<th>Actions</th>" in body
    assert 'value="delete_response"' in body
    assert f'value="{survey_response.id}"' in body
    assert 'class="danger-button"' in body
    assert 'href="/admin/surveys/arrival-survey/responses.csv"' in body


def test_admin_can_delete_survey_response_and_answers(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    survey = create_survey()
    question = create_question(survey, "Bio")
    submit_survey_response(survey, member, FakePost({f"question_{question.id}": "Hello"}))
    survey_response = SurveyResponse.objects.get(survey=survey, user=member)
    assert SurveyAnswer.objects.filter(response=survey_response).count() == 1
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/responses/",
        {"action": "delete_response", "response_id": str(survey_response.id)},
        follow=True,
    )

    assert response.status_code == 200
    assert b"Deleted survey response from member@example.com." in response.content
    assert not SurveyResponse.objects.filter(pk=survey_response.pk).exists()
    assert SurveyAnswer.objects.count() == 0


def test_survey_response_delete_is_scoped_to_current_survey(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    current_survey = create_survey()
    other_survey = create_survey(name="Other Survey", slug="other-survey")
    other_question = create_question(other_survey, "Bio")
    submit_survey_response(
        other_survey,
        member,
        FakePost({f"question_{other_question.id}": "Hello"}),
    )
    other_response = SurveyResponse.objects.get(survey=other_survey, user=member)
    client.force_login(admin)

    response = client.post(
        "/admin/surveys/arrival-survey/responses/",
        {"action": "delete_response", "response_id": str(other_response.id)},
    )

    assert response.status_code == 404
    assert Survey.objects.filter(pk=current_survey.pk).exists()
    assert SurveyResponse.objects.filter(pk=other_response.pk).exists()
    assert SurveyAnswer.objects.filter(response=other_response).count() == 1


def test_non_admin_cannot_delete_survey_response(client) -> None:
    member = create_user("member@example.com", is_admin=False)
    survey = create_survey()
    question = create_question(survey, "Bio")
    submit_survey_response(survey, member, FakePost({f"question_{question.id}": "Hello"}))
    survey_response = SurveyResponse.objects.get(survey=survey, user=member)
    client.force_login(member)

    response = client.post(
        "/admin/surveys/arrival-survey/responses/",
        {"action": "delete_response", "response_id": str(survey_response.id)},
    )

    assert response.status_code == 403
    assert SurveyResponse.objects.filter(pk=survey_response.pk).exists()
    assert SurveyAnswer.objects.filter(response=survey_response).count() == 1


def test_survey_export_outputs_response_matrix_and_escaped_values(client) -> None:
    admin = create_user()
    member = create_user("member@example.com", is_admin=False)
    member.first_name = "Ada"
    member.last_name = "Lovelace"
    member.save(update_fields=["first_name", "last_name", "updated_at"])
    survey = create_survey()
    question = create_question(survey, "Bio")
    deleted_question = create_question(survey, "Deleted", display_order=2)
    submit_survey_response(
        survey,
        member,
        FakePost({f"question_{question.id}": 'Hello, "camp"\nthere'}),
    )
    deleted_question.delete()
    client.force_login(admin)

    response = client.get("/admin/surveys/arrival-survey/responses.csv")
    body = response.content.decode()

    assert response.status_code == 200
    assert response["Content-Type"] == "text/csv"
    assert "Name,Email,Bio" in body
    assert "Deleted" not in body
    assert "Ada Lovelace,member@example.com" in body
    assert '"Hello, ""camp""\nthere"' in body


def test_survey_export_with_no_responses_still_outputs_headers(client) -> None:
    admin = create_user()
    survey = create_survey()
    create_question(survey, "Bio")
    client.force_login(admin)

    response = client.get("/admin/surveys/arrival-survey/responses.csv")

    assert response.status_code == 200
    assert response.content.decode().strip() == "Name,Email,Bio"
