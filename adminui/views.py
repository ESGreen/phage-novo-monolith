from __future__ import annotations

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import ProtectedError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from accounts.models import User
from accounts.permissions import admin_required
from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from camp.services import get_current_camp_year
from content.models import ContentPage, MediaItem, Menu
from core.models import SiteSettings
from payments.models import Payment, PaymentLog

from .forms import (
    AdminUserCreateForm,
    CampYearForm,
    ContentPageForm,
    MediaUploadAdminForm,
    MenuForm,
    MenuItemForm,
    TaxAddOnForm,
    TaxOverrideForm,
    TaxTierForm,
)


@admin_required
def home(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "adminui/home.html",
        {
            "site_settings": SiteSettings.load(),
            "current_camp_year": get_current_camp_year(),
        },
    )


@admin_required
def users(request: HttpRequest) -> HttpResponse:
    form = AdminUserCreateForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User created.")
        return redirect("adminui:users")
    return render(
        request,
        "adminui/users.html",
        {"users": User.objects.all(), "form": form},
    )


@admin_required
def camp(request: HttpRequest) -> HttpResponse:
    forms = _camp_forms()
    if request.method == "POST":
        action = request.POST.get("action")
        form_map = {
            "camp_year": CampYearForm,
            "tax_tier": TaxTierForm,
            "tax_add_on": TaxAddOnForm,
            "tax_override": TaxOverrideForm,
        }
        form_class = form_map.get(action)
        if form_class is not None:
            form = form_class(request.POST)
            forms[f"{action}_form"] = form
            if form.is_valid():
                obj = form.save(commit=False)
                obj.created_by = request.user
                obj.updated_by = request.user
                obj.save()
                messages.success(request, "Camp item saved.")
                return redirect("adminui:camp")

    return render(
        request,
        "adminui/camp.html",
        {
            **forms,
            "camp_years": CampYear.objects.all(),
            "tax_tiers": TaxTier.objects.select_related("camp_year"),
            "tax_add_ons": TaxAddOn.objects.select_related("camp_year"),
            "tax_overrides": TaxOverride.objects.select_related("user", "camp_year"),
        },
    )


@admin_required
def payments(request: HttpRequest) -> HttpResponse:
    return render(
        request,
        "adminui/payments.html",
        {
            "payments": Payment.objects.select_related("user", "camp_year"),
            "logs": PaymentLog.objects.select_related("payment")[:50],
        },
    )


@admin_required
def stripe(request: HttpRequest) -> HttpResponse:
    site_settings = SiteSettings.load()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "switch_mode":
            site_settings.stripe_mode = request.POST.get(
                "stripe_mode",
                SiteSettings.StripeMode.TEST,
            )
            site_settings.save(update_fields=["stripe_mode", "updated_at"])
            messages.success(request, "Stripe mode switched.")
            return redirect("adminui:stripe")
        if action == "delete_test_payments" and request.POST.get("confirm") == "delete":
            test_payments = Payment.objects.filter(stripe_mode=Payment.StripeMode.TEST)
            count = test_payments.count()
            PaymentLog.objects.filter(payment__in=test_payments).delete()
            test_payments.delete()
            messages.success(request, f"Deleted {count} test payments.")
            return redirect("adminui:stripe")

    return render(
        request,
        "adminui/stripe.html",
        {
            "site_settings": site_settings,
            "logs": PaymentLog.objects.all()[:50],
            "test_payment_count": Payment.objects.filter(
                stripe_mode=Payment.StripeMode.TEST,
            ).count(),
        },
    )


@admin_required
def pages(request: HttpRequest) -> HttpResponse:
    form = ContentPageForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create":
            form = ContentPageForm(request.POST)
            if form.is_valid():
                form.save()
                messages.success(request, "Page saved.")
                return redirect("adminui:pages")
        elif action == "delete":
            page = get_object_or_404(ContentPage, pk=request.POST.get("page_id"))
            try:
                page.delete()
                messages.success(request, "Page deleted.")
            except ProtectedError:
                messages.error(request, "Page is in use and cannot be deleted.")
            return redirect("adminui:pages")
    return render(
        request,
        "adminui/pages.html",
        {"pages": ContentPage.objects.all(), "form": form},
    )


@admin_required
def menus(request: HttpRequest) -> HttpResponse:
    Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
    menu_form = MenuForm()
    item_form = MenuItemForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_menu":
            menu_form = MenuForm(request.POST)
            if menu_form.is_valid():
                menu_form.save()
                messages.success(request, "Menu saved.")
                return redirect("adminui:menus")
        elif action == "create_item":
            item_form = MenuItemForm(request.POST)
            if item_form.is_valid():
                item_form.save()
                messages.success(request, "Menu item saved.")
                return redirect("adminui:menus")
        elif action == "delete_menu":
            menu = get_object_or_404(Menu, pk=request.POST.get("menu_id"))
            try:
                menu.delete()
                messages.success(request, "Menu deleted.")
            except ValidationError as error:
                messages.error(request, error.messages[0])
            return redirect("adminui:menus")
    return render(
        request,
        "adminui/menus.html",
        {
            "menus": Menu.objects.prefetch_related("items"),
            "menu_form": menu_form,
            "item_form": item_form,
        },
    )


@admin_required
def media(request: HttpRequest) -> HttpResponse:
    form = MediaUploadAdminForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "upload":
            form = MediaUploadAdminForm(request.POST, request.FILES)
            if form.is_valid():
                form.save()
                messages.success(request, "Media uploaded.")
                return redirect("adminui:media")
        elif action == "delete":
            media_item = get_object_or_404(MediaItem, pk=request.POST.get("media_id"))
            media_item.delete()
            messages.success(request, "Media deleted.")
            return redirect("adminui:media")
    return render(
        request,
        "adminui/media.html",
        {"media_items": MediaItem.objects.all(), "form": form},
    )


def _camp_forms() -> dict[str, object]:
    return {
        "camp_year_form": CampYearForm(),
        "tax_tier_form": TaxTierForm(),
        "tax_add_on_form": TaxAddOnForm(),
        "tax_override_form": TaxOverrideForm(),
    }
