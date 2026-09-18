from django.urls import path

from . import views

app_name = "reimbursements"

MEMBER_BASE = "<int:year>/reimbursements/<str:reimbursement_number>/"
ADMIN_BASE = "admin/<int:year>/reimbursements/<str:reimbursement_number>/"

urlpatterns = [
    path("reimbursements/", views.member_current, name="member-current"),
    path("<int:year>/reimbursements/", views.member_list, name="member-list"),
    path("<int:year>/reimbursements/create/", views.member_create, name="member-create"),
    path(MEMBER_BASE, views.member_detail, name="member-detail"),
    path(f"{MEMBER_BASE}payment/", views.member_save_payout, name="member-save-payout"),
    path(f"{MEMBER_BASE}expenses/add/", views.member_add_expense, name="member-add-expense"),
    path(
        f"{MEMBER_BASE}expenses/<int:expense_id>/delete/",
        views.member_delete_expense,
        name="member-delete-expense",
    ),
    path(
        f"{MEMBER_BASE}receipts/upload/",
        views.member_upload_receipt,
        name="member-upload-receipt",
    ),
    path(
        f"{MEMBER_BASE}receipts/explanation/",
        views.member_add_explanation,
        name="member-add-explanation",
    ),
    path(
        f"{MEMBER_BASE}receipts/<int:receipt_id>/delete/",
        views.member_delete_receipt,
        name="member-delete-receipt",
    ),
    path(
        f"{MEMBER_BASE}receipts/<int:receipt_id>/",
        views.receipt_file,
        name="receipt-file",
    ),
    path(f"{MEMBER_BASE}notes/", views.member_save_notes, name="member-save-notes"),
    path(f"{MEMBER_BASE}submit/", views.member_submit, name="member-submit"),
    path(f"{MEMBER_BASE}unsubmit/", views.member_unsubmit, name="member-unsubmit"),
    path(f"{MEMBER_BASE}delete/", views.member_delete, name="member-delete"),
    path("admin/reimbursements/", views.admin_current, name="admin-current"),
    path("admin/<int:year>/reimbursements/", views.admin_year, name="admin-year"),
    path(
        "admin/<int:year>/reimbursements/paid-expenses.csv",
        views.admin_paid_expenses_csv,
        name="admin-paid-expenses-csv",
    ),
    path(ADMIN_BASE, views.admin_detail, name="admin-detail"),
    path(f"{ADMIN_BASE}notes/", views.admin_save_notes, name="admin-save-notes"),
    path(
        f"{ADMIN_BASE}expenses/add/",
        views.admin_add_expense,
        name="admin-add-expense",
    ),
    path(
        f"{ADMIN_BASE}expenses/<int:expense_id>/delete/",
        views.admin_delete_expense,
        name="admin-delete-expense",
    ),
    path(
        f"{ADMIN_BASE}receipts/upload/",
        views.admin_upload_receipt,
        name="admin-upload-receipt",
    ),
    path(
        f"{ADMIN_BASE}receipts/explanation/",
        views.admin_add_explanation,
        name="admin-add-explanation",
    ),
    path(
        f"{ADMIN_BASE}receipts/<int:receipt_id>/delete/",
        views.admin_delete_receipt,
        name="admin-delete-receipt",
    ),
    path(f"{ADMIN_BASE}submit/", views.admin_submit, name="admin-submit"),
    path(f"{ADMIN_BASE}split/", views.admin_split, name="admin-split"),
    path(f"{ADMIN_BASE}pay/", views.admin_pay, name="admin-pay"),
    path(f"{ADMIN_BASE}reject/", views.admin_reject, name="admin-reject"),
    path(
        f"{ADMIN_BASE}return-to-draft/",
        views.admin_return_to_draft,
        name="admin-return-to-draft",
    ),
    path(
        f"{ADMIN_BASE}restore-submitted/",
        views.admin_restore_submitted,
        name="admin-restore-submitted",
    ),
]
