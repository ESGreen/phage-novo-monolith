from __future__ import annotations

from django import forms
from django.core.files.uploadedfile import UploadedFile

from .media import create_media_item, validate_image_upload
from .models import MediaItem


class MediaUploadForm(forms.Form):
    title = forms.CharField(max_length=200, required=False)
    file = forms.FileField()

    def clean_file(self) -> UploadedFile:
        uploaded_file = self.cleaned_data["file"]
        validate_image_upload(uploaded_file)
        return uploaded_file

    def save(self) -> MediaItem:
        return create_media_item(
            self.cleaned_data["file"],
            title=self.cleaned_data.get("title", ""),
        )
