import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from reimbursements.models import ReimbursementExpense, ReimbursementPayoutProfile

from .helpers import create_camp_year, create_category, create_draft, create_user

pytestmark = pytest.mark.django_db


def test_reimbursement_defaults_and_yearly_numbers():
    year = create_camp_year()
    user = create_user()
    first = create_draft(user, year)
    second = create_draft(user, year)

    assert first.status == "draft"
    assert first.reimbursement_number == "2026-R-0001"
    assert second.reimbursement_number == "2026-R-0002"


def test_reimbursement_total_is_derived_from_expenses():
    reimbursement = create_draft()
    category = create_category(reimbursement.camp_year)
    ReimbursementExpense.objects.create(
        reimbursement=reimbursement,
        category=category,
        description="A",
        amount_cents=100,
    )
    ReimbursementExpense.objects.create(
        reimbursement=reimbursement,
        category=category,
        description="B",
        amount_cents=250,
    )
    assert reimbursement.total_amount_cents == 350


def test_expense_rejects_wrong_year_category():
    reimbursement = create_draft()
    category = create_category(create_camp_year(2025))
    expense = ReimbursementExpense(
        reimbursement=reimbursement,
        category=category,
        description="Bad",
        amount_cents=1,
    )
    with pytest.raises(ValidationError):
        expense.full_clean()


def test_category_is_unique_case_insensitively():
    year = create_camp_year()
    create_category(year, "Food")
    with pytest.raises(IntegrityError):
        create_category(year, "food")


def test_payout_profile_normalizes_and_switches_methods():
    user = create_user()
    profile = ReimbursementPayoutProfile(
        user=user,
        method="zelle",
        zelle_email=" PERSON@EXAMPLE.COM ",
        check_city="Old",
    )
    profile.full_clean()
    assert profile.zelle_email == "person@example.com"
    assert profile.check_city == ""

    profile.method = "paper_check"
    profile.check_payee_name = " Fred "
    profile.check_address_line_1 = " 1 Main "
    profile.check_city = " Seattle "
    profile.check_state = "wa"
    profile.check_postal_code = "98101"
    profile.full_clean()
    assert profile.zelle_email == ""
    assert profile.check_state == "WA"


def test_profile_rejects_invalid_state_and_zip():
    profile = ReimbursementPayoutProfile(
        user=create_user(),
        method="paper_check",
        check_payee_name="Fred",
        check_address_line_1="1 Main",
        check_city="Seattle",
        check_state="XX",
        check_postal_code="bad",
    )
    with pytest.raises(ValidationError):
        profile.full_clean()
