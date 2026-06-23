from __future__ import annotations

"""Deckungslogik für Budget- und Tracking-Warnungen.

Eine Planung bzw. ein Zeitraum ist nicht gedeckt, wenn
Einkommen < Ausgaben + Ersparnisse ist. Die Logik liegt bewusst im Model,
damit Budget-Tab und Tracking-Tab dieselbe Berechnung nutzen.
"""

from dataclasses import dataclass
from typing import Iterable, Mapping

from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS

EPS = 1e-6


@dataclass(frozen=True)
class SavingsSuggestion:
    category: str
    amount: float


@dataclass(frozen=True)
class CoverageResult:
    income: float
    expenses: float
    savings: float
    savings_by_category: Mapping[str, float]

    @property
    def balance(self) -> float:
        return float(self.income) - float(self.expenses) - float(self.savings)

    @property
    def deficit(self) -> float:
        return max(0.0, -self.balance)

    @property
    def is_overdrawn(self) -> bool:
        return self.balance < -EPS

    def single_savings_suggestions(self) -> list[SavingsSuggestion]:
        """Ersparnis-Kategorien, die den Fehlbetrag alleine decken könnten."""
        if not self.is_overdrawn:
            return []
        needed = self.deficit
        out = [
            SavingsSuggestion(str(cat), float(amount))
            for cat, amount in self.savings_by_category.items()
            if float(amount) >= needed - EPS
        ]
        return sorted(out, key=lambda s: (-s.amount, s.category.casefold()))

    def combined_savings_suggestions(self) -> list[SavingsSuggestion]:
        """Kleinster transparenter Vorschlag: größte Sparpositionen bis gedeckt."""
        if not self.is_overdrawn:
            return []
        remaining = self.deficit
        out: list[SavingsSuggestion] = []
        for cat, amount in sorted(
            (
                (str(c), float(a))
                for c, a in self.savings_by_category.items()
                if float(a) > EPS
            ),
            key=lambda kv: (-kv[1], kv[0].casefold()),
        ):
            take = min(amount, remaining)
            if take <= EPS:
                continue
            out.append(SavingsSuggestion(cat, take))
            remaining -= take
            if remaining <= EPS:
                break
        if remaining > EPS:
            return []
        return out


@dataclass(frozen=True)
class BudgetYearCoverage:
    year: int
    months: Mapping[int, CoverageResult]
    annual: CoverageResult

    @property
    def negative_months(self) -> list[int]:
        return [m for m, res in sorted(self.months.items()) if res.is_overdrawn]

    @property
    def worst_month(self) -> tuple[int, CoverageResult] | None:
        negatives = [(m, res) for m, res in self.months.items() if res.is_overdrawn]
        if not negatives:
            return None
        return max(negatives, key=lambda item: item[1].deficit)

    @property
    def is_overdrawn(self) -> bool:
        return bool(self.negative_months) or self.annual.is_overdrawn


def coverage_from_tracking_rows(rows: Iterable[object]) -> CoverageResult:
    """Berechnet Deckung aus TrackingRow-ähnlichen Objekten."""
    income = 0.0
    expenses = 0.0
    savings = 0.0
    savings_by_category: dict[str, float] = {}
    for row in rows:
        typ = str(getattr(row, "typ", ""))
        amount = float(getattr(row, "amount", 0.0) or 0.0)
        if typ == TYP_INCOME:
            income += amount
        elif typ == TYP_EXPENSES:
            expenses += amount
        elif typ == TYP_SAVINGS:
            savings += amount
            cat = str(getattr(row, "category", "") or "")
            if cat:
                savings_by_category[cat] = savings_by_category.get(cat, 0.0) + amount
    return CoverageResult(income, expenses, savings, savings_by_category)


def budget_year_coverage(budget_model, year: int) -> BudgetYearCoverage:
    """Berechnet Deckung pro Monat und fürs Jahr aus BudgetModel-Daten."""
    matrices = {
        TYP_INCOME: budget_model.get_matrix(year, TYP_INCOME),
        TYP_EXPENSES: budget_model.get_matrix(year, TYP_EXPENSES),
        TYP_SAVINGS: budget_model.get_matrix(year, TYP_SAVINGS),
    }

    months: dict[int, CoverageResult] = {}
    annual_income = 0.0
    annual_expenses = 0.0
    annual_savings = 0.0
    annual_savings_by_category: dict[str, float] = {}

    for month in range(1, 13):
        income = sum(
            float(values.get(month, 0.0) or 0.0)
            for values in matrices[TYP_INCOME].values()
        )
        expenses = sum(
            float(values.get(month, 0.0) or 0.0)
            for values in matrices[TYP_EXPENSES].values()
        )
        savings_by_category = {
            str(cat): float(values.get(month, 0.0) or 0.0)
            for cat, values in matrices[TYP_SAVINGS].items()
            if abs(float(values.get(month, 0.0) or 0.0)) > EPS
        }
        savings = sum(savings_by_category.values())
        months[month] = CoverageResult(income, expenses, savings, savings_by_category)
        annual_income += income
        annual_expenses += expenses
        annual_savings += savings
        for cat, amount in savings_by_category.items():
            annual_savings_by_category[cat] = (
                annual_savings_by_category.get(cat, 0.0) + amount
            )

    annual = CoverageResult(
        annual_income, annual_expenses, annual_savings, annual_savings_by_category
    )
    return BudgetYearCoverage(int(year), months, annual)
