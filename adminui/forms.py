from __future__ import annotations

from datetime import datetime, time
from decimal import Decimal

from django import forms
from django.contrib.auth.password_validation import validate_password
from django.db.models import Q
from django.utils import timezone

from accounts.models import User
from camp.forms import build_tax_options
from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from camp.taxes import available_tax_add_ons, decimal_dollars_to_cents
from content.media import create_media_item
from content.models import ContentPage, Menu, MenuItem
from payments.models import Payment


class AdminUserCreateForm(forms.Form):
    account_address = forms.EmailField(
        label="Email",
        widget=forms.TextInput(
            attrs={
                "autocomplete": "new-password",
                "autocapitalize": "none",
                "data-1p-ignore": "true",
                "data-bwignore": "true",
                "data-lpignore": "true",
                "inputmode": "email",
                "spellcheck": "false",
            },
        ),
    )
    first_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    last_name = forms.CharField(
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"autocomplete": "off"}),
    )
    is_admin = forms.BooleanField(required=False)
    is_active = forms.BooleanField(required=False, initial=True)
    initial_secret = forms.CharField(
        label="Password",
        strip=False,
        widget=forms.TextInput(
            attrs={
                "autocomplete": "new-password",
                "autocapitalize": "none",
                "data-1p-ignore": "true",
                "data-bwignore": "true",
                "data-lpignore": "true",
                "spellcheck": "false",
            },
        ),
    )

    def clean_account_address(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["account_address"])
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("A user with this email already exists.")
        return email

    def clean_initial_secret(self) -> str:
        password = self.cleaned_data["initial_secret"]
        validate_password(password)
        return password

    def save(self) -> User:
        return User.objects.create_user(
            email=self.cleaned_data["account_address"],
            password=self.cleaned_data["initial_secret"],
            first_name=self.cleaned_data["first_name"],
            last_name=self.cleaned_data["last_name"],
            is_active=self.cleaned_data["is_active"],
            is_admin=self.cleaned_data["is_admin"],
        )


class AdminUserFlagsForm(forms.Form):
    is_active = forms.BooleanField(required=False)
    is_admin = forms.BooleanField(required=False)

    def __init__(self, *args: object, user: User, **kwargs: object) -> None:
        self.user = user
        initial = {
            "is_active": user.is_active,
            "is_admin": user.is_admin,
        }
        initial.update(kwargs.pop("initial", {}))
        super().__init__(*args, initial=initial, **kwargs)

    def save(self) -> User:
        self.user.is_active = self.cleaned_data["is_active"]
        self.user.is_admin = self.cleaned_data["is_admin"]
        self.user.save(update_fields=["is_active", "is_admin", "updated_at"])
        return self.user


class AdminUserEmailForm(forms.Form):
    new_email = forms.EmailField(label="New email")

    def __init__(self, *args: object, user: User, **kwargs: object) -> None:
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_new_email(self) -> str:
        email = User.objects.normalize_email(self.cleaned_data["new_email"])
        if User.objects.filter(email=email).exclude(pk=self.user.pk).exists():
            raise forms.ValidationError("Another account already uses this email address.")
        return email

    def save(self) -> User:
        self.user.email = self.cleaned_data["new_email"]
        self.user.save(update_fields=["email", "updated_at"])
        return self.user


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
        fields = ["label", "url"]
        widgets = {"url": forms.TextInput(attrs={"data-url-combobox-input": "true"})}


def _dollars_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1")))


def _cents_to_dollars(amount_cents: int) -> Decimal:
    return (Decimal(amount_cents) / Decimal("100")).quantize(Decimal("0.01"))


def _date_to_midnight(value) -> datetime:
    return timezone.make_aware(
        datetime.combine(value, time.min),
        timezone.get_current_timezone(),
    )


def _local_date(value: datetime):
    return timezone.localtime(value).date()


def _set_blank_page_labels(form: forms.Form) -> None:
    form.fields["dashboard_pre_page"].empty_label = "----"
    form.fields["dashboard_post_page"].empty_label = "----"
    if "camp_survey" in form.fields:
        form.fields["camp_survey"].empty_label = "----"
        form.fields["camp_survey"].label = "Camp survey"


def _named_users():
    return User.objects.filter(Q(first_name__gt="") | Q(last_name__gt="")).order_by(
        "last_name",
        "first_name",
        "email",
    )


def _user_label(user: User) -> str:
    name = user.get_full_name()
    return f"{name} - {user.email}" if name else user.email


def _user_name_search(user: User) -> str:
    name = user.get_full_name()
    reverse_name = f"{user.last_name} {user.first_name}".strip()
    return f"{name} {reverse_name}".lower()


class NamedUserSelect(forms.Select):
    def create_option(
        self,
        name: str,
        value: object,
        label: str,
        selected: bool,
        index: int,
        subindex: int | None = None,
        attrs: dict[str, object] | None = None,
    ) -> dict[str, object]:
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        user = getattr(value, "instance", None)
        if user is not None:
            option["attrs"]["data-name-search"] = _user_name_search(user)
            option["attrs"]["data-user-label"] = _user_label(user)
        return option


class NamedUserChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj: User) -> str:
        return _user_label(obj)


class CampYearCreateForm(forms.ModelForm):
    class Meta:
        model = CampYear
        fields = ["year", "dashboard_pre_page", "dashboard_post_page"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        initial = kwargs.pop("initial", {})
        initial.setdefault("year", timezone.localdate().year)
        super().__init__(*args, initial=initial, **kwargs)
        _set_blank_page_labels(self)


class CampYearDashboardSetupForm(forms.ModelForm):
    class Meta:
        model = CampYear
        fields = ["dashboard_pre_page", "dashboard_post_page", "camp_survey"]

    def __init__(self, *args: object, **kwargs: object) -> None:
        super().__init__(*args, **kwargs)
        _set_blank_page_labels(self)


class TaxTierCreateForm(forms.ModelForm):
    minimum_amount_dollars = forms.DecimalField(
        label="Minimum amount",
        min_value=Decimal("0.01"),
        max_digits=8,
        decimal_places=2,
    )
    start_date = forms.DateField(
        label="Start date",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    expiration_date = forms.DateField(
        label="End date",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = TaxTier
        fields = [
            "name",
            "description",
            "minimum_amount_dollars",
            "start_date",
            "expiration_date",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args: object, camp_year: CampYear, **kwargs: object) -> None:
        self.camp_year = camp_year
        instance = kwargs.get("instance")
        initial = kwargs.pop("initial", {}).copy()
        if instance is not None and instance.pk:
            initial.setdefault(
                "minimum_amount_dollars",
                _cents_to_dollars(instance.minimum_amount_cents),
            )
            initial.setdefault("start_date", _local_date(instance.start_date))
            initial.setdefault("expiration_date", _local_date(instance.expiration_date))
        super().__init__(*args, initial=initial, **kwargs)
        self.instance.camp_year = camp_year

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        amount = cleaned_data.get("minimum_amount_dollars")
        if amount is not None:
            self.instance.minimum_amount_cents = _dollars_to_cents(amount)
        return cleaned_data

    def clean_start_date(self) -> datetime:
        return _date_to_midnight(self.cleaned_data["start_date"])

    def clean_expiration_date(self) -> datetime:
        return _date_to_midnight(self.cleaned_data["expiration_date"])

    def save(self, commit: bool = True) -> TaxTier:
        obj = super().save(commit=False)
        obj.camp_year = self.camp_year
        obj.minimum_amount_cents = _dollars_to_cents(self.cleaned_data["minimum_amount_dollars"])
        if commit:
            obj.save()
        return obj


class TaxAddOnCreateForm(forms.ModelForm):
    amount_dollars = forms.DecimalField(
        label="Amount",
        min_value=Decimal("0.01"),
        max_digits=8,
        decimal_places=2,
    )
    start_date = forms.DateField(
        label="Start date",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )
    expiration_date = forms.DateField(
        label="End date",
        widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
    )

    class Meta:
        model = TaxAddOn
        fields = [
            "name",
            "description",
            "amount_dollars",
            "start_date",
            "expiration_date",
        ]
        widgets = {"description": forms.Textarea(attrs={"rows": 3})}

    def __init__(self, *args: object, camp_year: CampYear, **kwargs: object) -> None:
        self.camp_year = camp_year
        instance = kwargs.get("instance")
        initial = kwargs.pop("initial", {}).copy()
        if instance is not None and instance.pk:
            initial.setdefault("amount_dollars", _cents_to_dollars(instance.amount_cents))
            initial.setdefault("start_date", _local_date(instance.start_date))
            initial.setdefault("expiration_date", _local_date(instance.expiration_date))
        super().__init__(*args, initial=initial, **kwargs)
        self.instance.camp_year = camp_year

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        amount = cleaned_data.get("amount_dollars")
        if amount is not None:
            self.instance.amount_cents = _dollars_to_cents(amount)
        return cleaned_data

    def clean_start_date(self) -> datetime:
        return _date_to_midnight(self.cleaned_data["start_date"])

    def clean_expiration_date(self) -> datetime:
        return _date_to_midnight(self.cleaned_data["expiration_date"])

    def save(self, commit: bool = True) -> TaxAddOn:
        obj = super().save(commit=False)
        obj.camp_year = self.camp_year
        obj.amount_cents = _dollars_to_cents(self.cleaned_data["amount_dollars"])
        if commit:
            obj.save()
        return obj


class TaxOverrideCreateForm(forms.Form):
    user = NamedUserChoiceField(
        queryset=User.objects.none(),
        widget=NamedUserSelect(attrs={"data-user-combobox-select": "true"}),
    )
    override_type = forms.ChoiceField(choices=TaxOverride.OverrideType.choices)
    reduced_minimum_amount_dollars = forms.DecimalField(
        label="Reduced minimum amount",
        min_value=Decimal("0.01"),
        max_digits=8,
        decimal_places=2,
        required=False,
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args: object, camp_year: CampYear, **kwargs: object) -> None:
        self.camp_year = camp_year
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = _named_users()

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        user = cleaned_data.get("user")
        override_type = cleaned_data.get("override_type")
        amount = cleaned_data.get("reduced_minimum_amount_dollars")

        if user is not None and TaxOverride.objects.filter(
            camp_year=self.camp_year,
            user=user,
        ).exists():
            self.add_error("user", "This user already has a tax override for this camp year.")

        if override_type == TaxOverride.OverrideType.REDUCED_MINIMUM and amount is None:
            self.add_error(
                "reduced_minimum_amount_dollars",
                "Reduced minimum overrides require an amount.",
            )
        elif override_type == TaxOverride.OverrideType.WAIVED and amount is not None:
            self.add_error(
                "reduced_minimum_amount_dollars",
                "Waived overrides cannot have an amount.",
            )
        return cleaned_data

    def save(self, commit: bool = True) -> TaxOverride:
        amount = self.cleaned_data.get("reduced_minimum_amount_dollars")
        obj = TaxOverride(
            user=self.cleaned_data["user"],
            camp_year=self.camp_year,
            override_type=self.cleaned_data["override_type"],
            reduced_minimum_amount_cents=(
                _dollars_to_cents(amount) if amount is not None else None
            ),
            note=self.cleaned_data["note"],
        )
        if commit:
            obj.save()
        return obj


class ManualPaymentCreateForm(forms.Form):
    user = NamedUserChoiceField(
        queryset=User.objects.none(),
        widget=NamedUserSelect(attrs={"data-user-combobox-select": "true"}),
    )
    camp_year = forms.ModelChoiceField(label="Camp year", queryset=CampYear.objects.none())
    tax_amount_dollars = forms.DecimalField(
        label="Tax amount",
        min_value=Decimal("0.00"),
        max_digits=8,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "5.00", "data-tax-amount-input": "true"}),
    )
    add_ons = forms.ModelMultipleChoiceField(
        queryset=TaxAddOn.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )
    note = forms.CharField(
        label="Note/reference",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args: object, **kwargs: object) -> None:
        initial = kwargs.pop("initial", {}).copy()
        camp_years = CampYear.objects.order_by("-year")
        current_camp_year = camp_years.first()
        if current_camp_year is not None:
            initial.setdefault("camp_year", current_camp_year.pk)
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["user"].queryset = _named_users()
        self.fields["camp_year"].queryset = camp_years
        self.selected_camp_year = self._selected_camp_year(camp_years)
        self.fields["add_ons"].queryset = (
            available_tax_add_ons(self.selected_camp_year)
            if self.selected_camp_year is not None
            else TaxAddOn.objects.none()
        )

    @property
    def selected_add_on_ids(self) -> set[int]:
        value = self["add_ons"].value() or []
        return {int(add_on_id) for add_on_id in value if str(add_on_id).isdigit()}

    def _selected_camp_year(self, camp_years) -> CampYear | None:
        value = self.data.get("camp_year") if self.is_bound else self.initial.get("camp_year")
        if isinstance(value, CampYear):
            return value
        if value:
            try:
                return camp_years.filter(pk=value).first()
            except (TypeError, ValueError):
                return None
        return camp_years.first()

    def clean(self) -> dict[str, object]:
        cleaned_data = super().clean()
        user = cleaned_data.get("user")
        camp_year = cleaned_data.get("camp_year")
        tax_amount_dollars = cleaned_data.get("tax_amount_dollars")
        add_ons = cleaned_data.get("add_ons") or []

        if user is None or camp_year is None or tax_amount_dollars is None:
            return cleaned_data

        if Payment.objects.filter(
            user=user,
            camp_year=camp_year,
            status=Payment.Status.PAID,
        ).exists():
            self.add_error("user", "This user already has a paid payment for this camp year.")

        if Payment.objects.filter(
            user=user,
            camp_year=camp_year,
            status=Payment.Status.CREATED,
            checkout_expires_at__gt=timezone.now(),
        ).exists():
            self.add_error(
                "user",
                "This user has an unexpired pending Stripe checkout for this camp year.",
            )

        tax_amount_cents = decimal_dollars_to_cents(tax_amount_dollars)
        tax_options = build_tax_options(user, camp_year)
        qualifying_options = [
            option
            for option in tax_options
            if option.minimum_amount_cents <= tax_amount_cents
        ]
        if not qualifying_options:
            self.add_error(
                "tax_amount_dollars",
                (
                    "No tax tier or override qualifies for this amount. Create an "
                    "appropriate tax override before adding this payment."
                ),
            )
            return cleaned_data

        tax_option = max(
            qualifying_options,
            key=lambda option: option.minimum_amount_cents,
        )
        add_on_amount_cents = sum(add_on.amount_cents for add_on in add_ons)
        total_amount_cents = tax_amount_cents + add_on_amount_cents
        if total_amount_cents <= 0:
            raise forms.ValidationError("No payment is needed unless you select an add-on.")

        cleaned_data["tax_amount_cents"] = tax_amount_cents
        cleaned_data["effective_minimum_cents"] = tax_option.minimum_amount_cents
        cleaned_data["add_on_amount_cents"] = add_on_amount_cents
        cleaned_data["total_amount_cents"] = total_amount_cents
        cleaned_data["tax_tier_name_snapshot"] = tax_option.name
        return cleaned_data


class MediaUploadAdminForm(forms.Form):
    title = forms.CharField(max_length=200, required=False)
    image = forms.ImageField()

    def save(self):
        return create_media_item(
            self.cleaned_data["image"],
            title=self.cleaned_data.get("title", ""),
        )
