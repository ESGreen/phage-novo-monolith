from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect, render

from accounts.permissions import member_required
from content.markdown import render_markdown
from payments.checkout import (
    CheckoutBlocked,
    create_tax_checkout,
    get_paid_payment,
    get_unexpired_created_payment,
)
from payments.models import Payment

from .forms import TaxSelectionForm
from .models import CampYear
from .services import get_current_camp_year
from .taxes import (
    available_tax_add_ons,
    available_tax_tiers,
    get_tax_override,
    is_tax_waived,
)


@member_required
def dashboard_redirect(request: HttpRequest) -> HttpResponse:
    camp_year = get_current_camp_year()
    if camp_year is None:
        return render(request, "camp/no_camp_year.html")
    return redirect("camp:dashboard", year=camp_year.year)


@member_required
def year_redirect(request: HttpRequest, year: int) -> HttpResponseRedirect:
    get_object_or_404(CampYear, year=year)
    return redirect("camp:dashboard", year=year)


@member_required
def dashboard(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(
        CampYear.objects.select_related("dashboard_pre_page", "dashboard_post_page"),
        year=year,
    )
    pre_html = ""
    post_html = ""
    if camp_year.dashboard_pre_page:
        pre_html = render_markdown(camp_year.dashboard_pre_page.body_markdown)
    if camp_year.dashboard_post_page:
        post_html = render_markdown(camp_year.dashboard_post_page.body_markdown)
    tax_status = "Waived" if is_tax_waived(request.user, camp_year) else "Not paid"

    return render(
        request,
        "camp/dashboard.html",
        {
            "camp_year": camp_year,
            "pre_html": pre_html,
            "post_html": post_html,
            "tax_status": tax_status,
        },
    )


@member_required
def taxes(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear, year=year)
    tax_override = get_tax_override(request.user, camp_year)
    waived = tax_override is not None and is_tax_waived(request.user, camp_year)
    paid_payment = get_paid_payment(request.user, camp_year)
    blocking_payment = get_unexpired_created_payment(request.user, camp_year)
    available_tiers = available_tax_tiers(camp_year)
    available_add_ons = available_tax_add_ons(camp_year)
    form = None

    if (
        paid_payment is None
        and blocking_payment is None
        and not waived
        and available_tiers.exists()
    ):
        if request.method == "POST":
            form = TaxSelectionForm(request.POST, user=request.user, camp_year=camp_year)
            if form.is_valid():
                try:
                    checkout_result = create_tax_checkout(request.user, camp_year, form)
                except CheckoutBlocked as error:
                    messages.error(request, str(error))
                    return redirect("camp:taxes", year=camp_year.year)
                return redirect(checkout_result.checkout_url)
        else:
            form = TaxSelectionForm(user=request.user, camp_year=camp_year)

    return render(
        request,
        "camp/taxes.html",
        {
            "camp_year": camp_year,
            "tax_override": tax_override,
            "waived": waived,
            "paid_payment": paid_payment,
            "blocking_payment": blocking_payment,
            "available_tiers": available_tiers,
            "available_add_ons": available_add_ons,
            "form": form,
        },
    )


@member_required
def taxes_return(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear, year=year)
    session_id = request.GET.get("session_id", "")
    payment = None
    if session_id:
        payment = Payment.objects.filter(
            user=request.user,
            camp_year=camp_year,
            stripe_checkout_session_id=session_id,
        ).first()
    return render(
        request,
        "camp/taxes_return.html",
        {"camp_year": camp_year, "payment": payment, "session_id": session_id},
    )
