"""Sprachneutrale Budget-Erfassungsmodi.

Die UI darf übersetzte Labels anzeigen, aber Geschäftslogik darf nie auf
sichtbare Texte wie "Alle"/"All"/"Tous" prüfen. Dieses Modul hält die
stabilen internen Werte zentral.
"""

from __future__ import annotations

BUDGET_MODE_MONTH = "month"
BUDGET_MODE_ALL = "all"
BUDGET_MODE_RANGE = "range"

# Alt-/Anzeigenamen aus älteren Versionen und unterstützten Sprachen.
_MODE_ALIASES = {
    BUDGET_MODE_MONTH: BUDGET_MODE_MONTH,
    BUDGET_MODE_ALL: BUDGET_MODE_ALL,
    BUDGET_MODE_RANGE: BUDGET_MODE_RANGE,
    "monat": BUDGET_MODE_MONTH,
    "month": BUDGET_MODE_MONTH,
    "mois": BUDGET_MODE_MONTH,
    "alle": BUDGET_MODE_ALL,
    "all": BUDGET_MODE_ALL,
    "tous": BUDGET_MODE_ALL,
    "toutes": BUDGET_MODE_ALL,
    "bereich": BUDGET_MODE_RANGE,
    "range": BUDGET_MODE_RANGE,
    "period": BUDGET_MODE_RANGE,
    "période": BUDGET_MODE_RANGE,
    "periode": BUDGET_MODE_RANGE,
}


def normalize_budget_mode(value: object) -> str:
    """Gibt einen stabilen internen Budgetmodus zurück.

    Unbekannte Werte fallen bewusst auf ``month`` zurück, weil dies dem alten
    Verhalten entspricht und keine Mehrfachänderung auslöst.
    """
    key = str(value or "").strip().lower()
    return _MODE_ALIASES.get(key, BUDGET_MODE_MONTH)


def is_all_mode(value: object) -> bool:
    return normalize_budget_mode(value) == BUDGET_MODE_ALL


def is_range_mode(value: object) -> bool:
    return normalize_budget_mode(value) == BUDGET_MODE_RANGE
