import pytest

from reimbursements.models import Reimbursement
from reimbursements.reports import (
    expenses_by_category,
    neutralize_spreadsheet_text,
    paid_expenses_by_person,
)
from reimbursements.services import mark_reimbursement_paid

from .helpers import (
    add_required_data,
    create_camp_year,
    create_draft,
    create_submitted,
    create_user,
)

pytestmark = pytest.mark.django_db


def test_expenses_by_category_separates_submitted_paid_and_excludes_draft():
    year = create_camp_year()
    submitted = create_submitted(camp_year=year)
    paid = create_submitted(create_user("paid@example.com"), year)
    admin = create_user("admin@example.com", admin=True)
    mark_reimbursement_paid(reimbursement=paid, administrator=admin, payer_notes="")
    draft = add_required_data(create_draft(create_user("draft@example.com"), year))

    rows = expenses_by_category(camp_year=year)
    assert len(rows) == 1
    assert rows[0].submitted_amount_cents == submitted.total_amount_cents
    assert rows[0].paid_amount_cents == paid.total_amount_cents
    assert draft.status == Reimbursement.Status.DRAFT


def test_paid_expenses_group_by_person_and_category():
    year = create_camp_year()
    paid = create_submitted(camp_year=year)
    mark_reimbursement_paid(
        reimbursement=paid,
        administrator=create_user("admin@example.com", admin=True),
        payer_notes="",
    )
    rows = paid_expenses_by_person(camp_year=year)
    assert len(rows) == 1
    assert rows[0]["amount_cents"] == 1250


@pytest.mark.parametrize("value", ["=SUM(A1)", "+cmd", " -1", "\t@evil"])
def test_spreadsheet_text_is_neutralized(value):
    assert neutralize_spreadsheet_text(value).startswith("'")


def test_csv_is_admin_only_and_does_not_include_payout_data(client):
    paid = create_submitted()
    paid.requester.first_name = "Member"
    paid.requester.last_name = "Person"
    paid.requester.save(update_fields=["first_name", "last_name", "updated_at"])
    admin = create_user("admin@example.com", admin=True)
    mark_reimbursement_paid(
        reimbursement=paid,
        administrator=admin,
        payer_notes="",
    )
    url = f"/admin/{paid.camp_year.year}/reimbursements/paid-expenses.csv"
    assert client.get(url).status_code == 302
    client.force_login(paid.requester)
    assert client.get(url).status_code == 403
    client.force_login(admin)
    response = client.get(url)
    body = response.content.decode()
    assert response.status_code == 200
    assert paid.payout_snapshot.zelle_email not in body
    assert response["Cache-Control"] == "private, no-store"
