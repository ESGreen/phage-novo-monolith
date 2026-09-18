import pytest
from django.urls import reverse

from reimbursements.models import Reimbursement, ReimbursementPayoutProfile
from reimbursements.services import (
    mark_reimbursement_paid,
    reject_reimbursement,
    submit_reimbursement,
)

from .helpers import add_required_data, create_camp_year, create_draft, create_user

pytestmark = pytest.mark.django_db


def test_current_reimbursements_redirects_to_latest_year(client):
    create_camp_year(2025)
    create_camp_year(2026)
    client.force_login(create_user())

    response = client.get(reverse("reimbursements:member-current"))

    assert response.status_code == 302
    assert response.url == reverse("reimbursements:member-list", args=[2026])


def test_current_reimbursements_without_year_renders_empty_state(client):
    client.force_login(create_user())

    response = client.get(reverse("reimbursements:member-current"))

    assert response.status_code == 200
    assert "No camp year is configured" in response.content.decode()


def test_member_overview_requires_login_and_is_owner_scoped(client):
    year = create_camp_year()
    member = create_user()
    own = create_draft(member, year)
    other = create_draft(create_user("other@example.com"), year)
    url = reverse("reimbursements:member-list", args=[year.year])
    assert client.get(url).status_code == 302
    client.force_login(member)
    response = client.get(url)
    content = response.content.decode()
    assert own.reimbursement_number in content
    assert other.reimbursement_number not in content
    assert "Status and Actions" in content
    assert "Open it to add expenses and receipts, then submit it when finished" in content
    assert "unsubmit it if you need to make changes" in content
    assert ">Edit<" in content
    assert ">Submit<" in content


def test_create_is_post_only_and_uses_logged_in_member(client):
    year = create_camp_year()
    member = create_user()
    client.force_login(member)
    url = reverse("reimbursements:member-create", args=[year.year])
    assert client.get(url).status_code == 405
    response = client.post(url)
    reimbursement = Reimbursement.objects.get()
    assert reimbursement.requester == member
    assert response.status_code == 302


def test_member_cannot_view_other_reimbursement(client):
    reimbursement = create_draft()
    client.force_login(create_user("other@example.com"))
    url = reverse("reimbursements:member-detail", args=[2026, reimbursement.reimbursement_number])
    assert client.get(url).status_code == 404


def test_admin_member_url_redirects_to_admin_detail_for_other_member(client):
    reimbursement = create_draft()
    admin = create_user("admin@example.com", admin=True)
    client.force_login(admin)
    member_url = reverse(
        "reimbursements:member-detail",
        args=[2026, reimbursement.reimbursement_number],
    )

    response = client.get(member_url)

    assert response.status_code == 302
    assert response.url == reverse(
        "reimbursements:admin-detail",
        args=[2026, reimbursement.reimbursement_number],
    )


def test_member_detail_renders_draft_forms(client):
    reimbursement = create_draft()
    client.force_login(reimbursement.requester)
    url = reverse(
        "reimbursements:member-detail",
        args=[2026, reimbursement.reimbursement_number],
    )
    response = client.get(url)
    content = response.content.decode()
    assert response.status_code == 200
    assert "Payment Method" in content
    assert "Draft reimbursements will not be paid" in content
    assert "Submit this reimbursement when you have finished" in content
    assert 'data-payout-method="true"' in content
    assert 'data-payout-fields="zelle"' in content
    assert 'data-payout-fields="paper_check"' in content
    assert "JavaScript is off" in content
    assert "Upload Receipt" in content
    assert 'class="receipt-upload-form"' in content
    assert "Receipts are best" in content
    assert "please provide as much information as you can in an explanation" in content
    assert "Add Expense" in content
    assert "A reimbursement is made up of categorized expenses" in content
    assert "better track camp spending" in content
    assert 'class="reimbursement-expense-form"' in content
    assert 'class="expense-form-top-row"' in content
    assert 'class="expense-form-description form-row"' in content
    assert 'rows="2"' in content
    assert 'name="requester_notes"' in content
    assert 'rows="4"' in content
    assert "Delete Reimbursement" in content


def test_member_detail_renders_receipt_evidence_as_table(client):
    reimbursement = add_required_data(create_draft())
    client.force_login(reimbursement.requester)
    url = reverse(
        "reimbursements:member-detail",
        args=[2026, reimbursement.reimbursement_number],
    )

    response = client.get(url)
    content = response.content.decode()

    assert "Notes / Explanation" in content
    assert "Explanation" in content
    assert "Receipt unavailable." in content
    assert "Type <strong>delete</strong>" in content


def test_full_member_submit_unsubmit_flow(client):
    reimbursement = add_required_data(create_draft())
    client.force_login(reimbursement.requester)
    submit_url = reverse(
        "reimbursements:member-submit",
        args=[2026, reimbursement.reimbursement_number],
    )
    response = client.post(submit_url)
    reimbursement.refresh_from_db()
    assert response.status_code == 302
    assert reimbursement.status == "submitted"
    assert reimbursement.submitted_by == reimbursement.requester

    unsubmit_url = reverse(
        "reimbursements:member-unsubmit",
        args=[2026, reimbursement.reimbursement_number],
    )
    client.post(unsubmit_url)
    reimbursement.refresh_from_db()
    assert reimbursement.status == "draft"
    assert reimbursement.submitted_at is None


def test_member_overview_shows_submitted_actions(client):
    reimbursement = add_required_data(create_draft())
    submit_reimbursement(reimbursement=reimbursement, requester=reimbursement.requester)
    client.force_login(reimbursement.requester)

    response = client.get(
        reverse("reimbursements:member-list", args=[reimbursement.camp_year.year])
    )
    content = response.content.decode()

    assert ">View<" in content
    assert ">Unsubmit<" in content


@pytest.mark.parametrize(
    ("status", "message"),
    [
        ("submitted", "waiting for the camp to review and pay it"),
        ("paid", "This reimbursement has been paid"),
        ("rejected", "This reimbursement was rejected"),
    ],
)
def test_member_summary_explains_non_draft_statuses(client, status, message):
    reimbursement = add_required_data(create_draft())
    submit_reimbursement(reimbursement=reimbursement, requester=reimbursement.requester)
    if status == "paid":
        admin = create_user("admin@example.com", admin=True)
        mark_reimbursement_paid(
            reimbursement=reimbursement,
            administrator=admin,
            payer_notes="",
        )
    elif status == "rejected":
        admin = create_user("admin@example.com", admin=True)
        reject_reimbursement(
            reimbursement=reimbursement,
            administrator=admin,
            payer_notes="",
        )
    client.force_login(reimbursement.requester)
    response = client.get(
        reverse(
            "reimbursements:member-detail",
            args=[reimbursement.camp_year.year, reimbursement.reimbursement_number],
        )
    )
    assert message in response.content.decode()


def test_profile_payout_form_is_self_scoped(client):
    member = create_user()
    client.force_login(member)
    response = client.post(
        reverse("accounts:profile"),
        {"action": "reimbursement_payout", "method": "zelle", "zelle_email": "PAY@EXAMPLE.COM"},
    )
    assert response.status_code == 302
    assert ReimbursementPayoutProfile.objects.get(user=member).zelle_email == "pay@example.com"
