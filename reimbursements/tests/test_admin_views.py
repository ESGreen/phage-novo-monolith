import pytest
from django.db.models import ProtectedError
from django.urls import reverse

from reimbursements.models import ReimbursementExpense, ReimbursementExpenseCategory

from .helpers import create_camp_year, create_submitted, create_user

pytestmark = pytest.mark.django_db


def test_annual_admin_page_permissions_and_redirect(client):
    year = create_camp_year()
    assert client.get(reverse("reimbursements:admin-current")).status_code == 302
    member = create_user()
    client.force_login(member)
    assert client.get(reverse("reimbursements:admin-year", args=[year.year])).status_code == 403
    client.force_login(create_user("admin@example.com", admin=True))
    response = client.get(reverse("reimbursements:admin-current"))
    assert response.url.endswith("/admin/2026/reimbursements/")


def test_admin_can_pay_submitted_reimbursement(client):
    reimbursement = create_submitted()
    admin = create_user("admin@example.com", admin=True)
    client.force_login(admin)
    url = reverse("reimbursements:admin-pay", args=[2026, reimbursement.reimbursement_number])
    response = client.post(url, {"payer_notes": "Paid"})
    reimbursement.refresh_from_db()
    assert response.status_code == 302
    assert reimbursement.status == "paid"
    assert reimbursement.paid_by == admin


def test_reject_allows_blank_notes(client):
    reimbursement = create_submitted()
    admin = create_user("admin@example.com", admin=True)
    client.force_login(admin)
    url = reverse("reimbursements:admin-reject", args=[2026, reimbursement.reimbursement_number])
    client.post(url, {"payer_notes": ""})
    reimbursement.refresh_from_db()
    assert reimbursement.status == "rejected"


def test_admin_detail_renders_submitted_actions(client):
    reimbursement = create_submitted()
    client.force_login(create_user("admin@example.com", admin=True))
    url = reverse(
        "reimbursements:admin-detail",
        args=[2026, reimbursement.reimbursement_number],
    )
    response = client.get(url)
    content = response.content.decode()
    assert response.status_code == 200
    assert "Split Expenses" in content
    assert "<th>Select</th>" in content
    assert "Select Food expense" not in content
    assert "Category" in content
    assert "Explanation" in content
    assert "Amount" in content
    assert 'rows="3"' in content
    assert "Mark Paid" in content
    assert 'class="reimbursement-final-actions"' in content
    assert "I confirm that this reimbursement has been paid" not in content
    assert "Reject" in content


def test_category_card_create_and_protect_delete(client):
    year = create_camp_year()
    admin = create_user("admin@example.com", admin=True)
    client.force_login(admin)
    url = reverse("adminui:camp-year-edit", args=[year.year])
    client.post(url, {"action": "reimbursement_category", "name": "Food"})
    category = ReimbursementExpenseCategory.objects.get()
    assert category.name == "Food"
    response = client.post(
        url,
        {"action": "reimbursement_category_delete", "category_id": category.id},
    )
    assert response.status_code == 302
    assert not ReimbursementExpenseCategory.objects.exists()


def test_used_category_cannot_be_deleted(client):
    reimbursement = create_submitted()
    category = reimbursement.expenses.first().category
    client.force_login(create_user("admin@example.com", admin=True))
    url = reverse("adminui:camp-year-edit", args=[reimbursement.camp_year.year])
    response = client.post(
        url,
        {"action": "reimbursement_category_delete", "category_id": category.id},
    )
    assert response.status_code == 302
    assert ReimbursementExpenseCategory.objects.filter(pk=category.pk).exists()


def test_direct_used_category_delete_is_protected():
    reimbursement = create_submitted()
    category = reimbursement.expenses.first().category
    with pytest.raises(ProtectedError):
        category.delete()
    assert ReimbursementExpense.objects.filter(category=category).exists()
