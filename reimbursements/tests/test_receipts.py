from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse

from reimbursements.models import ReimbursementReceipt
from reimbursements.receipts import MAX_RECEIPT_FILE_SIZE_BYTES
from reimbursements.services import add_file_receipt

from .helpers import create_draft, create_user, image_upload, pdf_upload

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def private_root(settings, tmp_path):
    settings.REIMBURSEMENT_RECEIPT_ROOT = tmp_path / "private"


@pytest.mark.parametrize(
    ("upload", "receipt_type"),
    [(image_upload(), "image"), (pdf_upload(), "pdf")],
)
def test_valid_uploads_are_stored_privately(upload, receipt_type, settings):
    reimbursement = create_draft()
    receipt = add_file_receipt(
        reimbursement=reimbursement,
        requester=reimbursement.requester,
        uploaded_file=upload,
    )
    assert receipt.receipt_type == receipt_type
    assert Path(settings.REIMBURSEMENT_RECEIPT_ROOT, receipt.file_path).is_file()
    assert str(settings.MEDIA_ROOT) not in receipt.file_path


def test_file_receipt_can_include_optional_explanation():
    reimbursement = create_draft()
    receipt = add_file_receipt(
        reimbursement=reimbursement,
        requester=reimbursement.requester,
        uploaded_file=pdf_upload(),
        explanation="Groceries and camp supplies.",
    )

    assert receipt.explanation == "Groceries and camp supplies."


def test_invalid_file_is_rejected():
    reimbursement = create_draft()
    bad = pdf_upload("not-an-image.txt")
    with pytest.raises(ValidationError):
        add_file_receipt(
            reimbursement=reimbursement,
            requester=reimbursement.requester,
            uploaded_file=bad,
        )


def test_receipt_access_is_owner_or_admin_only(client):
    reimbursement = create_draft()
    receipt = add_file_receipt(
        reimbursement=reimbursement,
        requester=reimbursement.requester,
        uploaded_file=pdf_upload(),
    )
    url = reverse(
        "reimbursements:receipt-file",
        args=[2026, reimbursement.reimbursement_number, receipt.id],
    )

    assert client.get(url).status_code == 302
    client.force_login(create_user("other@example.com"))
    assert client.get(url).status_code == 404
    client.force_login(reimbursement.requester)
    response = client.get(url)
    assert response.status_code == 200
    assert response["Cache-Control"] == "private, no-store"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response["Content-Disposition"].startswith("attachment")

    client.force_login(create_user("admin@example.com", admin=True))
    assert client.get(url).status_code == 200


def test_explanation_cannot_be_downloaded(client):
    reimbursement = create_draft()
    receipt = ReimbursementReceipt.objects.create(
        reimbursement=reimbursement,
        receipt_type="explanation",
        explanation="No receipt",
    )
    client.force_login(reimbursement.requester)
    url = reverse(
        "reimbursements:receipt-file",
        args=[2026, reimbursement.reimbursement_number, receipt.id],
    )
    assert client.get(url).status_code == 404


def test_file_size_limit_is_enforced():
    reimbursement = create_draft()
    upload = pdf_upload()
    upload.size = MAX_RECEIPT_FILE_SIZE_BYTES + 1
    with pytest.raises(ValidationError):
        add_file_receipt(
            reimbursement=reimbursement,
            requester=reimbursement.requester,
            uploaded_file=upload,
        )


def test_pdf_acceptance_is_extension_based():
    reimbursement = create_draft()
    receipt = add_file_receipt(
        reimbursement=reimbursement,
        requester=reimbursement.requester,
        uploaded_file=pdf_upload("FAKE.PDF"),
    )
    assert receipt.receipt_type == "pdf"


def test_download_filename_cannot_break_content_disposition(client):
    reimbursement = create_draft()
    receipt = add_file_receipt(
        reimbursement=reimbursement,
        requester=reimbursement.requester,
        uploaded_file=pdf_upload('bad"name.pdf'),
    )
    client.force_login(reimbursement.requester)
    url = reverse(
        "reimbursements:receipt-file",
        args=[2026, reimbursement.reimbursement_number, receipt.id],
    )
    header = client.get(url)["Content-Disposition"]
    assert 'filename="badname.pdf"' in header
    assert "filename*=UTF-8''bad%22name.pdf" in header
