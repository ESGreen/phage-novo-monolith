import pytest

from reimbursements.forms import ReimbursementExpenseCreateForm, ReimbursementPayoutProfileForm
from reimbursements.models import ReimbursementPayoutProfile

from .helpers import create_camp_year, create_category, create_draft, create_user

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.01", 1), ("12.34", 1234), ("1000000.00", 100_000_000)],
)
def test_expense_amount_converts_to_integer_cents(value, expected):
    reimbursement = create_draft()
    category = create_category(reimbursement.camp_year)
    form = ReimbursementExpenseCreateForm(
        {"description": "Expense", "category": category.id, "amount_dollars": value},
        reimbursement=reimbursement,
    )
    assert form.is_valid(), form.errors
    assert form.amount_cents == expected


@pytest.mark.parametrize("value", ["0", "-1", "1.001", "1000000.01", "abc"])
def test_expense_amount_rejects_invalid_values(value):
    reimbursement = create_draft()
    category = create_category(reimbursement.camp_year)
    form = ReimbursementExpenseCreateForm(
        {"description": "Expense", "category": category.id, "amount_dollars": value},
        reimbursement=reimbursement,
    )
    assert not form.is_valid()


def test_expense_category_choices_are_year_scoped():
    reimbursement = create_draft()
    own = create_category(reimbursement.camp_year)
    other_reimbursement = create_draft(
        user=create_user("other@example.com"),
        camp_year=create_camp_year(2025),
    )
    other = create_category(other_reimbursement.camp_year)
    form = ReimbursementExpenseCreateForm(reimbursement=reimbursement)
    assert list(form.fields["category"].queryset) == [own]
    assert other not in form.fields["category"].queryset


@pytest.mark.parametrize("description", ["", "   "])
def test_expense_description_is_required(description):
    reimbursement = create_draft()
    category = create_category(reimbursement.camp_year)
    form = ReimbursementExpenseCreateForm(
        {
            "description": description,
            "category": category.id,
            "amount_dollars": "1.00",
        },
        reimbursement=reimbursement,
    )
    assert not form.is_valid()


def test_new_payout_profile_defaults_to_paper_check_without_blank_choice():
    user = create_user()
    form = ReimbursementPayoutProfileForm(user=user)

    assert form.initial["method"] == ReimbursementPayoutProfile.Method.PAPER_CHECK
    assert form.fields["method"].empty_label is None
    assert list(form.fields["method"].choices) == [
        ("paper_check", "Paper check"),
        ("zelle", "Zelle"),
    ]
