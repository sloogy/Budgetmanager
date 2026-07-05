"""Regression v2.2.0: Cockpit-Start, Ampel, Monatsabschluss, Tracking-Komfort.

Qt-freie Logiktests (Ampel, Monatsabschluss-Model) plus statische
Zusicherungen für die UI-Verdrahtung.
"""
from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.migrations import migrate_all  # noqa: E402
from model.month_close_model import MonthCloseModel  # noqa: E402
from model.month_status import (  # noqa: E402
    LEVEL_GREEN,
    LEVEL_RED,
    LEVEL_YELLOW,
    compute_month_status,
)
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS  # noqa: E402


# ── Ampel ────────────────────────────────────────────────────────
def test_status_green_when_on_plan():
    st = compute_month_status(5000, 3000, 4000, 500)
    assert st.level == LEVEL_GREEN
    assert st.free_amount == 1500


def test_status_yellow_near_budget():
    st = compute_month_status(5000, 3700, 4000, 300)  # 92.5% des Budgets
    assert st.level == LEVEL_YELLOW


def test_status_yellow_tight_rest():
    # Budget weit weg, aber Rest < 5% der Einnahmen
    st = compute_month_status(5000, 4500, 10000, 400)  # Rest 100 = 2%
    assert st.level == LEVEL_YELLOW


def test_status_red_over_budget():
    st = compute_month_status(5000, 4200, 4000, 0)
    assert st.level == LEVEL_RED


def test_status_red_negative_free_amount():
    st = compute_month_status(3000, 2500, 0, 800)  # Rest −300, kein Budget
    assert st.level == LEVEL_RED
    assert st.free_amount == -300


# ── Monatsabschluss ──────────────────────────────────────────────
def _add_cat(conn, typ, name, is_fix=0, is_rec=0):
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) "
        "VALUES(?,?,?,?,1)",
        (typ, name, is_fix, is_rec),
    )


def _book(conn, y, m, typ, cat, amount):
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) "
        "VALUES(?,?,?,?,?,?)",
        (f"{y:04d}-{m:02d}-15", typ, cat, amount, "t", "manual"),
    )


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def test_month_close_surplus_flow(conn):
    _add_cat(conn, TYP_INCOME, "Lohn")
    _add_cat(conn, TYP_EXPENSES, "Essen")
    _add_cat(conn, TYP_SAVINGS, "Notgroschen")
    _book(conn, 2026, 6, TYP_INCOME, "Lohn", 5000.0)
    _book(conn, 2026, 6, TYP_EXPENSES, "Essen", 3000.0)
    conn.commit()

    m = MonthCloseModel(conn)
    info = m.compute(2026, 6)
    assert info.balance == 2000.0
    assert info.surplus_target == "Notgroschen"
    assert not info.already_closed

    m.book_surplus(2026, 6, 2000.0, "Notgroschen", "Monatsabschluss Juni 2026")
    info2 = m.compute(2026, 6)
    # Nach der Buchung ist der Monat ausgeglichen (Ersparnis bindet den Rest).
    assert abs(info2.balance) < 0.005
    row = conn.execute(
        "SELECT amount, date FROM tracking WHERE typ=? AND category=?",
        (TYP_SAVINGS, "Notgroschen"),
    ).fetchone()
    assert row is not None and float(row[0]) == 2000.0
    assert str(row[1]).endswith("-30")  # Monatsletzter Juni

    m.mark_closed(2026, 6)
    assert m.compute(2026, 6).already_closed


def test_month_close_surplus_prefers_open_goal(conn):
    _add_cat(conn, TYP_SAVINGS, "Ferien")
    _add_cat(conn, TYP_SAVINGS, "Auto")
    conn.execute(
        "INSERT INTO savings_goals(name, target_amount, current_amount, category, status, created_date) "
        "VALUES('Auto', 10000, 1000, 'Auto', 'active', '2026-01-01')"
    )
    _add_cat(conn, TYP_INCOME, "Lohn")
    _book(conn, 2026, 6, TYP_INCOME, "Lohn", 500.0)
    conn.commit()

    info = MonthCloseModel(conn).compute(2026, 6)
    assert info.surplus_target == "Auto"


def test_month_close_deficit_lists_only_funded_savings(conn):
    _add_cat(conn, TYP_INCOME, "Lohn")
    _add_cat(conn, TYP_EXPENSES, "Essen")
    _add_cat(conn, TYP_SAVINGS, "Notgroschen")
    _add_cat(conn, TYP_SAVINGS, "Leer")
    _book(conn, 2026, 5, TYP_SAVINGS, "Notgroschen", 800.0)  # Guthaben
    _book(conn, 2026, 6, TYP_INCOME, "Lohn", 1000.0)
    _book(conn, 2026, 6, TYP_EXPENSES, "Essen", 1400.0)
    conn.commit()

    m = MonthCloseModel(conn)
    info = m.compute(2026, 6)
    assert info.balance == -400.0
    cats = [c for c, _ in info.savings_with_funds]
    assert cats == ["Notgroschen"]  # "Leer" hat kein Guthaben

    m.cover_deficit_from_savings(2026, 6, 400.0, "Notgroschen", "Monatsabschluss")
    assert abs(m.compute(2026, 6).balance) < 0.005


def test_month_close_reduction_hints_never_include_fix_or_recurring(conn):
    _add_cat(conn, TYP_INCOME, "Lohn")
    _add_cat(conn, TYP_EXPENSES, "Miete", is_fix=1, is_rec=1)
    _add_cat(conn, TYP_EXPENSES, "Abo", is_rec=1)
    _add_cat(conn, TYP_EXPENSES, "Kleidung")
    for cat, amt in (("Miete", 1400), ("Abo", 40), ("Kleidung", 150)):
        conn.execute(
            "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 7, ?, ?, ?)",
            (TYP_EXPENSES, cat, amt),
        )
    _book(conn, 2026, 6, TYP_INCOME, "Lohn", 100.0)
    _book(conn, 2026, 6, TYP_EXPENSES, "Kleidung", 300.0)
    conn.commit()

    info = MonthCloseModel(conn).compute(2026, 6)
    hint_cats = [c for c, _, _ in info.reduction_hints]
    assert "Kleidung" in hint_cats
    assert "Miete" not in hint_cats
    assert "Abo" not in hint_cats


def test_month_close_lists_open_past_months_chronologically(conn):
    _add_cat(conn, TYP_INCOME, "Lohn")
    _add_cat(conn, TYP_EXPENSES, "Essen")
    _book(conn, 2026, 4, TYP_INCOME, "Lohn", 4000.0)
    _book(conn, 2026, 5, TYP_INCOME, "Lohn", 4000.0)
    _book(conn, 2026, 6, TYP_EXPENSES, "Essen", 500.0)
    conn.commit()

    m = MonthCloseModel(conn)
    m.mark_closed(2026, 4)

    assert m.list_open_months_before(2026, 7) == [(2026, 5), (2026, 6)]

    from datetime import date

    assert m.suggested_month_to_close(date(2026, 7, 5)) == (2026, 5)


def test_month_close_suggests_current_only_near_month_end_when_no_past_open(conn):
    m = MonthCloseModel(conn)

    from datetime import date

    assert m.suggested_month_to_close(date(2026, 7, 24)) is None
    assert m.suggested_month_to_close(date(2026, 7, 25)) == (2026, 7)
    m.mark_closed(2026, 7)
    assert m.suggested_month_to_close(date(2026, 7, 25)) is None


# ── Statische Zusicherungen (UI-Verdrahtung) ────────────────────
def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_cockpit_is_start_page_and_has_status_and_close_button():
    mw = _src("views/main_window.py")
    assert "start_on_cockpit" in mw
    cp = _src("views/tabs/cockpit_tab.py")
    assert "compute_month_status" in cp
    assert "MonthCloseDialog" in cp
    assert 'tr("cockpit.free_amount")' in cp


def test_overview_has_four_tabs_and_status_line():
    src = _src("views/tabs/overview_kpi_panel.py")
    assert src.count("self.chart_tabs.addTab(") == 4
    assert "_build_trend_tab" in src
    assert "compute_month_status" in src
    # Konto-Vergleich hängt nicht mehr als eigener Reiter im TabWidget
    assert 'addTab(self._build_typ_tab()' not in src


def test_tracking_remembers_last_category_per_typ():
    qa = _src("views/quick_add_dialog.py")
    tr_ = _src("views/tracker_dialog.py")
    for src in (qa, tr_):
        assert "tracking_last_category" in src
    st = _src("settings.py")
    assert '"tracking_last_category": {}' in st
    assert '"start_on_cockpit": True' in st


def test_help_tooltips_wired():
    assert 'tr("help.budget_pot")' in _src("views/category_manager_dialog.py")
    mc = _src("views/month_close_dialog.py")
    assert 'tr("help.month_close")' in mc
    assert 'tr("help.savings")' in mc
    assert 'tr("month_close.no_fix_cut_tip")' in mc


def test_month_close_dialog_uses_stable_amount_color_api():
    mc = _src("views/month_close_dialog.py")
    ui = _src("views/ui_colors.py")
    assert "c.positive" not in mc
    assert "c.amount_color(info.balance)" in mc
    assert "positive: str" in ui
    assert "amount_color" in ui


def test_month_close_deficit_does_not_use_future_savings_for_past_month(conn):
    _add_cat(conn, TYP_INCOME, "Lohn")
    _add_cat(conn, TYP_EXPENSES, "Essen")
    _add_cat(conn, TYP_SAVINGS, "Notgroschen")
    _book(conn, 2026, 5, TYP_INCOME, "Lohn", 1000.0)
    _book(conn, 2026, 5, TYP_EXPENSES, "Essen", 1400.0)
    # Dieses Guthaben entsteht erst im Juni und darf beim Abschluss Mai nicht
    # rückwirkend als Deckung vorgeschlagen werden.
    _book(conn, 2026, 6, TYP_SAVINGS, "Notgroschen", 800.0)
    conn.commit()

    info = MonthCloseModel(conn).compute(2026, 5)

    assert info.balance == -400.0
    assert info.savings_with_funds == []


def test_main_window_gesamt_past_year_uses_december_for_budget_warnings_static():
    src = _src("views/main_window.py")
    assert "selected_year == date.today().year else 12" in src


def test_cockpit_budget_warnings_uses_settings_lookback_static():
    src = _src("views/tabs/cockpit_tab.py")
    assert "budget_suggestion_months" in src
    assert "lookback_months=lookback" in src
