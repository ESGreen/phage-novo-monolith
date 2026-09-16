from __future__ import annotations

import csv
from urllib.parse import quote

from django.contrib import messages
from django.db.models import Sum
from django.http import FileResponse, Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST

from accounts.permissions import admin_required, member_required
from camp.models import CampYear
from camp.services import get_current_camp_year

from .forms import (
    ReimbursementDeleteForm,
    ReimbursementExpenseCreateForm,
    ReimbursementPayerNotesForm,
    ReimbursementPaymentForm,
    ReimbursementPayoutProfileForm,
    ReimbursementReceiptExplanationForm,
    ReimbursementReceiptUploadForm,
    ReimbursementRequesterNotesForm,
    ReimbursementSplitForm,
)
from .models import (
    Reimbursement,
    ReimbursementExpense,
    ReimbursementPayoutProfile,
    ReimbursementReceipt,
)
from .receipts import receipt_absolute_path
from .reports import expenses_by_category, paid_expenses_by_person, paid_expenses_export_rows
from .services import (
    ReimbursementConflictError,
    add_expense,
    add_explanation_receipt,
    add_file_receipt,
    create_reimbursement_draft,
    delete_expense,
    delete_receipt,
    delete_reimbursement_draft,
    mark_reimbursement_paid,
    reject_reimbursement,
    restore_reimbursement_to_submitted,
    return_reimbursement_to_draft,
    save_payout_profile,
    split_reimbursement,
    submit_reimbursement,
    unsubmit_reimbursement,
    update_payer_notes,
    update_requester_notes,
)


def _member_reimbursement(
    request: HttpRequest, year: int, reimbursement_number: str
) -> Reimbursement:
    return get_object_or_404(
        Reimbursement.objects.select_related("camp_year", "requester"),
        camp_year__year=year,
        reimbursement_number=reimbursement_number,
        requester=request.user,
    )


def _admin_reimbursement(year: int, reimbursement_number: str) -> Reimbursement:
    return get_object_or_404(
        Reimbursement.objects.select_related("camp_year", "requester"),
        camp_year__year=year,
        reimbursement_number=reimbursement_number,
    )


def _detail_url(reimbursement: Reimbursement, fragment: str = "") -> str:
    url = reverse(
        "reimbursements:member-detail",
        kwargs={
            "year": reimbursement.camp_year.year,
            "reimbursement_number": reimbursement.reimbursement_number,
        },
    )
    return f"{url}#{fragment}" if fragment else url


def _admin_year_url(year: int, fragment: str = "") -> str:
    url = reverse("reimbursements:admin-year", kwargs={"year": year})
    return f"{url}#{fragment}" if fragment else url


@member_required
def member_current(request: HttpRequest) -> HttpResponse:
    camp_year = get_current_camp_year()
    if camp_year is None:
        return render(request, "reimbursements/member_no_year.html")
    return redirect("reimbursements:member-list", year=camp_year.year)


@member_required
def member_list(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear, year=year)
    reimbursements = (
        Reimbursement.objects.filter(
            camp_year=camp_year,
            requester=request.user,
        )
        .annotate(total_cents=Sum("expenses__amount_cents"))
        .order_by("-created_at", "-reimbursement_number")
    )
    return render(
        request,
        "reimbursements/member_overview.html",
        {"camp_year": camp_year, "reimbursements": reimbursements},
    )


@member_required
@require_POST
def member_create(request: HttpRequest, year: int) -> HttpResponse:
    reimbursement = create_reimbursement_draft(
        requester=request.user,
        camp_year=get_object_or_404(CampYear, year=year),
    )
    messages.success(request, "Reimbursement created.")
    return redirect(_detail_url(reimbursement))


@member_required
def member_detail(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    profile = ReimbursementPayoutProfile.objects.filter(user=request.user).first()
    return render(
        request,
        "reimbursements/member_detail.html",
        {
            "reimbursement": reimbursement,
            "expenses": reimbursement.expenses.select_related("category"),
            "receipts": reimbursement.receipts.all(),
            "payout_form": ReimbursementPayoutProfileForm(user=request.user, instance=profile),
            "expense_form": ReimbursementExpenseCreateForm(reimbursement=reimbursement),
            "upload_form": ReimbursementReceiptUploadForm(),
            "explanation_form": ReimbursementReceiptExplanationForm(),
            "notes_form": ReimbursementRequesterNotesForm(
                initial={"requester_notes": reimbursement.requester_notes}
            ),
            "delete_form": ReimbursementDeleteForm(),
        },
    )


@member_required
@require_POST
def member_save_payout(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    if reimbursement.status != Reimbursement.Status.DRAFT:
        raise Http404
    profile = ReimbursementPayoutProfile.objects.filter(user=request.user).first()
    form = ReimbursementPayoutProfileForm(request.POST, user=request.user, instance=profile)
    if form.is_valid():
        save_payout_profile(user=request.user, data=form.cleaned_data)
        messages.success(request, "Reimbursement payment information updated.")
    else:
        messages.error(request, next(iter(form.errors.values()))[0])
    return redirect(_detail_url(reimbursement, "payment-method"))


@member_required
@require_POST
def member_add_expense(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    form = ReimbursementExpenseCreateForm(request.POST, reimbursement=reimbursement)
    if form.is_valid():
        add_expense(
            reimbursement=reimbursement,
            requester=request.user,
            category=form.cleaned_data["category"],
            description=form.cleaned_data["description"],
            amount_cents=form.amount_cents,
        )
        messages.success(request, "Expense added.")
    else:
        messages.error(request, "Fix the expense fields before adding it.")
    return redirect(_detail_url(reimbursement, "expenses"))


@member_required
@require_POST
def member_delete_expense(
    request: HttpRequest, year: int, reimbursement_number: str, expense_id: int
) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    expense = get_object_or_404(ReimbursementExpense, pk=expense_id, reimbursement=reimbursement)
    delete_expense(expense=expense, requester=request.user)
    messages.success(request, "Expense deleted.")
    return redirect(_detail_url(reimbursement, "expenses"))


@member_required
@require_POST
def member_upload_receipt(
    request: HttpRequest, year: int, reimbursement_number: str
) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    form = ReimbursementReceiptUploadForm(request.POST, request.FILES)
    if form.is_valid():
        try:
            add_file_receipt(
                reimbursement=reimbursement,
                requester=request.user,
                uploaded_file=form.cleaned_data["file"],
                explanation=form.cleaned_data["explanation"],
            )
            messages.success(request, "Receipt uploaded.")
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect(_detail_url(reimbursement, "receipts"))


@member_required
@require_POST
def member_add_explanation(
    request: HttpRequest, year: int, reimbursement_number: str
) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    form = ReimbursementReceiptExplanationForm(request.POST)
    if form.is_valid():
        add_explanation_receipt(
            reimbursement=reimbursement,
            requester=request.user,
            explanation=form.cleaned_data["explanation"],
        )
        messages.success(request, "Explanation added.")
    return redirect(_detail_url(reimbursement, "receipts"))


@member_required
@require_POST
def member_delete_receipt(
    request: HttpRequest, year: int, reimbursement_number: str, receipt_id: int
) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    receipt = get_object_or_404(ReimbursementReceipt, pk=receipt_id, reimbursement=reimbursement)
    delete_receipt(receipt=receipt, requester=request.user)
    messages.success(request, "Receipt deleted.")
    return redirect(_detail_url(reimbursement, "receipts"))


@member_required
def receipt_file(
    request: HttpRequest, year: int, reimbursement_number: str, receipt_id: int
) -> HttpResponse:
    query = ReimbursementReceipt.objects.select_related("reimbursement", "reimbursement__camp_year")
    if not request.user.is_admin:
        query = query.filter(reimbursement__requester=request.user)
    receipt = get_object_or_404(
        query,
        pk=receipt_id,
        reimbursement__camp_year__year=year,
        reimbursement__reimbursement_number=reimbursement_number,
    )
    if not receipt.file_path:
        raise Http404
    path = receipt_absolute_path(receipt.file_path)
    if not path.is_file():
        raise Http404
    response = FileResponse(path.open("rb"), content_type=receipt.content_type)
    disposition = (
        "attachment" if receipt.receipt_type == ReimbursementReceipt.ReceiptType.PDF else "inline"
    )
    ascii_name = receipt.original_filename.encode("ascii", "ignore").decode() or "receipt"
    ascii_name = ascii_name.replace('"', "").replace("\\", "")
    encoded_name = quote(receipt.original_filename)
    response["Content-Disposition"] = (
        f"{disposition}; filename=\"{ascii_name}\"; filename*=UTF-8''{encoded_name}"
    )
    response["X-Content-Type-Options"] = "nosniff"
    response["Cache-Control"] = "private, no-store"
    return response


@member_required
@require_POST
def member_save_notes(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    form = ReimbursementRequesterNotesForm(request.POST)
    if form.is_valid():
        update_requester_notes(
            reimbursement=reimbursement,
            requester=request.user,
            requester_notes=form.cleaned_data["requester_notes"],
        )
        messages.success(request, "Notes updated.")
    return redirect(_detail_url(reimbursement, "requester-notes"))


@member_required
@require_POST
def member_submit(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    try:
        submit_reimbursement(reimbursement=reimbursement, requester=request.user)
        messages.success(request, "Reimbursement submitted.")
    except Exception as exc:
        messages.error(request, str(exc))
    return redirect(_detail_url(reimbursement))


@member_required
@require_POST
def member_unsubmit(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    try:
        unsubmit_reimbursement(reimbursement=reimbursement, requester=request.user)
        messages.success(request, "Reimbursement returned to draft.")
    except ReimbursementConflictError as exc:
        messages.error(request, str(exc))
    return redirect(_detail_url(reimbursement))


@member_required
@require_POST
def member_delete(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _member_reimbursement(request, year, reimbursement_number)
    form = ReimbursementDeleteForm(request.POST)
    if form.is_valid():
        delete_reimbursement_draft(
            reimbursement=reimbursement,
            requester=request.user,
            confirmation=form.cleaned_data["confirmation"],
        )
        messages.success(request, "Reimbursement deleted.")
        return redirect("reimbursements:member-list", year=year)
    messages.error(request, "Type delete to confirm.")
    return redirect(_detail_url(reimbursement, "delete-reimbursement"))


@admin_required
def admin_current(request: HttpRequest) -> HttpResponse:
    year_value = request.GET.get("year")
    if year_value is not None:
        if not year_value.isdigit() or len(year_value) != 4:
            raise Http404
        camp_year = get_object_or_404(CampYear, year=int(year_value))
    else:
        camp_year = get_current_camp_year()
        if camp_year is None:
            return render(request, "reimbursements/admin_no_year.html")
    return redirect("reimbursements:admin-year", year=camp_year.year)


@admin_required
def admin_year(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear, year=year)
    category_rows = expenses_by_category(camp_year=camp_year)
    person_rows = paid_expenses_by_person(camp_year=camp_year)
    base = Reimbursement.objects.filter(camp_year=camp_year).select_related("requester")
    context = {
        "camp_year": camp_year,
        "camp_years": CampYear.objects.order_by("-year"),
        "category_rows": category_rows,
        "category_submitted_total": sum(row.submitted_amount_cents for row in category_rows),
        "category_paid_total": sum(row.paid_amount_cents for row in category_rows),
        "person_rows": person_rows,
        "person_total": sum(int(row["amount_cents"]) for row in person_rows),
        "submitted_reimbursements": base.filter(status=Reimbursement.Status.SUBMITTED)
        .annotate(total_cents=Sum("expenses__amount_cents"))
        .order_by("submitted_at", "reimbursement_number"),
        "paid_reimbursements": base.filter(status=Reimbursement.Status.PAID)
        .annotate(total_cents=Sum("expenses__amount_cents"))
        .order_by("-paid_at", "reimbursement_number"),
        "rejected_reimbursements": base.filter(status=Reimbursement.Status.REJECTED)
        .annotate(total_cents=Sum("expenses__amount_cents"))
        .order_by("-rejected_at", "reimbursement_number"),
    }
    return render(request, "reimbursements/admin_annual.html", context)


@admin_required
def admin_paid_expenses_csv(request: HttpRequest, year: int) -> HttpResponse:
    camp_year = get_object_or_404(CampYear, year=year)
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = (
        f'attachment; filename="reimbursements-{year}-paid-expenses.csv"'
    )
    response["Cache-Control"] = "private, no-store"
    response["X-Content-Type-Options"] = "nosniff"
    writer = csv.writer(response)
    writer.writerows(paid_expenses_export_rows(camp_year=camp_year))
    return response


@admin_required
def admin_detail(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    categories = (
        reimbursement.expenses.select_related("category")
        .values_list("category__name", flat=True)
        .distinct()
    )
    return render(
        request,
        "reimbursements/admin_detail.html",
        {
            "reimbursement": reimbursement,
            "categories": sorted(categories, key=str.casefold),
            "expenses": reimbursement.expenses.select_related("category"),
            "receipts": reimbursement.receipts.all(),
            "notes_form": ReimbursementPayerNotesForm(
                initial={"payer_notes": reimbursement.payer_notes}
            ),
            "payment_form": ReimbursementPaymentForm(
                initial={"payer_notes": reimbursement.payer_notes}
            ),
            "split_form": ReimbursementSplitForm(reimbursement=reimbursement),
        },
    )


@admin_required
@require_POST
def admin_save_notes(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    form = ReimbursementPayerNotesForm(request.POST)
    if form.is_valid():
        update_payer_notes(
            reimbursement=reimbursement,
            administrator=request.user,
            payer_notes=form.cleaned_data["payer_notes"],
        )
        messages.success(request, "Admin notes updated.")
    detail_url = reverse(
        "reimbursements:admin-detail",
        kwargs={"year": year, "reimbursement_number": reimbursement_number},
    )
    return redirect(f"{detail_url}#notes")


@admin_required
@require_POST
def admin_split(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    form = ReimbursementSplitForm(request.POST, reimbursement=reimbursement)
    if form.is_valid():
        try:
            child = split_reimbursement(
                reimbursement=reimbursement,
                administrator=request.user,
                expense_ids=form.cleaned_data["expenses"].values_list("id", flat=True),
                rationale=form.cleaned_data["rationale"],
            )
            messages.success(
                request,
                "Selected expenses were moved to draft reimbursement "
                f"{child.reimbursement_number}.",
            )
        except Exception as exc:
            messages.error(request, str(exc))
    return redirect(
        "reimbursements:admin-detail", year=year, reimbursement_number=reimbursement_number
    )


@admin_required
@require_POST
def admin_pay(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    form = ReimbursementPaymentForm(request.POST)
    if form.is_valid():
        try:
            mark_reimbursement_paid(
                reimbursement=reimbursement,
                administrator=request.user,
                payer_notes=form.cleaned_data["payer_notes"],
            )
            messages.success(request, "Reimbursement marked paid.")
        except ReimbursementConflictError as exc:
            messages.error(request, str(exc))
    return redirect(_admin_year_url(year, "SubmittedReimbursements"))


@admin_required
@require_POST
def admin_reject(request: HttpRequest, year: int, reimbursement_number: str) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    form = ReimbursementPayerNotesForm(request.POST)
    if form.is_valid():
        try:
            reject_reimbursement(
                reimbursement=reimbursement,
                administrator=request.user,
                payer_notes=form.cleaned_data["payer_notes"],
            )
            messages.success(request, "Reimbursement rejected.")
        except ReimbursementConflictError as exc:
            messages.error(request, str(exc))
    return redirect(_admin_year_url(year, "SubmittedReimbursements"))


@admin_required
@require_POST
def admin_return_to_draft(
    request: HttpRequest, year: int, reimbursement_number: str
) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    try:
        return_reimbursement_to_draft(reimbursement=reimbursement, administrator=request.user)
        messages.success(request, "Reimbursement returned to draft.")
    except ReimbursementConflictError as exc:
        messages.error(request, str(exc))
    return redirect(_admin_year_url(year, "SubmittedReimbursements"))


@admin_required
@require_POST
def admin_restore_submitted(
    request: HttpRequest, year: int, reimbursement_number: str
) -> HttpResponse:
    reimbursement = _admin_reimbursement(year, reimbursement_number)
    try:
        restore_reimbursement_to_submitted(reimbursement=reimbursement, administrator=request.user)
        messages.success(request, "Reimbursement moved to submitted.")
    except ReimbursementConflictError as exc:
        messages.error(request, str(exc))
    return redirect(_admin_year_url(year, "SubmittedReimbursements"))
