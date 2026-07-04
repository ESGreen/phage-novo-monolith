from __future__ import annotations

from django import forms
from django.contrib.auth.password_validation import validate_password

from accounts.models import User
from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from content.media import create_media_item
from content.models import ContentPage, Menu, MenuItem


class AdminUserCreateForm(forms.Form):
    email = forms.EmailField()
    first_name = forms.CharField(max_length=150, required=False)
    last_name = forms.CharField(max_length=150, required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    is_admin = forms.BooleanField(required=False)
    password = forms.CharField(widget=forms.PasswordInput)
    bio_markdown = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
    photo = forms.ImageField(required=False)

    def clean_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["email"])
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_password(self) -> str:
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def save(self) -> User:
        user = User.objects.create_user(
            email=self.cleaned_data["email"],
            password=self.cleaned_data["password"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            is_active=self.cleaned_data["is_active"],
            is_admin=self.cleaned_data["is_admin"],
        )
        user.profile.bio_markdown = self.cleaned_data["bio_markdown"]
        if self.cleaned_data.get("photo"):
            user.profile.photo = create_media_item(
                self.cleaned_data["photo"],
                title=f"{user.get_full_name() or user.email} profile photo",
            )
        user.profile.save(update_fields=["photo", "bio_markdown", "updated_at"])
        return user


class ContentPageForm(forms.ModelForm):
    class Meta:
        model = ContentPage
        fields = ["title", "slug", "body_markdown"]
        widgets = {"body_markdown": forms.Textarea(attrs={"rows": 8})}


class MenuForm(forms.ModelForm):
    class Meta:
        model = Menu
        fields = ["menu_name"]


class MenuItemForm(forms.ModelForm):
    class Meta:
        model = MenuItem
        fields = ["menu", "label", "url", "display_order"]


class CampYearForm(forms.ModelForm):
    class Meta:
        model = CampYear
        fields = ["year", "dashboard_pre_page", "dashboard_post_page"]


class TaxTierForm(forms.ModelForm):
    class Meta:
        model = TaxTier
        fields = [
            "camp_year",
            "name",
            "description",
            "minimum_amount_cents",
            "start_date",
            "expiration_date",
            "display_order",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "expiration_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TaxAddOnForm(forms.ModelForm):
    class Meta:
        model = TaxAddOn
        fields = [
            "camp_year",
            "name",
            "description",
            "amount_cents",
            "start_date",
            "expiration_date",
            "display_order",
        ]
        widgets = {
            "description": forms.Textarea(attrs={"rows": 3}),
            "start_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
            "expiration_date": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }


class TaxOverrideForm(forms.ModelForm):
    class Meta:
        model = TaxOverride
        fields = ["user", "camp_year", "override_type", "reduced_minimum_amount_cents", "note"]
        widgets = {"note": forms.Textarea(attrs={"rows": 3})}


class MediaUploadAdminForm(forms.Form):
    title = forms.CharField(max_length=200, required=False)
    image = forms.ImageField()

    def save(self):
        return create_media_item(
            self.cleaned_data["image"],
            title=self.cleaned_data.get("title", ""),
        )
