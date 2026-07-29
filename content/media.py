from __future__ import annotations

from pathlib import Path, PurePath
from urllib.parse import quote
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile
from django.utils.text import slugify
from PIL import Image, ImageOps, UnidentifiedImageError

from .models import MediaItem

MAX_IMAGE_UPLOAD_SIZE_BYTES = 10 * 1024 * 1024
ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_IMAGE_FORMATS = {"JPEG", "MPO", "PNG", "GIF", "WEBP"}
PROFILE_PHOTO_DERIVATIVE_SIZE = 768
PROFILE_PHOTO_DERIVATIVE_QUALITY = 85


def validate_image_upload(uploaded_file: UploadedFile) -> None:
    original_name = PurePath(uploaded_file.name).name
    extension = PurePath(original_name).suffix.lower().lstrip(".")
    content_type = getattr(uploaded_file, "content_type", "")

    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError("Upload a JPG, PNG, GIF, or WebP image.")
    if content_type not in ALLOWED_CONTENT_TYPES:
        raise ValidationError("Upload a JPG, PNG, GIF, or WebP image.")
    if uploaded_file.size > MAX_IMAGE_UPLOAD_SIZE_BYTES:
        raise ValidationError("Image uploads must be 10 MB or smaller.")

    try:
        image = Image.open(uploaded_file)
        if image.format not in ALLOWED_IMAGE_FORMATS:
            raise ValidationError("Upload a JPG, PNG, GIF, or WebP image.")
        image.verify()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValidationError("Upload a valid image file.") from error
    finally:
        uploaded_file.seek(0)


def safe_original_filename(filename: str) -> str:
    original_name = PurePath(filename).name
    extension = PurePath(original_name).suffix.lower()
    stem = slugify(PurePath(original_name).stem) or "image"
    return f"{stem}{extension}"


def media_storage_filename(media_id: int, original_filename: str) -> str:
    return f"{media_id}-{safe_original_filename(original_filename)}"


def create_media_item(uploaded_file: UploadedFile, title: str = "") -> MediaItem:
    validate_image_upload(uploaded_file)
    original_filename = safe_original_filename(uploaded_file.name)
    media_item = MediaItem.objects.create(
        title=title.strip(),
        original_filename=original_filename,
        file_path=f"pending-{uuid4().hex}",
        content_type=uploaded_file.content_type,
        size_bytes=uploaded_file.size,
    )
    media_item.file_path = default_storage.save(
        media_storage_filename(media_item.id, original_filename),
        uploaded_file,
    )
    media_item.save(update_fields=["file_path", "updated_at"])
    return media_item


def profile_photo_derivative_filename(
    media_item: MediaItem,
    size: int = PROFILE_PHOTO_DERIVATIVE_SIZE,
) -> str:
    return f"profile_photos/{media_item.id}-{size}.jpg"


def profile_photo_derivative_path(media_item: MediaItem, size: int = PROFILE_PHOTO_DERIVATIVE_SIZE):
    return Path(settings.DERIVED_MEDIA_ROOT) / profile_photo_derivative_filename(media_item, size)


def profile_photo_derivative_url(
    media_item: MediaItem,
    size: int = PROFILE_PHOTO_DERIVATIVE_SIZE,
) -> str:
    filename = profile_photo_derivative_filename(media_item, size)
    derived_url = settings.DERIVED_MEDIA_URL.rstrip("/")
    return f"{derived_url}/{quote(filename)}"


def get_profile_photo_derivative_url(
    media_item: MediaItem,
    size: int = PROFILE_PHOTO_DERIVATIVE_SIZE,
) -> str:
    derivative_path = profile_photo_derivative_path(media_item, size)
    if derivative_path.exists():
        return profile_photo_derivative_url(media_item, size)

    derivative_path.parent.mkdir(parents=True, exist_ok=True)
    with default_storage.open(media_item.file_path, "rb") as original_file:
        image = Image.open(original_file)
        image.seek(0)
        image = ImageOps.exif_transpose(image).copy()

    if image.mode in {"RGBA", "LA"} or (image.mode == "P" and "transparency" in image.info):
        background = Image.new("RGB", image.size, "white")
        alpha = image.convert("RGBA").getchannel("A")
        background.paste(image.convert("RGBA"), mask=alpha)
        image = background
    else:
        image = image.convert("RGB")

    image.thumbnail((size, size), Image.Resampling.LANCZOS)
    image.save(
        derivative_path,
        format="JPEG",
        quality=PROFILE_PHOTO_DERIVATIVE_QUALITY,
        optimize=True,
        progressive=True,
    )
    return profile_photo_derivative_url(media_item, size)
