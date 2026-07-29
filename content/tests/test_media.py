from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from content.media import (
    MAX_IMAGE_UPLOAD_SIZE_BYTES,
    create_media_item,
    get_profile_photo_derivative_url,
    profile_photo_derivative_path,
    validate_image_upload,
)

pytestmark = pytest.mark.django_db

PROFILE_PHOTO_FIXTURES_DIR = Path(__file__).resolve().parents[2] / "tests/fixtures/profile_photos"


def image_upload(
    name: str,
    image_format: str,
    content_type: str,
    size: tuple[int, int] = (1, 1),
) -> SimpleUploadedFile:
    output = BytesIO()
    Image.new("RGB", size, "red").save(output, format=image_format)
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


def test_profile_photo_derivative_is_created_from_original(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    media_item = create_media_item(
        image_upload("portrait.jpg", "JPEG", "image/jpeg", size=(1200, 900)),
    )

    url = get_profile_photo_derivative_url(media_item)

    derivative_path = profile_photo_derivative_path(media_item)
    assert url == f"/derived-media/profile_photos/{media_item.id}-768.jpg"
    assert derivative_path.exists()
    with Image.open(derivative_path) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= 768


def test_profile_photo_derivative_reuses_existing_file(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    media_item = create_media_item(
        image_upload("portrait.jpg", "JPEG", "image/jpeg", size=(1200, 900)),
    )

    first_url = get_profile_photo_derivative_url(media_item)
    derivative_path = profile_photo_derivative_path(media_item)
    first_mtime = derivative_path.stat().st_mtime_ns
    second_url = get_profile_photo_derivative_url(media_item)

    assert second_url == first_url
    assert derivative_path.stat().st_mtime_ns == first_mtime


def test_profile_photo_derivative_does_not_modify_original(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    media_item = create_media_item(
        image_upload("portrait.jpg", "JPEG", "image/jpeg", size=(1200, 900)),
    )
    with default_storage.open(media_item.file_path, "rb") as original_file:
        original_bytes = original_file.read()

    get_profile_photo_derivative_url(media_item)

    media_item.refresh_from_db()
    with default_storage.open(media_item.file_path, "rb") as original_file:
        assert original_file.read() == original_bytes
    assert media_item.original_filename == "portrait.jpg"
    assert media_item.content_type == "image/jpeg"
    assert media_item.size_bytes == len(original_bytes)


def test_profile_photo_derivative_uses_first_mpo_frame(settings, tmp_path) -> None:
    settings.MEDIA_ROOT = str(tmp_path / "media")
    settings.DERIVED_MEDIA_ROOT = tmp_path / "derived-media"
    fixture_path = PROFILE_PHOTO_FIXTURES_DIR / "black-mpo.jpeg"
    upload = SimpleUploadedFile(
        "black-mpo.jpeg",
        fixture_path.read_bytes(),
        content_type="image/jpeg",
    )
    media_item = create_media_item(upload)

    get_profile_photo_derivative_url(media_item)

    with Image.open(profile_photo_derivative_path(media_item)) as image:
        assert image.format == "JPEG"
        assert getattr(image, "n_frames", 1) == 1
        assert max(image.size) <= 768
