from __future__ import annotations

from typing import Any
from urllib.parse import quote

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.files.storage import default_storage
from django.db import models
from django.urls import reverse


class ContentPage(models.Model):
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    body_markdown = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title

    def get_absolute_url(self) -> str:
        return reverse("content:page-detail", kwargs={"slug": self.slug})


class MediaItem(models.Model):
    title = models.CharField(max_length=200, blank=True)
    original_filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=255, unique=True)
    content_type = models.CharField(max_length=100)
    size_bytes = models.PositiveBigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "original_filename"]

    def __str__(self) -> str:
        return self.title or self.original_filename

    @property
    def url(self) -> str:
        return f"{settings.MEDIA_URL.rstrip('/')}/{quote(self.file_path)}"

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        file_path = self.file_path
        result = super().delete(*args, **kwargs)
        if file_path:
            default_storage.delete(file_path)
        return result


class Menu(models.Model):
    ROOT_MENU_NAME = "root"

    menu_name = models.SlugField(max_length=100, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["menu_name"]

    def __str__(self) -> str:
        return self.menu_name

    @property
    def display_name(self) -> str:
        return self.menu_name.replace("-", " ").title()

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        if self.menu_name == self.ROOT_MENU_NAME:
            raise ValidationError("The root menu cannot be deleted.")
        return super().delete(*args, **kwargs)


class MenuItem(models.Model):
    menu = models.ForeignKey(Menu, on_delete=models.CASCADE, related_name="items")
    label = models.CharField(max_length=200)
    url = models.CharField(max_length=500)
    display_order = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["display_order", "label"]

    def __str__(self) -> str:
        return self.label
