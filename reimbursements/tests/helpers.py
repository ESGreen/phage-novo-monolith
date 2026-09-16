from __future__ import annotations

from io import BytesIO

from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.models import User
from camp.models import CampYear
from reimbursements.models import (
    ReimbursementExpense,
    ReimbursementExpenseCategory,
    ReimbursementPayoutProfile,
    ReimbursementReceipt,
)
from reimbursements.services import create_reimbursement_draft, submit_reimbursement


def create_user(email="member@example.com", *, admin=False):
    return User.objects.create_user(email=email, password="password123!", is_admin=admin)


def create_camp_year(year=2026):
    return CampYear.objects.create(year=year)


def create_category(camp_year, name="Food"):
    return ReimbursementExpenseCategory.objects.create(camp_year=camp_year, name=name)


def create_profile(user):
    return ReimbursementPayoutProfile.objects.create(
        user=user,
        method=ReimbursementPayoutProfile.Method.ZELLE,
        zelle_email=user.email,
    )


def create_draft(user=None, camp_year=None):
    user = user or create_user()
    camp_year = camp_year or create_camp_year()
    return create_reimbursement_draft(requester=user, camp_year=camp_year)


def add_required_data(reimbursement):
    category = ReimbursementExpenseCategory.objects.filter(
        camp_year=reimbursement.camp_year,
        name="Food",
    ).first() or create_category(reimbursement.camp_year)
    ReimbursementExpense.objects.create(
        reimbursement=reimbursement,
        category=category,
        description="Groceries",
        amount_cents=1250,
    )
    ReimbursementReceipt.objects.create(
        reimbursement=reimbursement,
        receipt_type=ReimbursementReceipt.ReceiptType.EXPLANATION,
        explanation="Receipt unavailable.",
    )
    create_profile(reimbursement.requester)
    return reimbursement


def create_submitted(user=None, camp_year=None):
    reimbursement = add_required_data(create_draft(user, camp_year))
    return submit_reimbursement(reimbursement=reimbursement, requester=reimbursement.requester)


def image_upload(name="receipt.png", image_format="PNG"):
    data = BytesIO()
    Image.new("RGB", (4, 4), "white").save(data, format=image_format)
    return SimpleUploadedFile(name, data.getvalue(), content_type=f"image/{image_format.lower()}")


def pdf_upload(name="receipt.pdf"):
    return SimpleUploadedFile(name, b"not actually a pdf", content_type="application/pdf")
