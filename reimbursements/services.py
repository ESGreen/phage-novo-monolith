from __future__ import annotations

from collections.abc import Collection
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone

from camp.models import CampYear

from .models import (
    Reimbursement,
    ReimbursementExpense,
    ReimbursementExpenseCategory,
    ReimbursementPayoutProfile,
    ReimbursementPayoutSnapshot,
    ReimbursementReceipt,
)
from .receipts import (
    MAX_RECEIPT_FILES,
    MAX_RECEIPT_TOTAL_SIZE_BYTES,
    build_receipt_relative_path,
    copy_receipt_file,
    delete_receipt_file,
    store_receipt_file,
    validate_receipt_upload,
)

User = get_user_model()


class ReimbursementError(Exception):
    pass


class ReimbursementConflictError(ReimbursementError):
    pass


def dollars_to_cents(amount: Decimal) -> int:
    return int((amount * Decimal("100")).quantize(Decimal("1")))


def _next_reimbursement_number(camp_year: CampYear) -> str:
    prefix = f"{camp_year.year}-R-"
    current = (
        Reimbursement.objects.filter(camp_year=camp_year, reimbursement_number__startswith=prefix)
        .order_by("-reimbursement_number")
        .values_list("reimbursement_number", flat=True)
        .first()
    )
    sequence = int(current.removeprefix(prefix)) + 1 if current else 1
    return f"{prefix}{sequence:04d}"


def create_reimbursement_draft(*, requester: User, camp_year: CampYear) -> Reimbursement:
    for attempt in range(2):
        try:
            with transaction.atomic():
                locked_year = CampYear.objects.select_for_update().get(pk=camp_year.pk)
                return Reimbursement.objects.create(
                    reimbursement_number=_next_reimbursement_number(locked_year),
                    camp_year=locked_year,
                    requester=requester,
                )
        except IntegrityError as exc:
            if attempt:
                raise ReimbursementError("Could not allocate a reimbursement number.") from exc
    raise AssertionError("unreachable")


def save_payout_profile(*, user: User, data: dict[str, object]) -> ReimbursementPayoutProfile:
    profile, _ = ReimbursementPayoutProfile.objects.get_or_create(
        user=user,
        defaults={"method": data.get("method") or ReimbursementPayoutProfile.Method.ZELLE},
    )
    for field in (
        "method",
        "zelle_email",
        "check_payee_name",
        "check_address_line_1",
        "check_address_line_2",
        "check_city",
        "check_state",
        "check_postal_code",
    ):
        setattr(profile, field, data.get(field, ""))
    profile.full_clean()
    profile.save()
    return profile


def add_expense(
    *,
    reimbursement: Reimbursement,
    requester: User,
    category: ReimbursementExpenseCategory,
    description: str,
    amount_cents: int,
) -> ReimbursementExpense:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        _require_editable(locked, requester)
        expense = ReimbursementExpense(
            reimbursement=locked,
            category=category,
            description=description,
            amount_cents=amount_cents,
        )
        expense.full_clean()
        expense.save()
        return expense


def delete_expense(*, expense: ReimbursementExpense, requester: User) -> None:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=expense.reimbursement_id)
        _require_editable(locked, requester)
        ReimbursementExpense.objects.filter(pk=expense.pk, reimbursement=locked).delete()


def _require_editable(reimbursement: Reimbursement, requester: User) -> None:
    if reimbursement.requester_id != requester.pk:
        raise ReimbursementConflictError("This reimbursement does not belong to you.")
    if reimbursement.status != Reimbursement.Status.DRAFT:
        raise ReimbursementConflictError("This reimbursement is no longer editable.")


def add_file_receipt(
    *,
    reimbursement: Reimbursement,
    requester: User,
    uploaded_file,
    explanation: str = "",
) -> ReimbursementReceipt:
    validated = validate_receipt_upload(uploaded_file)
    relative_path = ""
    try:
        with transaction.atomic():
            locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
            _require_editable(locked, requester)
            files = locked.receipts.exclude(
                receipt_type=ReimbursementReceipt.ReceiptType.EXPLANATION
            )
            if files.count() >= MAX_RECEIPT_FILES:
                raise ValidationError("A reimbursement may have at most 20 receipt files.")
            total_size = files.aggregate(total=Sum("size_bytes"))["total"] or 0
            if total_size + validated.size_bytes > MAX_RECEIPT_TOTAL_SIZE_BYTES:
                raise ValidationError("Receipt files may total at most 100 MB.")
            relative_path = build_receipt_relative_path(locked, validated.extension)
            store_receipt_file(uploaded_file, relative_path)
            receipt = ReimbursementReceipt(
                reimbursement=locked,
                receipt_type=validated.receipt_type,
                original_filename=validated.original_filename,
                file_path=relative_path,
                content_type=validated.content_type,
                size_bytes=validated.size_bytes,
                explanation=explanation.strip(),
            )
            receipt.full_clean()
            receipt.save()
            return receipt
    except Exception:
        if relative_path:
            delete_receipt_file(relative_path)
        raise


def add_explanation_receipt(
    *, reimbursement: Reimbursement, requester: User, explanation: str
) -> ReimbursementReceipt:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        _require_editable(locked, requester)
        receipt = ReimbursementReceipt(
            reimbursement=locked,
            receipt_type=ReimbursementReceipt.ReceiptType.EXPLANATION,
            explanation=explanation,
        )
        receipt.full_clean()
        receipt.save()
        return receipt


def delete_receipt(*, receipt: ReimbursementReceipt, requester: User) -> None:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=receipt.reimbursement_id)
        _require_editable(locked, requester)
        file_path = receipt.file_path
        receipt.delete()
        if file_path:
            transaction.on_commit(lambda: delete_receipt_file(file_path))


def update_requester_notes(
    *, reimbursement: Reimbursement, requester: User, requester_notes: str
) -> Reimbursement:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        _require_editable(locked, requester)
        locked.requester_notes = requester_notes.strip()
        locked.save(update_fields=["requester_notes"])
        return locked


def submit_reimbursement(*, reimbursement: Reimbursement, requester: User) -> Reimbursement:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        _require_editable(locked, requester)
        expenses = list(locked.expenses.select_related("category"))
        receipts = list(locked.receipts.all())
        if not expenses:
            raise ValidationError("Add at least one expense before submitting.")
        if not receipts:
            raise ValidationError("Add a receipt or explanation before submitting.")
        for expense in expenses:
            expense.full_clean()
        for receipt in receipts:
            receipt.full_clean()
        try:
            profile = ReimbursementPayoutProfile.objects.get(user=requester)
        except ReimbursementPayoutProfile.DoesNotExist as exc:
            raise ValidationError(
                "Add reimbursement payment information before submitting."
            ) from exc
        profile.full_clean()
        ReimbursementPayoutSnapshot.objects.create(
            reimbursement=locked,
            method=profile.method,
            zelle_email=profile.zelle_email,
            check_payee_name=profile.check_payee_name,
            check_address_line_1=profile.check_address_line_1,
            check_address_line_2=profile.check_address_line_2,
            check_city=profile.check_city,
            check_state=profile.check_state,
            check_postal_code=profile.check_postal_code,
        )
        locked.status = Reimbursement.Status.SUBMITTED
        locked.submitted_at = timezone.now()
        locked.save(update_fields=["status", "submitted_at"])
        return locked


def unsubmit_reimbursement(*, reimbursement: Reimbursement, requester: User) -> Reimbursement:
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        if locked.requester_id != requester.pk or locked.status != Reimbursement.Status.SUBMITTED:
            raise ReimbursementConflictError("This reimbursement can no longer be unsubmitted.")
        _move_to_draft(locked)
        return locked


def _move_to_draft(reimbursement: Reimbursement) -> None:
    reimbursement.status = Reimbursement.Status.DRAFT
    reimbursement.submitted_at = None
    reimbursement.rejected_at = None
    reimbursement.rejected_by = None
    ReimbursementPayoutSnapshot.objects.filter(reimbursement=reimbursement).delete()
    reimbursement.save(update_fields=["status", "submitted_at", "rejected_at", "rejected_by"])


def return_reimbursement_to_draft(
    *, reimbursement: Reimbursement, administrator: User
) -> Reimbursement:
    if not administrator.is_admin:
        raise ReimbursementConflictError("Admin access is required.")
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        if locked.status not in (Reimbursement.Status.SUBMITTED, Reimbursement.Status.REJECTED):
            raise ReimbursementConflictError("This reimbursement cannot be moved to draft.")
        _move_to_draft(locked)
        return locked


def reject_reimbursement(
    *, reimbursement: Reimbursement, administrator: User, payer_notes: str
) -> Reimbursement:
    if not administrator.is_admin:
        raise ReimbursementConflictError("Admin access is required.")
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        if locked.status != Reimbursement.Status.SUBMITTED:
            raise ReimbursementConflictError("This reimbursement is no longer submitted.")
        locked.status = Reimbursement.Status.REJECTED
        locked.rejected_at = timezone.now()
        locked.rejected_by = administrator
        locked.payer_notes = payer_notes.strip()
        locked.save(update_fields=["status", "rejected_at", "rejected_by", "payer_notes"])
        return locked


def restore_reimbursement_to_submitted(
    *, reimbursement: Reimbursement, administrator: User
) -> Reimbursement:
    if not administrator.is_admin:
        raise ReimbursementConflictError("Admin access is required.")
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        if locked.status != Reimbursement.Status.REJECTED:
            raise ReimbursementConflictError("This reimbursement is no longer rejected.")
        locked.status = Reimbursement.Status.SUBMITTED
        locked.rejected_at = None
        locked.rejected_by = None
        locked.save(update_fields=["status", "rejected_at", "rejected_by"])
        return locked


def mark_reimbursement_paid(
    *,
    reimbursement: Reimbursement,
    administrator: User,
    payer_notes: str,
) -> Reimbursement:
    if not administrator.is_admin:
        raise ReimbursementConflictError("Admin access is required.")
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        if locked.status != Reimbursement.Status.SUBMITTED:
            raise ReimbursementConflictError("This reimbursement is no longer submitted.")
        if locked.total_amount_cents <= 0 or not hasattr(locked, "payout_snapshot"):
            raise ReimbursementConflictError("This reimbursement is not ready for payment.")
        locked.status = Reimbursement.Status.PAID
        locked.paid_at = timezone.now()
        locked.paid_by = administrator
        locked.payer_notes = payer_notes.strip()
        locked.save(update_fields=["status", "paid_at", "paid_by", "payer_notes"])
        return locked


def update_payer_notes(
    *, reimbursement: Reimbursement, administrator: User, payer_notes: str
) -> Reimbursement:
    if not administrator.is_admin:
        raise ReimbursementConflictError("Admin access is required.")
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        locked.payer_notes = payer_notes.strip()
        locked.save(update_fields=["payer_notes"])
        return locked


def delete_reimbursement_draft(
    *, reimbursement: Reimbursement, requester: User, confirmation: str
) -> None:
    if confirmation.strip().lower() != "delete":
        raise ValidationError("Type delete to confirm.")
    with transaction.atomic():
        locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
        _require_editable(locked, requester)
        paths = list(locked.receipts.exclude(file_path="").values_list("file_path", flat=True))
        locked.delete()
        transaction.on_commit(lambda: [delete_receipt_file(path) for path in paths])


def split_reimbursement(
    *,
    reimbursement: Reimbursement,
    administrator: User,
    expense_ids: Collection[int],
    rationale: str,
) -> Reimbursement:
    rationale = rationale.strip()
    selected_ids = set(expense_ids)
    if not administrator.is_admin or not rationale:
        raise ValidationError("Select expenses and enter split notes.")

    copied_paths: list[str] = []
    try:
        with transaction.atomic():
            locked = Reimbursement.objects.select_for_update().get(pk=reimbursement.pk)
            if locked.status != Reimbursement.Status.SUBMITTED:
                raise ReimbursementConflictError("This reimbursement is no longer submitted.")
            expenses = list(locked.expenses.select_for_update())
            available_ids = {expense.id for expense in expenses}
            if (
                not selected_ids
                or not selected_ids <= available_ids
                or selected_ids == available_ids
            ):
                raise ValidationError("Select some, but not all, expenses to split.")

            child = create_reimbursement_draft(
                requester=locked.requester,
                camp_year=locked.camp_year,
            )
            child.split_from = locked
            child.requester_notes = locked.requester_notes
            child.payer_notes = rationale
            child.full_clean()
            child.save(update_fields=["split_from", "requester_notes", "payer_notes"])

            for receipt in locked.receipts.all():
                if receipt.receipt_type == ReimbursementReceipt.ReceiptType.EXPLANATION:
                    ReimbursementReceipt.objects.create(
                        reimbursement=child,
                        receipt_type=receipt.receipt_type,
                        explanation=receipt.explanation,
                    )
                    continue
                extension = Path(receipt.file_path).suffix
                destination = build_receipt_relative_path(child, extension)
                copy_receipt_file(receipt.file_path, destination)
                copied_paths.append(destination)
                ReimbursementReceipt.objects.create(
                    reimbursement=child,
                    receipt_type=receipt.receipt_type,
                    original_filename=receipt.original_filename,
                    file_path=destination,
                    content_type=receipt.content_type,
                    size_bytes=receipt.size_bytes,
                )

            ReimbursementExpense.objects.filter(id__in=selected_ids).update(reimbursement=child)
            return child
    except Exception:
        for path in copied_paths:
            delete_receipt_file(path)
        raise
