from __future__ import annotations

from typing import Any

from django.contrib.auth.base_user import AbstractBaseUser, BaseUserManager
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone


class UserManager(BaseUserManager["User"]):
    """User manager that treats lowercase email as the login identity."""

    @classmethod
    def normalize_email(cls, email: str | None) -> str:
        if email is None:
            return ""
        return email.strip().lower()

    def get_by_natural_key(self, email: str) -> User:
        return self.get(email=self.normalize_email(email))

    def create_user(self, email: str, password: str | None = None, **extra_fields: Any) -> User:
        normalized_email = self.normalize_email(email)
        if not normalized_email:
            raise ValueError("Users must have an email address")

        user = self.model(email=normalized_email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self,
        email: str,
        password: str | None = None,
        **extra_fields: Any,
    ) -> User:
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("is_admin", True)

        if extra_fields.get("is_admin") is not True:
            raise ValueError("Superusers must have is_admin=True")

        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser):
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_active = models.BooleanField(default=True)
    is_admin = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    EMAIL_FIELD = "email"
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["email"]

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.email = User.objects.normalize_email(self.email)
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.email

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    def get_short_name(self) -> str:
        return self.first_name or self.email


class MemberProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    photo = models.ForeignKey(
        "content.MediaItem",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name="profile_photos",
    )
    bio_markdown = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["user__email"]

    def __str__(self) -> str:
        return f"Profile for {self.user.email}"


@receiver(post_save, sender=User)
def create_member_profile(sender: type[User], instance: User, created: bool, **kwargs: Any) -> None:
    if created:
        MemberProfile.objects.get_or_create(user=instance)
