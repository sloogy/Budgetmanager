"""Monatsstatus-Ampel (v2.2.0).

Eine einzige, überall gleiche Bewertung des laufenden Monats für Cockpit und
Übersicht – bewusst simpel und DAU-erklärbar:

- 🔴 ROT:   Es wurde mehr ausgegeben als geplant ODER es ist mehr Geld
            abgeflossen (Ausgaben + Ersparnisse) als hereinkam.
- 🟡 GELB:  Knapp – Ausgaben bei ≥ 90% des Plans oder frei verfügbarer Rest
            unter 5% der Einnahmen.
- 🟢 GRÜN:  Im Plan.

Qt-frei, damit die Logik headless testbar ist.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVEL_GREEN = "green"
LEVEL_YELLOW = "yellow"
LEVEL_RED = "red"

_ICONS = {LEVEL_GREEN: "🟢", LEVEL_YELLOW: "🟡", LEVEL_RED: "🔴"}
_TEXT_KEYS = {
    LEVEL_GREEN: "status.month_green",
    LEVEL_YELLOW: "status.month_yellow",
    LEVEL_RED: "status.month_red",
}


@dataclass(frozen=True)
class MonthStatus:
    level: str  # green | yellow | red
    icon: str  # 🟢 / 🟡 / 🔴
    text_key: str  # i18n-Key für die Kurzbeschreibung
    free_amount: float  # frei verfügbar = Einnahmen − Ausgaben − Ersparnisse


def compute_month_status(
    income_actual: float,
    expense_actual: float,
    expense_budget: float,
    savings_actual: float,
) -> MonthStatus:
    """Berechnet die Ampel aus Ist-Werten und dem Ausgaben-Budget."""
    income_actual = float(income_actual or 0.0)
    expense_actual = float(expense_actual or 0.0)
    expense_budget = float(expense_budget or 0.0)
    savings_actual = float(savings_actual or 0.0)

    free_amount = income_actual - expense_actual - savings_actual

    over_budget = expense_budget > 0 and expense_actual > expense_budget + 0.005
    if free_amount < -0.005 or over_budget:
        level = LEVEL_RED
    else:
        near_budget = expense_budget > 0 and expense_actual >= 0.9 * expense_budget
        tight_rest = income_actual > 0 and free_amount < 0.05 * income_actual
        level = LEVEL_YELLOW if (near_budget or tight_rest) else LEVEL_GREEN

    return MonthStatus(
        level=level,
        icon=_ICONS[level],
        text_key=_TEXT_KEYS[level],
        free_amount=free_amount,
    )
