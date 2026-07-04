from __future__ import annotations

from io import BytesIO

import pytest
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from content.media import MAX_IMAGE_UPLOAD_SIZE_BYTES, create_media_item, validate_image_upload

pytestmark = pytest.mark.django_db


def image_upload(name: str, image_format: str, content_type: str) -> SimpleUploadedFile:
    output = BytesIO()
    Image.new("RGB", (1, 1), "red").save(output, format=image_format)
    return SimpleUploadedFile(name, output.getvalue(), content_type=content_type)


def test_valid_image_uploads_are_accepted() -> None:
    uploads = [
        image_upload("photo.jpg", "JPEG", "image/jpeg"),
        image_upload("photo.png", "PNG", "image/png"),
        image_upload("photo.gif", "GIF", "image/gif"),
        image_upload("photo.webp", "WEBP", "image/webp"),
    ]

    for upload in uploads:
        validate_image_upload(upload)


def test_svg_upload_is_rejected() -> None:
    upload = SimpleUploadedFile(
        "vector.svg",
        b'<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        content_type="image/svg+xml",
    )

    with pytest.raises(ValidationError):
        validate_image_upload(upload)


def test_non_image_upload_is_rejected() -> None:
    upload = SimpleUploadedFile("not-image.png", b"not an image", content_type="image/png")

    with pytest.raises(ValidationError):
        validate_image_upload(upload)


def test_oversized_image_upload_is_rejected() -> None:
    upload = SimpleUploadedFile(
        "huge.png",
        b"x" * (MAX_IMAGE_UPLOAD_SIZE_BYTES + 1),
        content_type="image/png",
    )

    with pytest.raises(ValidationError):
        validate_image_upload(upload)


def test_create_media_item_stores_safe_flat_filename(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    upload = image_upload("../Phage Map 2026.PNG", "PNG", "image/png")

    media_item = create_media_item(upload, title="Map")

    assert media_item.title == "Map"
    assert media_item.original_filename == "phage-map-2026.png"
    assert media_item.file_path == f"{media_item.id}-phage-map-2026.png"
    assert "/" not in media_item.file_path
    assert media_item.url == f"/media/{media_item.file_path}"
    assert default_storage.exists(media_item.file_path)


def test_deleting_media_item_deletes_file(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path)
    media_item = create_media_item(image_upload("photo.png", "PNG", "image/png"))
    file_path = media_item.file_path

    assert default_storage.exists(file_path)
    media_item.delete()

    assert not default_storage.exists(file_path)
