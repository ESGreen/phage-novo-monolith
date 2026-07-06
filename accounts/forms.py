from __future__ import annotations

from django import forms
from django.contrib.auth import authenticate

from content.media import create_media_item

from .models import MemberProfile, User


class EmailAuthenticationForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Password", strip=False, widget=forms.PasswordInput)

    error_messages = {
        "invalid_login": "Please enter a correct email and password.",
    }

    def __init__(self, request: object | None = None, *args: object, **kwargs: object) -> None:
        self.request = request
        self.user_cache: User | None = None
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        email = cleaned_data.get("email")
        password = cleaned_data.get("password")

        if email and password:
            self.user_cache = authenticate(self.request, email=email, password=password)
            if self.user_cache is None:
                raise forms.ValidationError(
                    self.error_messages["invalid_login"],
                    code="invalid_login",
                )

        return cleaned_data

    def get_user(self) -> User | None:
        return self.user_cache


class ProfilePhotoForm(forms.Form):
    photo = forms.ImageField(
        label="Photo",
        widget=forms.FileInput(
            attrs={
                "class": "visually-hidden",
                "data-auto-submit-form": "profile-photo-form",
            }
        ),
    )

    def __init__(self, *args: object, user: User, **kwargs: object) -> None:
        self.user = user
        self.profile, _ = MemberProfile.objects.get_or_create(user=user)
        super().__init__(*args, **kwargs)

    def save(self) -> User:
        title = f"{self.user.get_full_name() or self.user.email} profile photo"
        self.profile.photo = create_media_item(self.cleaned_data["photo"], title=title)
        self.profile.save(update_fields=["photo", "updated_at"])
        return self.user


class ProfileBioForm(forms.Form):
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    bio_markdown = forms.CharField(
        label="Bio",
        required=False,
        widget=forms.Textarea(attrs={"rows": 8}),
    )

    def __init__(self, *args: object, user: User, **kwargs: object) -> None:
        self.user = user
        self.profile, _ = MemberProfile.objects.get_or_create(user=user)
        initial = {
            "first_name": user.first_name,
            "last_name": user.last_name,
            "bio_markdown": self.profile.bio_markdown,
        }
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)

    def save(self) -> User:
        self.user.first_name = self.cleaned_data["first_name"]
        self.user.last_name = self.cleaned_data["last_name"]
        self.user.save(update_fields=["first_name", "last_name", "updated_at"])

        self.profile.bio_markdown = self.cleaned_data["bio_markdown"]
        self.profile.save(update_fields=["bio_markdown", "updated_at"])
        return self.user


class EmailChangeForm(forms.Form):
    new_email = forms.EmailField(label="New email")
    confirm_new_email = forms.EmailField(label="Confirm new email")

    def __init__(self, *args: object, user: User, **kwargs: object) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        new_email = User.objects.normalize_email(cleaned_data.get("new_email"))
        confirm_new_email = User.objects.normalize_email(cleaned_data.get("confirm_new_email"))

        cleaned_data["new_email"] = new_email
        cleaned_data["confirm_new_email"] = confirm_new_email

        if new_email and confirm_new_email and new_email != confirm_new_email:
            self.add_error("confirm_new_email", "Email addresses do not match.")
        if (
            new_email
            and new_email != self.user.email
            and User.objects.filter(email=new_email).exclude(pk=self.user.pk).exists()
        ):
            self.add_error("new_email", "Another account already uses this email address.")

        return cleaned_data

    def save(self) -> User:
        self.user.email = self.cleaned_data["new_email"]
        self.user.save(update_fields=["email", "updated_at"])
        return self.user
