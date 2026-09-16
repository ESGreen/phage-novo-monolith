from __future__ import annotations

from dataclasses import dataclass

from django.db.models import Q, Sum
from django.db.models.functions import Coalesce, Lower

from camp.models import CampYear

from .models import Reimbursement, ReimbursementExpense, ReimbursementExpenseCategory


@dataclass(frozen=True)
class CategoryExpenseTotals:
    category_name: str
    submitted_amount_cents: int
    paid_amount_cents: int


def expenses_by_category(*, camp_year: CampYear) -> list[CategoryExpenseTotals]:
    rows = (
        ReimbursementExpenseCategory.objects.filter(camp_year=camp_year)
        .annotate(
            submitted_amount_cents=Coalesce(
                Sum(
                    "expenses__amount_cents",
                    filter=Q(expenses__reimbursement__status=Reimbursement.Status.SUBMITTED),
                ),
                0,
            ),
            paid_amount_cents=Coalesce(
                Sum(
                    "expenses__amount_cents",
                    filter=Q(expenses__reimbursement__status=Reimbursement.Status.PAID),
                ),
                0,
            ),
        )
        .filter(Q(submitted_amount_cents__gt=0) | Q(paid_amount_cents__gt=0))
        .order_by(Lower("name"), "id")
    )
    return [
        CategoryExpenseTotals(row.name, row.submitted_amount_cents, row.paid_amount_cents)
        for row in rows
    ]


def paid_expenses_by_person(*, camp_year: CampYear) -> list[dict[str, object]]:
    return list(
        ReimbursementExpense.objects.filter(
            reimbursement__camp_year=camp_year,
            reimbursement__status=Reimbursement.Status.PAID,
        )
        .values(
            "reimbursement__requester_id",
            "reimbursement__requester__first_name",
            "reimbursement__requester__last_name",
            "reimbursement__requester__email",
            "category_id",
            "category__name",
        )
        .annotate(amount_cents=Sum("amount_cents"))
        .order_by(
            Lower("reimbursement__requester__last_name"),
            Lower("reimbursement__requester__first_name"),
            Lower("reimbursement__requester__email"),
            Lower("category__name"),
            "category_id",
        )
    )


def neutralize_spreadsheet_text(value: str) -> str:
    stripped = value.lstrip()
    if stripped.startswith(("=", "+", "-", "@")):
        return f"'{value}"
    return value


def paid_expenses_export_rows(*, camp_year: CampYear) -> list[list[str]]:
    rows = [["Member", "Category", "Amount Paid"]]
    total = 0
    for row in paid_expenses_by_person(camp_year=camp_year):
        name = (
            f"{row['reimbursement__requester__first_name']} "
            f"{row['reimbursement__requester__last_name']}"
        ).strip() or str(row["reimbursement__requester__email"])
        amount_cents = int(row["amount_cents"])
        total += amount_cents
        rows.append(
            [
                neutralize_spreadsheet_text(name),
                neutralize_spreadsheet_text(str(row["category__name"])),
                f"{amount_cents / 100:.2f}",
            ]
        )
    rows.append(["Total", "", f"{total / 100:.2f}"])
    return rows
