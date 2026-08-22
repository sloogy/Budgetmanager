"""Separater Lernmodus für neue Budgets aus Tracking-Daten.

Dieses Modul ist absichtlich unabhängig von der normalen Budget-Suggestion-Engine:
Kategorien ohne positives Jahresbudget werden hier klassifiziert und als
Startbudget vorgeschlagen. Sobald ein Budget existiert, ist der Lernmodus für
 diese Kategorie beendet.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from math import ceil, floor
from statistics import median

from model.category_forecast_mode import (
    FORECAST_MODE_INCREMENTAL,
    FORECAST_MODE_NORMAL,
    FORECAST_MODE_POT,
)
from model.typ_constants import TYP_INCOME, TYP_SAVINGS, is_income
from utils.i18n import tr
from utils.money import format_money

KIND_FIXED_RECURRING = "fixed_recurring"
KIND_FIXED_INCREMENTAL = "fixed_incremental"
KIND_RECURRING_ONLY = "recurring_only"
KIND_VARIABLE_POT = "variable_pot"
KIND_SAVINGS_POT = "savings_pot"
KIND_VARIABLE_INCOME = "variable_income"
KIND_IRREGULAR = "irregular"

ALL_LEARNING_BUDGET_KINDS = (
    KIND_FIXED_RECURRING,
    KIND_FIXED_INCREMENTAL,
    KIND_RECURRING_ONLY,
    KIND_VARIABLE_POT,
    KIND_SAVINGS_POT,
    KIND_VARIABLE_INCOME,
    KIND_IRREGULAR,
)


@dataclass(frozen=True)
class LearningBudgetKindProfile:
    kind: str
    label_key: str
    is_fix: bool
    is_recurring: bool
    forecast_mode: str


LEARNING_KIND_PROFILES: dict[str, LearningBudgetKindProfile] = {
    KIND_FIXED_RECURRING: LearningBudgetKindProfile(
        KIND_FIXED_RECURRING,
        "budget_learning.kind.fixed_recurring",
        True,
        True,
        FORECAST_MODE_INCREMENTAL,
    ),
    KIND_FIXED_INCREMENTAL: LearningBudgetKindProfile(
        KIND_FIXED_INCREMENTAL,
        "budget_learning.kind.fixed_incremental",
        True,
        False,
        FORECAST_MODE_INCREMENTAL,
    ),
    KIND_RECURRING_ONLY: LearningBudgetKindProfile(
        KIND_RECURRING_ONLY,
        "budget_learning.kind.recurring_only",
        False,
        True,
        FORECAST_MODE_NORMAL,
    ),
    KIND_VARIABLE_POT: LearningBudgetKindProfile(
        KIND_VARIABLE_POT,
        "budget_learning.kind.variable_pot",
        False,
        False,
        FORECAST_MODE_NORMAL,
    ),
    KIND_SAVINGS_POT: LearningBudgetKindProfile(
        KIND_SAVINGS_POT,
        "budget_learning.kind.savings_pot",
        False,
        False,
        FORECAST_MODE_POT,
    ),
    KIND_VARIABLE_INCOME: LearningBudgetKindProfile(
        KIND_VARIABLE_INCOME,
        "budget_learning.kind.variable_income",
        False,
        True,
        FORECAST_MODE_NORMAL,
    ),
    KIND_IRREGULAR: LearningBudgetKindProfile(
        KIND_IRREGULAR,
        "budget_learning.kind.irregular",
        False,
        False,
        FORECAST_MODE_POT,
    ),
}


def budget_kind_profile(kind: str) -> LearningBudgetKindProfile:
    return LEARNING_KIND_PROFILES.get(
        str(kind or ""), LEARNING_KIND_PROFILES[KIND_VARIABLE_POT]
    )


def budget_kind_label(kind: str) -> str:
    return tr(budget_kind_profile(kind).label_key)


def _coefficient_of_variation(values: list[float]) -> float:
    positives = [float(v) for v in values if float(v or 0.0) > 0.01]
    if len(positives) < 2:
        return 0.0
    avg = sum(positives) / len(positives)
    if avg <= 0.01:
        return 0.0
    variance = sum((v - avg) ** 2 for v in positives) / len(positives)
    return (variance**0.5) / avg


def infer_learning_budget_kind(typ: str, observed_values: list[float]) -> str:
    """Klassifiziert Tracking-Daten in eine Budgetart.

    Die Heuristik ist bewusst konservativ. Sie soll einen sinnvollen Vorschlag
    machen, aber niemals die Entscheidung des Nutzers ersetzen.
    """
    values = [abs(float(v or 0.0)) for v in observed_values]
    positives = [v for v in values if v > 0.01]
    if not positives:
        return KIND_VARIABLE_POT

    zero_count = sum(1 for v in values if v <= 0.01)
    active_count = len(positives)
    active_count / max(1, len(values))
    cv = _coefficient_of_variation(positives)

    if typ == TYP_INCOME or is_income(typ):
        # Fixer Monatslohn wird als fix+wiederholend erkannt; Stundenlohn/Nebenjob
        # wird konservativ als schwankendes Einkommen behandelt.
        if zero_count == 0 and cv <= 0.02 and active_count >= 2:
            return KIND_FIXED_RECURRING
        return KIND_VARIABLE_INCOME

    if typ == TYP_SAVINGS:
        return KIND_SAVINGS_POT

    # Lücken im Verlauf sind bei Gesundheit, Franchise, Reparaturen usw. typisch:
    # kein normaler monatlicher Fixbetrag, sondern Topf/Rückstellung.
    if zero_count > 0:
        # Lücken + sehr ähnliche Beträge deuten auf inkrementelle Fixkosten
        # (z.B. quartalsweise Versicherung). Variierende Beträge bleiben bewusst
        # unregelmäßige Rückstellungen.
        if active_count >= 2 and cv <= 0.10:
            return KIND_FIXED_INCREMENTAL
        return KIND_IRREGULAR

    # Jeder beobachtete Monat hat Buchungen. Wirklich gleiche Beträge sind
    # Fixkosten; leicht schwankende, aber klar wiederkehrende Kategorien bleiben
    # „nur wiederholend“. Typische Haushaltskategorien wie Essen werden als
    # variabler Topf geführt, damit sie flexibel bleiben.
    if cv <= 0.02 and active_count >= 2:
        return KIND_FIXED_RECURRING
    if cv <= 0.05:
        return KIND_RECURRING_ONLY
    return KIND_VARIABLE_POT


def learned_monthly_amount(typ: str, kind: str, observed_values: list[float]) -> float:
    """Ermittelt den Monatsbetrag passend zur erkannten Budgetart."""
    values = [abs(float(v or 0.0)) for v in observed_values]
    positives = [v for v in values if v > 0.01]
    if not positives:
        return 0.0

    if kind in {KIND_IRREGULAR, KIND_FIXED_INCREMENTAL, KIND_SAVINGS_POT} and any(
        v <= 0.01 for v in values
    ):
        # Rückstellungslogik: auf beobachtete Monate verteilen, damit z.B.
        # Franchise/Selbstbehalt als Monatsreserve statt als monatliche Fixkosten
        # vorgeschlagen werden.
        return sum(values) / max(1, len(values))

    if kind == KIND_VARIABLE_INCOME:
        # Einkommen nicht schönrechnen: Für Stundenlohn/schwankenden Lohn ist der
        # niedrigste beobachtete positive Monat der konservativste Startwert.
        return float(min(positives))

    if kind == KIND_VARIABLE_POT:
        # Variable Töpfe nicht zu knapp starten. Bei moderaten Schwankungen gibt
        # ein kleiner Puffer einen praxisnahen Startwert; bei starken Sprüngen
        # bleibt der Median stabiler und verhindert Überreaktionen.
        if _coefficient_of_variation(positives) <= 0.10:
            return (sum(positives) / len(positives)) * 1.02
        return float(median(positives))

    return float(median(positives))


def round_learning_amount(typ: str, amount: float, round_to: float) -> float:
    """Konservative Rundung: Einkommen runter, Ausgaben/Ersparnisse rauf."""
    step = max(1.0, float(round_to or 10.0))
    raw = max(0.0, float(amount or 0.0))
    if raw <= 0.0:
        return 0.0
    if typ == TYP_INCOME or is_income(typ):
        # Schwankende Einkommen werden bewusst grober abgerundet als Ausgaben.
        # Beispiel 4'820/5'130/4'760 CHF → 4'750 CHF Startbudget.
        step = max(step, 50.0)
        rounded = floor(raw / step) * step
    else:
        rounded = ceil(raw / step) * step
    return max(step, float(rounded))


def tracking_series_text(
    year: int, monthly: dict[int, float], months: list[int]
) -> str:
    parts: list[str] = []
    for month in months:
        amount = float(monthly.get(month, 0.0) or 0.0)
        parts.append(f"{month:02d}/{year}: {format_money(amount)}")
    return ", ".join(parts)


def apply_learning_budget_kind(
    conn: sqlite3.Connection,
    typ: str,
    category: str,
    kind: str,
    *,
    recurring_day: int | None = None,
) -> None:
    """Speichert die vom Nutzer bestätigte Budgetart an der Kategorie."""
    profile = budget_kind_profile(kind)
    if recurring_day is None:
        try:
            from settings import Settings

            recurring_day = int(Settings().get("recurring_preferred_day", 25) or 25)
        except Exception:
            recurring_day = 25
    day = int(recurring_day or 25)
    day = max(1, min(31, day))

    row = conn.execute(
        "SELECT id FROM categories WHERE typ=? AND name=?",
        (typ, category),
    ).fetchone()
    if row is None:
        conn.execute(
            """
            INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day, forecast_mode)
            VALUES(?,?,?,?,?,?)
            """,
            (
                typ,
                category,
                1 if profile.is_fix else 0,
                1 if profile.is_recurring else 0,
                day,
                profile.forecast_mode,
            ),
        )
    else:
        conn.execute(
            """
            UPDATE categories
            SET is_fix=?, is_recurring=?, recurring_day=?, forecast_mode=?
            WHERE typ=? AND name=?
            """,
            (
                1 if profile.is_fix else 0,
                1 if profile.is_recurring else 0,
                day,
                profile.forecast_mode,
                typ,
                category,
            ),
        )
    conn.commit()
