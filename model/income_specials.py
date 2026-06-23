"""Hilfslogik für besondere Einkommen wie den 13. Monatslohn.

Die normale Forecast-Engine soll ein einmaliges, planbares Einkommen nicht wie
monatliches Einkommen lernen. Deshalb bekommt der 13. Monatslohn eine eigene
Einkommenskategorie mit genau einem budgetierten Auszahlungsmonat.
"""

from __future__ import annotations

from dataclasses import dataclass
import sqlite3

from model.budget_model import BudgetModel
from model.category_forecast_mode import FORECAST_MODE_INCREMENTAL
from model.category_model import CategoryModel
from model.typ_constants import TYP_INCOME

DEFAULT_13TH_SALARY_CATEGORY = "13. Monatslohn"


@dataclass(frozen=True)
class ThirteenthSalaryPlan:
    year: int
    payout_month: int
    amount: float
    category: str = DEFAULT_13TH_SALARY_CATEGORY


def apply_13th_month_salary(
    conn: sqlite3.Connection,
    *,
    year: int,
    payout_month: int,
    amount: float,
    category: str = DEFAULT_13TH_SALARY_CATEGORY,
    recurring_day: int = 25,
    clear_other_months: bool = True,
) -> ThirteenthSalaryPlan:
    """Trägt den 13. Monatslohn als planbares Einmaleinkommen ein.

    Fachregel:
    - eigene Einkommenskategorie, damit der normale Monatslohn sauber bleibt
    - nur der Auszahlungsmonat erhält den Betrag
    - andere Monate werden auf 0 gesetzt, damit der Betrag nicht versehentlich
      als monatlich wiederkehrendes Einkommen interpretiert wird
    """
    y = int(year)
    m = int(payout_month)
    if m < 1 or m > 12:
        raise ValueError("payout_month must be between 1 and 12")
    value = float(amount or 0.0)
    if value <= 0:
        raise ValueError("amount must be greater than zero")
    cat = (
        category or DEFAULT_13TH_SALARY_CATEGORY
    ).strip() or DEFAULT_13TH_SALARY_CATEGORY
    day = max(1, min(31, int(recurring_day or 25)))

    CategoryModel(conn).upsert(
        TYP_INCOME,
        cat,
        is_fix=True,
        is_recurring=False,
        recurring_day=day,
        forecast_mode=FORECAST_MODE_INCREMENTAL,
    )
    budget = BudgetModel(conn)
    months = range(1, 13) if clear_other_months else (m,)
    for month in months:
        budget.set_amount(y, month, TYP_INCOME, cat, value if month == m else 0.0)

    return ThirteenthSalaryPlan(year=y, payout_month=m, amount=value, category=cat)
