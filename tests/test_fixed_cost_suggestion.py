"""Regressionstests für die Fixkosten-Regel der Budget-Vorschlagslogik (v2.0.8).

Kernregel:
    "0 darf nie allein der Auslöser für einen Budgetvorschlag mit Fixkosten sein.
     Fixkosten können inkrementell sein."

Interpretation für die Engine:
  - Fixkosten/wiederkehrende Kategorien (is_fix=1 oder is_recurring=1)
    ignorieren 0-Monate bei Budgetänderungen.
  - Es braucht wiederholte echte Buchungen (> 0), bevor ein Vorschlag entsteht.
  - Flexible Kategorien dürfen 0-Monate weiterhin als Teil eines wiederholten
    Nutzungsmusters verwenden.

Läuft ohne Qt/PySide6.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.migrations import migrate_all  # noqa: E402
from model.budget_suggestion_engine import BudgetSuggestionEngine  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402

# ── Helpers ──────────────────────────────────────────────────────


def _prev_months(year: int, month: int, n: int):
    """Liefert n (year, month)-Paare rückwärts inkl. Startmonat."""
    out = []
    y, m = year, month
    for _ in range(n):
        out.append((y, m))
        m -= 1
        if m < 1:
            m = 12
            y -= 1
    return out


def _add_category(conn, name, *, is_fix=False, is_recurring=False):
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) "
        "VALUES(?,?,?,?,1)",
        (TYP_EXPENSES, name, 1 if is_fix else 0, 1 if is_recurring else 0),
    )


def _set_budget(conn, name, months, amount):
    for y, m in months:
        conn.execute(
            "INSERT OR REPLACE INTO budget(year, month, typ, category, amount) "
            "VALUES(?,?,?,?,?)",
            (y, m, TYP_EXPENSES, name, amount),
        )


def _book(conn, name, months, amount):
    if amount == 0:
        return
    for y, m in months:
        conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) "
            "VALUES(?,?,?,?,?)",
            (f"{y:04d}-{m:02d}-15", TYP_EXPENSES, name, amount, "test"),
        )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


# Zielmonat des Vorschlags. use_current_month=False → Analyse startet im Vormonat.
TARGET_Y, TARGET_M = 2025, 12
# 9 budgetierte Monate (Ziel + 8 davor) sichern genug Datenpunkte + 0-Strähne >= 6.
BUDGET_MONTHS = _prev_months(TARGET_Y, TARGET_M, 9)
# Buchungs-Historie: die abgeschlossenen Monate vor dem Zielmonat.
HISTORY_MONTHS = _prev_months(2025, 11, 8)


# ── T1: Fixkosten + 0 Buchungen → kein Vorschlag ─────────────────


def test_fixed_cost_zero_actuals_no_suggestion(conn):
    _add_category(conn, "Miete", is_fix=True)
    _set_budget(conn, "Miete", BUDGET_MONTHS, 1500.0)
    # KEINE Buchungen
    eng = BudgetSuggestionEngine(conn)
    res = eng.compute_category_suggestion(
        typ=TYP_EXPENSES, category="Miete", year=TARGET_Y, month=TARGET_M
    )
    assert res is None, "Fixkosten dürfen ohne echte Buchung keinen Vorschlag erzeugen"


# ── T2: Nicht-Fixkosten, gleiche Daten → 0-Reduktion liefert Vorschlag ─


def test_non_fixed_zero_actuals_does_suggest(conn):
    _add_category(conn, "Hobby", is_fix=False)
    _set_budget(conn, "Hobby", BUDGET_MONTHS, 1500.0)
    eng = BudgetSuggestionEngine(conn)
    res = eng.compute_category_suggestion(
        typ=TYP_EXPENSES, category="Hobby", year=TARGET_Y, month=TARGET_M
    )
    assert res is not None, "Nicht-Fixkosten sollen bei langer 0-Strähne gesenkt werden"
    assert res.suggested_budget < 1500.0


# ── T3: Fixkosten mit echten, wiederholten Buchungen → Vorschlag erlaubt ─


def test_fixed_cost_with_repeated_real_bookings_still_suggests(conn):
    _add_category(conn, "Strom", is_fix=True)
    _set_budget(conn, "Strom", BUDGET_MONTHS, 100.0)
    # Dauerhaft deutlich über Budget → Erhöhungsvorschlag erwartet
    _book(conn, "Strom", HISTORY_MONTHS, 160.0)
    eng = BudgetSuggestionEngine(conn)
    res = eng.compute_category_suggestion(
        typ=TYP_EXPENSES, category="Strom", year=TARGET_Y, month=TARGET_M
    )
    assert (
        res is not None
    ), "Fixkosten mit wiederholten echten Buchungen müssen analysiert werden"
    assert res.suggested_budget > 100.0, "Dauerhafte Überschreitung → Budget erhöhen"
    assert res.direction == "deficit"


# ── T4: Schutz abschaltbar ───────────────────────────────────────


def test_respect_fixed_costs_flag_can_disable(conn):
    _add_category(conn, "Versicherung", is_fix=True)
    _set_budget(conn, "Versicherung", BUDGET_MONTHS, 1500.0)
    eng = BudgetSuggestionEngine(conn)
    # Mit Schutz: kein Vorschlag
    assert (
        eng.compute_category_suggestion(
            typ=TYP_EXPENSES, category="Versicherung", year=TARGET_Y, month=TARGET_M
        )
        is None
    )
    # Ohne Schutz: 0-Reduktion greift wie bei normalen Kategorien
    res = eng.compute_category_suggestion(
        typ=TYP_EXPENSES,
        category="Versicherung",
        year=TARGET_Y,
        month=TARGET_M,
        respect_fixed_costs=False,
    )
    assert res is not None
    assert res.suggested_budget < 1500.0


# ── T5: Dein Versicherungsfall: 1 echte Buchung + viele 0 → kein Senken ─


def test_fixed_cost_one_real_booking_plus_zeros_does_not_reduce(conn):
    """Budget 200, Ist 250/0/0/... darf kein Senkungsvorschlag werden."""
    months = _prev_months(2026, 7, 7)
    history = _prev_months(2026, 6, 6)
    _add_category(conn, "Versicherung", is_fix=True, is_recurring=True)
    _set_budget(conn, "Versicherung", months, 200.0)
    _book(conn, "Versicherung", [history[-1]], 250.0)  # eine alte echte Zahlung

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Versicherung", year=2026, month=7, months_back=6
    )

    assert res is None


def test_fixed_incremental_over_budget_active_months_but_total_covered_no_increase(
    conn,
):
    """Budget 200, Ist 250/250/250/0/0/0 ist total gedeckt und darf nicht erhöhen."""
    months = _prev_months(2026, 7, 7)
    # HISTORY_MONTHS in zeitlicher Reihenfolge: Juni, Mai, April, März, Februar, Januar.
    history = _prev_months(2026, 6, 6)
    _add_category(conn, "Versicherung", is_fix=True, is_recurring=True)
    _set_budget(conn, "Versicherung", months, 200.0)
    _book(conn, "Versicherung", history[3:], 250.0)  # Jan–März je 250, danach 0

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Versicherung", year=2026, month=7, months_back=6
    )

    assert res is None


def test_fixed_incremental_total_undercovered_uses_window_average(conn):
    """Bei lumpy Fixkosten wird Erhöhung aus Gesamtunterdeckung abgeleitet, nicht aus Einzelzahlung."""
    months = _prev_months(2026, 7, 7)
    history = _prev_months(2026, 6, 6)
    _add_category(conn, "Versicherung", is_fix=True, is_recurring=True)
    _set_budget(conn, "Versicherung", months, 200.0)
    _book(conn, "Versicherung", history[3:], 450.0)  # 1350 Ist gegen 1200 Budget

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Versicherung", year=2026, month=7, months_back=6
    )

    assert res is not None
    assert res.direction == "deficit"
    assert res.suggested_budget == 220.0


# ── T6: Wiederkehrend ohne is_fix wird ebenfalls geschützt ─────────


def test_recurring_category_zero_months_do_not_reduce_budget(conn):
    """Auch is_recurring=1 ist fixed-like und darf nicht wegen 0-Monaten senken."""
    months = _prev_months(2026, 7, 7)
    history = _prev_months(2026, 6, 6)
    _add_category(conn, "Jahresabo", is_fix=False, is_recurring=True)
    _set_budget(conn, "Jahresabo", months, 120.0)
    _book(conn, "Jahresabo", [history[-1]], 120.0)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Jahresabo", year=2026, month=7, months_back=6
    )

    assert res is None


# ── T7: Flexible Budgets bleiben flexibel ─────────────────────────


def test_flexible_category_can_reduce_from_repeated_low_pattern_with_zero(conn):
    """Hobby 40 CHF, Ist 20/30/0/20/30/0 darf gesenkt werden."""
    months = [(2026, m) for m in [1, 2, 3, 4, 5, 6, 7]]
    _add_category(conn, "Hobby", is_fix=False, is_recurring=False)
    _set_budget(conn, "Hobby", months, 40.0)
    for month, amount in [(1, 20), (2, 30), (3, 0), (4, 20), (5, 30), (6, 0)]:
        _book(conn, "Hobby", [(2026, month)], amount)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Hobby", year=2026, month=7, months_back=6
    )

    assert res is not None
    assert res.suggested_budget < res.current_budget


# ── T8: Ausreißer rauf/runter bleibt stabil ───────────────────────


def test_food_overshoot_then_undershoot_stays_stable(conn):
    """Nahrungsmittel 400, Ist 450 danach 350 ergibt keinen Vorschlag."""
    months = [(2026, 1), (2026, 2), (2026, 3)]
    _add_category(conn, "Nahrungsmittel")
    _set_budget(conn, "Nahrungsmittel", months, 400.0)
    _book(conn, "Nahrungsmittel", [(2026, 1)], 450.0)
    _book(conn, "Nahrungsmittel", [(2026, 2)], 350.0)

    res = BudgetSuggestionEngine(conn).compute_category_suggestion(
        typ=TYP_EXPENSES, category="Nahrungsmittel", year=2026, month=3, months_back=2
    )

    assert res is None
