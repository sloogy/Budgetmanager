"""Zentrale Typ-Konstanten für Budget/Tracking-Typen.

Wichtig:
- Diese Strings sind DB-Schlüssel. Sie dürfen NIE übersetzt werden.
- Anzeigetexte kommen aus utils.i18n.display_typ(TYP_xxx).
- Alle Modelle, Engines und Views sollen diese Konstanten importieren
  statt "Einkommen" / "Ausgaben" / "Ersparnisse" als Literale zu schreiben.

Historisch: Die DB speichert immer Deutsch (Einkommen/Ausgaben/Ersparnisse).
Das bleibt so – aber der Code referenziert ab jetzt Konstanten, nicht Literale.
"""
from __future__ import annotations

# ── DB-Schlüssel (nie ändern, DB-Migration nötig wenn doch) ──
TYP_INCOME   = "Einkommen"
TYP_EXPENSES = "Ausgaben"
TYP_SAVINGS  = "Ersparnisse"

# Alle Typen als Tuple (für Iteration, Validierung)
ALL_TYPEN: tuple[str, ...] = (TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS)

# Normalisierungs-Aliases: externe / veraltete Strings → DB-Schlüssel
_ALIASES: dict[str, str] = {
    # Einkommen
    "einnahmen":  TYP_INCOME,
    "einkommen":  TYP_INCOME,
    "income":     TYP_INCOME,
    # Ausgaben
    "ausgaben":   TYP_EXPENSES,
    "expenses":   TYP_EXPENSES,
    "expense":    TYP_EXPENSES,
    # Ersparnisse
    "ersparnisse": TYP_SAVINGS,
    "sparen":      TYP_SAVINGS,
    "savings":     TYP_SAVINGS,
}

# Typen bei denen Beträge abs() normiert werden (nicht Einkommen)
ABS_TYPEN: frozenset[str] = frozenset({TYP_EXPENSES, TYP_SAVINGS})

# Typen bei denen positiv = über Plan (Einkommen: mehr ist gut)
INCOME_TYPEN: frozenset[str] = frozenset({TYP_INCOME})


def normalize_typ(raw: str) -> str:
    """Normalisiert einen Typ-String auf den DB-Schlüssel.

    Akzeptiert:
    - Direkte DB-Schlüssel ("Einkommen", "Ausgaben", "Ersparnisse")
    - Aliasnamen ("income", "expenses", "savings", "einnahmen", …)
    - Gross-/Kleinschreibung wird ignoriert

    Returns:
        DB-Schlüssel (TYP_INCOME / TYP_EXPENSES / TYP_SAVINGS)
        oder den Eingabe-String wenn kein Alias gefunden.
    """
    s = str(raw or "").strip()
    return _ALIASES.get(s.lower(), s)


def is_income(typ: str) -> bool:
    """True wenn typ das Einkommen-Konto darstellt."""
    return normalize_typ(typ) == TYP_INCOME


def rest_sign(typ: str, budget: float, actual: float) -> float:
    """Berechnet den Rest nach einheitlicher Vorzeichen-Konvention.

    Konvention (positiv = gut / unter Budget):
    - Einkommen:          actual - budget  (mehr verdient = positiv)
    - Ausgaben/Ersparnisse: budget - actual  (weniger ausgegeben = positiv)

    Das ist die *eine* zentrale Stelle für diese Logik.
    Alle anderen Code-Stellen (a-b / b-a) sollen hierher migriert werden.
    """
    if is_income(typ):
        return actual - budget
    return budget - actual
