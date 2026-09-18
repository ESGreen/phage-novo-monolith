import pytest
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError

from reimbursements.models import ReimbursementExpense, ReimbursementPayoutSnapshot
from reimbursements.services import (
    ReimbursementConflictError,
    admin_add_expense,
    admin_submit_reimbursement,
    mark_reimbursement_paid,
    reject_reimbursement,
    return_reimbursement_to_draft,
    split_reimbursement,
    submit_reimbursement,
    unsubmit_reimbursement,
)

from .helpers import add_required_data, create_draft, create_submitted, create_user

pytestmark = pytest.mark.django_db


def test_submission_requires_expense_receipt_and_profile():
    draft = create_draft()
    with pytest.raises(ValidationError):
        submit_reimbursement(reimbursement=draft, requester=draft.requester)
    draft.refresh_from_db()
    assert draft.status == "draft"
    assert not ReimbursementPayoutSnapshot.objects.filter(reimbursement=draft).exists()


def test_submit_unsubmit_and_resubmit_snapshot():
    draft = add_required_data(create_draft())
    submit_reimbursement(reimbursement=draft, requester=draft.requester)
    draft.refresh_from_db()
    assert draft.status == "submitted"
    assert draft.payout_snapshot.zelle_email == draft.requester.email

    unsubmit_reimbursement(reimbursement=draft, requester=draft.requester)
    draft.refresh_from_db()
    assert draft.status == "draft"
    assert draft.submitted_at is None
    assert not ReimbursementPayoutSnapshot.objects.filter(reimbursement=draft).exists()


def test_admin_transitions_and_paid_is_terminal():
    reimbursement = create_submitted()
    admin = create_user("admin@example.com", admin=True)
    reject_reimbursement(reimbursement=reimbursement, administrator=admin, payer_notes="")
    reimbursement.refresh_from_db()
    assert reimbursement.status == "rejected"

    return_reimbursement_to_draft(reimbursement=reimbursement, administrator=admin)
    reimbursement.refresh_from_db()
    assert reimbursement.status == "draft"

    reimbursement = create_submitted(create_user("paid@example.com"), reimbursement.camp_year)
    mark_reimbursement_paid(
        reimbursement=reimbursement,
        administrator=admin,
        payer_notes="ok",
    )
    reimbursement.refresh_from_db()
    assert reimbursement.status == "paid"
    with pytest.raises(ReimbursementConflictError):
        unsubmit_reimbursement(reimbursement=reimbursement, requester=reimbursement.requester)


def test_split_moves_only_selected_expenses_and_copies_context():
    reimbursement = create_submitted()
    category = reimbursement.expenses.first().category
    extra = ReimbursementExpense.objects.create(
        reimbursement=reimbursement,
        category=category,
        description="Fuel",
        amount_cents=500,
    )
    reimbursement.requester_notes = "Member notes"
    reimbursement.save(update_fields=["requester_notes"])
    admin = create_user("admin@example.com", admin=True)

    child = split_reimbursement(
        reimbursement=reimbursement,
        administrator=admin,
        expense_ids=[extra.id],
        rationale="Need more detail",
    )
    assert child.status == "draft"
    assert child.split_from_id == reimbursement.id
    assert child.requester_notes == "Member notes"
    assert child.payer_notes == "Need more detail"
    assert list(child.expenses.values_list("id", flat=True)) == [extra.id]
    assert reimbursement.expenses.count() == 1


def test_split_rejects_all_expenses():
    reimbursement = create_submitted()
    admin = create_user("admin@example.com", admin=True)
    with pytest.raises(ValidationError):
        split_reimbursement(
            reimbursement=reimbursement,
            administrator=admin,
            expense_ids=list(reimbursement.expenses.values_list("id", flat=True)),
            rationale="No",
        )


def test_split_source_is_protected_from_deletion():
    reimbursement = create_submitted()
    category = reimbursement.expenses.first().category
    extra = ReimbursementExpense.objects.create(
        reimbursement=reimbursement,
        category=category,
        description="Fuel",
        amount_cents=500,
    )
    child = split_reimbursement(
        reimbursement=reimbursement,
        administrator=create_user("admin@example.com", admin=True),
        expense_ids=[extra.id],
        rationale="Need detail",
    )
    assert child.split_from_id == reimbursement.id
    with pytest.raises(ProtectedError):
        reimbursement.delete()


def test_admin_can_edit_and_submit_member_draft():
    reimbursement = add_required_data(create_draft())
    admin = create_user("admin@example.com", admin=True)
    category = reimbursement.expenses.first().category

    admin_add_expense(
        reimbursement=reimbursement,
        administrator=admin,
        category=category,
        description="Added by admin",
        amount_cents=500,
    )
    admin_submit_reimbursement(reimbursement=reimbursement, administrator=admin)
    reimbursement.refresh_from_db()

    assert reimbursement.status == "submitted"
    assert reimbursement.submitted_by == admin
    assert reimbursement.expenses.filter(description="Added by admin").exists()
    assert reimbursement.payout_snapshot.zelle_email == reimbursement.requester.email


def test_return_to_draft_clears_submitted_by():
    reimbursement = create_submitted()
    admin = create_user("admin@example.com", admin=True)
    assert reimbursement.submitted_by == reimbursement.requester

    return_reimbursement_to_draft(reimbursement=reimbursement, administrator=admin)
    reimbursement.refresh_from_db()

    assert reimbursement.status == "draft"
    assert reimbursement.submitted_by is None
