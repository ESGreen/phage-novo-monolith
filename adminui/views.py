from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.forms import SetPasswordForm
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Count, Max, Min, ProtectedError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.forms import ProfileBioForm, ProfilePhotoForm
from accounts.models import User
from accounts.permissions import admin_required
from camp.models import CampYear, TaxAddOn, TaxOverride, TaxTier
from camp.services import get_current_camp_year
from content.models import ContentPage, MediaItem, Menu, MenuItem
from core.models import SiteSettings
from payments.models import Payment, PaymentLog

from .forms import (
    AdminUserCreateForm,
    AdminUserEmailForm,
    AdminUserFlagsForm,
    CampYearCreateForm,
    CampYearPagesForm,
    ContentPageForm,
    MediaUploadAdminForm,
    MenuForm,
    MenuItemForm,
    TaxAddOnCreateForm,
    TaxOverrideCreateForm,
    TaxTierCreateForm,
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
    form = AdminUserCreateForm(request.POST or None)
    create_user_status_message = ""
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "User created.")
        return redirect("adminui:users")
    if request.method == "POST":
        create_user_status_message = _first_form_error_message(form)
    return render(
        request,
        "adminui/users.html",
        {
            "create_user_status_message": create_user_status_message,
            "users": User.objects.all(),
            "form": form,
        },
    )


@admin_required
@require_POST
def user_intro_email(request: HttpRequest) -> JsonResponse:
    form = AdminUserCreateForm(request.POST)
    if not form.is_valid():
        return JsonResponse(
            {
                "message": _first_form_error_message(form),
                "errors": form.errors.get_json_data(),
            },
            status=400,
        )

    first_name = form.cleaned_data["first_name"]
    last_name = form.cleaned_data["last_name"]
    email = form.cleaned_data["account_address"]
    full_name = f"{first_name} {last_name}".strip() or email
    body = render_to_string(
        "adminui/emails/new_user_intro.txt",
        {
            "email": email,
            "first_name": first_name,
            "full_name": full_name,
            "last_name": last_name,
            "login_url": request.build_absolute_uri("/login/"),
            "password": form.cleaned_data["initial_secret"],
        },
    )
    return JsonResponse({"body": body})


def _first_form_error_message(form: AdminUserCreateForm) -> str:
    for field_name, errors in form.errors.items():
        if not errors:
            continue
        if field_name == "__all__":
            return str(errors[0])
        field = form.fields.get(field_name)
        label = field.label if field is not None else field_name.replace("_", " ").title()
        return f"{label}: {errors[0]}"
    return "Fix the create user fields before continuing."


@admin_required
def user_edit(request: HttpRequest, user_id: int) -> HttpResponse:
    edited_user = get_object_or_404(User, pk=user_id)
    if edited_user.pk == request.user.pk:
        raise PermissionDenied("Current user cannot be edited.")

    flags_form = AdminUserFlagsForm(user=edited_user)
    email_form = AdminUserEmailForm(user=edited_user)
    password_form = SetPasswordForm(user=edited_user)
    photo_form = ProfilePhotoForm(user=edited_user)
    bio_form = ProfileBioForm(user=edited_user)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "flags":
            flags_form = AdminUserFlagsForm(request.POST, user=edited_user)
            if flags_form.is_valid():
                flags_form.save()
                messages.success(request, "User flags updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "email":
            email_form = AdminUserEmailForm(request.POST, user=edited_user)
            if email_form.is_valid():
                email_form.save()
                messages.success(request, "User email updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "password":
            password_form = SetPasswordForm(user=edited_user, data=request.POST)
            if password_form.is_valid():
                password_form.save()
                messages.success(request, "User password updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "photo":
            photo_form = ProfilePhotoForm(request.POST, request.FILES, user=edited_user)
            if photo_form.is_valid():
                photo_form.save()
                messages.success(request, "User photo updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)
        elif action == "bio":
            bio_form = ProfileBioForm(request.POST, user=edited_user)
            if bio_form.is_valid():
                bio_form.save()
                messages.success(request, "User bio updated.")
                return redirect("adminui:user-edit", user_id=edited_user.id)

    heading = edited_user.get_full_name() or edited_user.email
    return render(
        request,
        "adminui/user_edit.html",
        {
            "edited_user": edited_user,
            "heading": heading,
            "flags_form": flags_form,
            "email_form": email_form,
            "password_form": password_form,
            "photo_form": photo_form,
            "bio_form": bio_form,
        },
    )


@admin_required
def camp(request: HttpRequest) -> HttpResponse:
    form = CampYearCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        camp_year = form.save(commit=False)
        camp_year.created_by = request.user
        camp_year.updated_by = request.user
        camp_year.save()
        messages.success(request, "Camp year created.")
        return redirect(_camp_year_section_url(camp_year, "dashboard-pages"))

    return render(
        request,
        "adminui/camp.html",
        {
            "camp_year_form": form,
            "camp_years": _camp_year_summaries(),
        },
    )


@admin_required
def camp_year_edit(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(
        CampYear.objects.select_related("dashboard_pre_page", "dashboard_post_page"),
        year=year,
    )
    pages_form = CampYearPagesForm(instance=camp_year)
    tax_tier_form = TaxTierCreateForm(camp_year=camp_year)
    tax_add_on_form = TaxAddOnCreateForm(camp_year=camp_year)
    tax_override_form = TaxOverrideCreateForm(camp_year=camp_year)

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "pages":
            pages_form = CampYearPagesForm(request.POST, instance=camp_year)
            if pages_form.is_valid():
                updated_year = pages_form.save(commit=False)
                updated_year.updated_by = request.user
                updated_year.save()
                messages.success(request, "Dashboard pages updated.")
                return redirect(_camp_year_section_url(camp_year, "dashboard-pages"))
        elif action == "tax_tier":
            tax_tier_form = TaxTierCreateForm(request.POST, camp_year=camp_year)
            if tax_tier_form.is_valid():
                tax_tier = tax_tier_form.save(commit=False)
                tax_tier.created_by = request.user
                tax_tier.display_order = _next_display_order(TaxTier, camp_year)
                tax_tier.updated_by = request.user
                tax_tier.save()
                messages.success(request, "Tax tier created.")
                return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        elif action == "tax_tier_move_up":
            _move_ordered_item(TaxTier, camp_year, request.POST.get("item_id"), "up")
            return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        elif action == "tax_tier_move_down":
            _move_ordered_item(TaxTier, camp_year, request.POST.get("item_id"), "down")
            return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        elif action == "tax_add_on":
            tax_add_on_form = TaxAddOnCreateForm(request.POST, camp_year=camp_year)
            if tax_add_on_form.is_valid():
                tax_add_on = tax_add_on_form.save(commit=False)
                tax_add_on.created_by = request.user
                tax_add_on.display_order = _next_display_order(TaxAddOn, camp_year)
                tax_add_on.updated_by = request.user
                tax_add_on.save()
                messages.success(request, "Tax add-on created.")
                return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        elif action == "tax_add_on_move_up":
            _move_ordered_item(TaxAddOn, camp_year, request.POST.get("item_id"), "up")
            return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        elif action == "tax_add_on_move_down":
            _move_ordered_item(TaxAddOn, camp_year, request.POST.get("item_id"), "down")
            return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        elif action == "tax_override":
            tax_override_form = TaxOverrideCreateForm(request.POST, camp_year=camp_year)
            if tax_override_form.is_valid():
                tax_override = tax_override_form.save(commit=False)
                tax_override.created_by = request.user
                tax_override.updated_by = request.user
                tax_override.save()
                messages.success(request, "Tax override created.")
                return redirect(_camp_year_section_url(camp_year, "tax-overrides"))
        elif action == "tax_override_delete":
            tax_override = get_object_or_404(
                TaxOverride,
                pk=request.POST.get("override_id"),
                camp_year=camp_year,
            )
            tax_override.delete()
            messages.success(request, "Tax override deleted.")
            return redirect(_camp_year_section_url(camp_year, "tax-overrides"))

    return render(
        request,
        "adminui/camp_year_edit.html",
        {
            "camp_year": camp_year,
            "pages_form": pages_form,
            "tax_add_on_form": tax_add_on_form,
            "tax_add_ons": camp_year.tax_add_ons.order_by("display_order", "id"),
            "tax_override_form": tax_override_form,
            "tax_overrides": TaxOverride.objects.filter(camp_year=camp_year)
            .select_related("user")
            .order_by("user__email"),
            "tax_tier_form": tax_tier_form,
            "tax_tiers": camp_year.tax_tiers.order_by("display_order", "id"),
        },
    )


@admin_required
def camp_tax_tier_edit(request: HttpRequest, year: int, tier_id: int) -> HttpResponse:
    tax_tier = get_object_or_404(
        TaxTier.objects.select_related("camp_year"),
        pk=tier_id,
        camp_year__year=year,
    )
    form = TaxTierCreateForm(
        request.POST or None,
        camp_year=tax_tier.camp_year,
        instance=tax_tier,
    )
    if request.method == "POST":
        if request.POST.get("action") == "delete":
            camp_year = tax_tier.camp_year
            tax_tier.delete()
            messages.success(request, "Tax tier deleted.")
            return redirect(_camp_year_section_url(camp_year, "tax-tiers"))
        if form.is_valid():
            updated_tier = form.save(commit=False)
            updated_tier.updated_by = request.user
            updated_tier.save()
            messages.success(request, "Tax tier updated.")
            return redirect(_camp_year_section_url(tax_tier.camp_year, "tax-tiers"))

    return render(
        request,
        "adminui/camp_tax_tier_edit.html",
        {
            "camp_year": tax_tier.camp_year,
            "form": form,
            "tax_tier": tax_tier,
        },
    )


@admin_required
def camp_tax_add_on_edit(request: HttpRequest, year: int, add_on_id: int) -> HttpResponse:
    tax_add_on = get_object_or_404(
        TaxAddOn.objects.select_related("camp_year"),
        pk=add_on_id,
        camp_year__year=year,
    )
    form = TaxAddOnCreateForm(
        request.POST or None,
        camp_year=tax_add_on.camp_year,
        instance=tax_add_on,
    )
    if request.method == "POST":
        if request.POST.get("action") == "delete":
            camp_year = tax_add_on.camp_year
            tax_add_on.delete()
            messages.success(request, "Tax add-on deleted.")
            return redirect(_camp_year_section_url(camp_year, "tax-add-ons"))
        if form.is_valid():
            updated_add_on = form.save(commit=False)
            updated_add_on.updated_by = request.user
            updated_add_on.save()
            messages.success(request, "Tax add-on updated.")
            return redirect(_camp_year_section_url(tax_add_on.camp_year, "tax-add-ons"))

    return render(
        request,
        "adminui/camp_tax_add_on_edit.html",
        {
            "camp_year": tax_add_on.camp_year,
            "form": form,
            "tax_add_on": tax_add_on,
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
    return render(
        request,
        "adminui/pages.html",
        {"pages": ContentPage.objects.all(), "form": form},
    )


@admin_required
def page_edit(request: HttpRequest, slug: str) -> HttpResponse:
    page = get_object_or_404(ContentPage, slug=slug)
    form = ContentPageForm(request.POST or None, instance=page)

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            try:
                page.delete()
                messages.success(request, "Page deleted.")
                return redirect("adminui:pages")
            except ProtectedError:
                messages.error(request, "Page is in use and cannot be deleted.")
                return redirect("adminui:page-edit", slug=page.slug)

        if form.is_valid():
            updated_page = form.save()
            messages.success(request, "Page updated.")
            if request.POST.get("redirect_to") == "view":
                return redirect(updated_page.get_absolute_url())
            return redirect("adminui:pages")

    return render(
        request,
        "adminui/page_edit.html",
        {"form": form, "page": page},
    )


@admin_required
def menus(request: HttpRequest) -> HttpResponse:
    Menu.objects.get_or_create(menu_name=Menu.ROOT_MENU_NAME)
    menu_form = MenuForm()
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_menu":
            menu_form = MenuForm(request.POST)
            if menu_form.is_valid():
                menu = menu_form.save()
                messages.success(request, "Menu saved.")
                return redirect("adminui:menu-edit", menu_name=menu.menu_name)
    return render(
        request,
        "adminui/menus.html",
        {
            "menus": _menus_with_item_summaries(),
            "menu_form": menu_form,
        },
    )


@admin_required
def menu_edit(request: HttpRequest, menu_name: str) -> HttpResponse:
    menu = get_object_or_404(Menu, menu_name=menu_name)
    item_form = MenuItemForm()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_item":
            item_form = MenuItemForm(request.POST)
            if item_form.is_valid():
                item = item_form.save(commit=False)
                item.menu = menu
                item.display_order = _next_menu_item_display_order(menu)
                item.save()
                messages.success(request, "Menu item saved.")
                return redirect(_menu_section_url(menu, "menu-items"))
        elif action == "menu_item_move_up":
            _move_menu_item(menu, request.POST.get("item_id"), "up")
            return redirect(_menu_section_url(menu, "menu-items"))
        elif action == "menu_item_move_down":
            _move_menu_item(menu, request.POST.get("item_id"), "down")
            return redirect(_menu_section_url(menu, "menu-items"))
        elif action == "delete_menu":
            try:
                menu.delete()
                messages.success(request, "Menu deleted.")
                return redirect("adminui:menus")
            except ValidationError as error:
                messages.error(request, error.messages[0])
                return redirect("adminui:menu-edit", menu_name=menu.menu_name)

    return render(
        request,
        "adminui/menu_edit.html",
        {
            "item_form": item_form,
            "menu": menu,
            "menu_items": menu.items.order_by("display_order", "id"),
            "url_suggestions": _menu_url_suggestions(),
        },
    )


@admin_required
def menu_item_edit(request: HttpRequest, item_id: int) -> HttpResponse:
    menu_item = get_object_or_404(MenuItem.objects.select_related("menu"), pk=item_id)
    form = MenuItemForm(request.POST or None, instance=menu_item)

    if request.method == "POST":
        if request.POST.get("action") == "delete":
            menu = menu_item.menu
            menu_item.delete()
            messages.success(request, "Menu item deleted.")
            return redirect(_menu_section_url(menu, "menu-items"))
        if form.is_valid():
            form.save()
            messages.success(request, "Menu item updated.")
            return redirect(_menu_section_url(menu_item.menu, "menu-items"))

    return render(
        request,
        "adminui/menu_item_edit.html",
        {
            "form": form,
            "menu": menu_item.menu,
            "menu_item": menu_item,
            "url_suggestions": _menu_url_suggestions(),
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


def _camp_year_summaries() -> list[CampYear]:
    camp_years = list(
        CampYear.objects.annotate(
            override_count=Count("tax_overrides", distinct=True),
            tax_add_on_count=Count("tax_add_ons", distinct=True),
            tax_closes_at=Max("tax_tiers__expiration_date"),
            tax_opens_at=Min("tax_tiers__start_date"),
            tax_tier_count=Count("tax_tiers", distinct=True),
        ).order_by("-year"),
    )
    camp_year_ids = [camp_year.id for camp_year in camp_years]
    paid_user_ids = _user_ids_by_camp_year(
        Payment.objects.filter(
            camp_year_id__in=camp_year_ids,
            status=Payment.Status.PAID,
        ),
    )
    override_user_ids = _user_ids_by_camp_year(
        TaxOverride.objects.filter(camp_year_id__in=camp_year_ids),
    )
    waived_user_ids = _user_ids_by_camp_year(
        TaxOverride.objects.filter(
            camp_year_id__in=camp_year_ids,
            override_type=TaxOverride.OverrideType.WAIVED,
        ),
    )

    for camp_year in camp_years:
        paid_users = paid_user_ids.get(camp_year.id, set())
        override_users = override_user_ids.get(camp_year.id, set())
        camp_year.paid_count = len(paid_users)
        camp_year.people_count = len(paid_users | override_users)
        camp_year.waived_count = len(waived_user_ids.get(camp_year.id, set()))

    return camp_years


def _user_ids_by_camp_year(queryset) -> dict[int, set[int]]:
    user_ids: dict[int, set[int]] = {}
    for camp_year_id, user_id in queryset.values_list("camp_year_id", "user_id").distinct():
        user_ids.setdefault(camp_year_id, set()).add(user_id)
    return user_ids


def _camp_year_section_url(camp_year: CampYear, section_id: str) -> str:
    return reverse("adminui:camp-year-edit", kwargs={"year": camp_year.year}) + f"#{section_id}"


def _menu_section_url(menu: Menu, section_id: str) -> str:
    return reverse("adminui:menu-edit", kwargs={"menu_name": menu.menu_name}) + f"#{section_id}"


def _menus_with_item_summaries() -> list[Menu]:
    menus = list(Menu.objects.prefetch_related("items").order_by("menu_name"))
    for menu in menus:
        labels = [item.label for item in menu.items.all()]
        menu.item_summary = ", ".join(labels) if labels else "----"
    return menus


def _menu_url_suggestions() -> list[str]:
    suggestions = ["/dashboard/", "/profile/"]
    current_year = get_current_camp_year()
    if current_year is not None:
        suggestions.extend(
            [
                reverse("camp:dashboard", kwargs={"year": current_year.year}),
                reverse("camp:taxes", kwargs={"year": current_year.year}),
            ],
        )
    suggestions.extend(page.get_absolute_url() for page in ContentPage.objects.order_by("slug"))
    suggestions.extend(
        reverse("content:menu-detail", kwargs={"menu_name": menu.menu_name})
        for menu in Menu.objects.order_by("menu_name")
    )
    return list(dict.fromkeys(suggestions))


def _next_menu_item_display_order(menu: Menu) -> int:
    max_order = menu.items.aggregate(Max("display_order"))["display_order__max"]
    return (max_order or 0) + 1


def _move_menu_item(menu: Menu, item_id: str | None, direction: str) -> None:
    with transaction.atomic():
        item = get_object_or_404(
            MenuItem.objects.select_for_update(),
            pk=item_id,
            menu=menu,
        )
        items = list(
            MenuItem.objects.select_for_update()
            .filter(menu=menu)
            .order_by("display_order", "id"),
        )
        current_index = next(
            index for index, candidate in enumerate(items) if candidate.pk == item.pk
        )
        if direction == "up" and current_index > 0:
            swap_index = current_index - 1
        elif direction == "down" and current_index < len(items) - 1:
            swap_index = current_index + 1
        else:
            swap_index = current_index

        items[current_index], items[swap_index] = items[swap_index], items[current_index]
        for display_order, ordered_item in enumerate(items, start=1):
            if ordered_item.display_order != display_order:
                ordered_item.display_order = display_order
                ordered_item.save(update_fields=["display_order", "updated_at"])


def _next_display_order(model, camp_year: CampYear) -> int:
    max_order = model.objects.filter(camp_year=camp_year).aggregate(Max("display_order"))[
        "display_order__max"
    ]
    return (max_order or 0) + 1


def _move_ordered_item(model, camp_year: CampYear, item_id: str | None, direction: str) -> None:
    with transaction.atomic():
        item = get_object_or_404(
            model.objects.select_for_update(),
            pk=item_id,
            camp_year=camp_year,
        )
        items = list(
            model.objects.select_for_update()
            .filter(camp_year=camp_year)
            .order_by("display_order", "id"),
        )
        current_index = next(
            index for index, candidate in enumerate(items) if candidate.pk == item.pk
        )
        if direction == "up" and current_index > 0:
            swap_index = current_index - 1
        elif direction == "down" and current_index < len(items) - 1:
            swap_index = current_index + 1
        else:
            swap_index = current_index

        items[current_index], items[swap_index] = items[swap_index], items[current_index]
        for display_order, ordered_item in enumerate(items, start=1):
            if ordered_item.display_order != display_order:
                ordered_item.display_order = display_order
                ordered_item.save(update_fields=["display_order", "updated_at"])
