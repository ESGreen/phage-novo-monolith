from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path, PurePath

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, UnidentifiedImageError

from .models import Reimbursement, ReimbursementReceipt

MAX_RECEIPT_FILE_SIZE_BYTES = 15 * 1024 * 1024
MAX_RECEIPT_FILES = 20
MAX_RECEIPT_TOTAL_SIZE_BYTES = 100 * 1024 * 1024

_IMAGE_TYPES = {
    "JPEG": (".jpg", "image/jpeg"),
    "PNG": (".png", "image/png"),
    "WEBP": (".webp", "image/webp"),
}


@dataclass(frozen=True)
class ValidatedReceiptUpload:
    receipt_type: str
    original_filename: str
    extension: str
    content_type: str
    size_bytes: int


def _safe_original_filename(name: str, extension: str) -> str:
    basename = PurePath(name.replace("\\", "/")).name
    basename = "".join(character for character in basename if ord(character) >= 32)
    stem = Path(basename).stem.strip() or "receipt"
    max_stem_length = 255 - len(extension)
    return f"{stem[:max_stem_length]}{extension}"


def validate_receipt_upload(uploaded_file: UploadedFile) -> ValidatedReceiptUpload:
    if uploaded_file.size <= 0:
        raise ValidationError("Receipt file is empty.")
    if uploaded_file.size > MAX_RECEIPT_FILE_SIZE_BYTES:
        raise ValidationError("Receipt files may not exceed 15 MB.")

    original_suffix = Path(uploaded_file.name).suffix.lower()
    if original_suffix == ".pdf":
        extension = ".pdf"
        receipt_type = ReimbursementReceipt.ReceiptType.PDF
        content_type = "application/pdf"
    else:
        try:
            uploaded_file.seek(0)
            with Image.open(uploaded_file) as image:
                image.verify()
                image_format = image.format
        except (UnidentifiedImageError, OSError, SyntaxError) as exc:
            raise ValidationError("Upload a JPEG, PNG, WebP, or PDF receipt.") from exc
        finally:
            uploaded_file.seek(0)
        if image_format not in _IMAGE_TYPES:
            raise ValidationError("Upload a JPEG, PNG, WebP, or PDF receipt.")
        extension, content_type = _IMAGE_TYPES[image_format]
        receipt_type = ReimbursementReceipt.ReceiptType.IMAGE

    return ValidatedReceiptUpload(
        receipt_type=receipt_type,
        original_filename=_safe_original_filename(uploaded_file.name, extension),
        extension=extension,
        content_type=content_type,
        size_bytes=uploaded_file.size,
    )


def build_receipt_relative_path(
    reimbursement: Reimbursement,
    extension: str,
    *,
    file_uuid: uuid.UUID | None = None,
) -> str:
    value = file_uuid or uuid.uuid4()
    return f"{reimbursement.camp_year.year}/{reimbursement.reimbursement_number}/{value}{extension}"


def receipt_absolute_path(relative_path: str) -> Path:
    if not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
        raise ValidationError("Invalid receipt path.")
    root = Path(settings.REIMBURSEMENT_RECEIPT_ROOT).resolve()
    candidate = (root / relative_path).resolve()
    if root not in candidate.parents:
        raise ValidationError("Invalid receipt path.")
    return candidate


def store_receipt_file(uploaded_file: UploadedFile, relative_path: str) -> None:
    target = receipt_absolute_path(relative_path)
    target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with target.open("xb") as stored_file:
        for chunk in uploaded_file.chunks():
            stored_file.write(chunk)
    os.chmod(target, 0o600)


def copy_receipt_file(source_relative_path: str, destination_relative_path: str) -> None:
    source = receipt_absolute_path(source_relative_path)
    destination = receipt_absolute_path(destination_relative_path)
    destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    shutil.copyfile(source, destination)
    os.chmod(destination, 0o600)


def delete_receipt_file(relative_path: str) -> None:
    try:
        receipt_absolute_path(relative_path).unlink(missing_ok=True)
    except (OSError, ValidationError):
        return


def receipt_content_type(relative_path: str) -> str:
    return mimetypes.guess_type(relative_path)[0] or "application/octet-stream"
