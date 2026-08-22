"""Regressionstest: Soll-Buchungsdatum je wiederkehrendem Eintrag.

Sichert die Eigenschaft "Wiederkehrende Transaktion mit Soll-Buchungsdatum
je Eintrag" auf Datenschicht-Ebene ab. Der GUI-Buchungspfad
(views/tabs/tracking_tab.py::add_fixcosts) leitet das Buchungsdatum aus dem
je Kategorie gepflegten `recurring_day` ab und klemmt es auf das Monatsende
(z. B. Tag 31 im Februar -> 28./29.) bzw. auf mindestens den 1.

Dieser Test spiegelt diese Produktionslogik (wie schon `_status` in
test_picker_and_budget_reached.py) UND verankert sie über
Quelltext-Marker-Assertions im echten Code, damit ein stilles Abdriften des
GUI-Pfads auffällt. Läuft ohne Qt/PySide6 (reine Datenschicht).
"""

from __future__ import annotations

import calendar
import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.budget_model import BudgetModel
from model.category_model import CategoryModel
from model.database import open_db
from model.migrations import migrate_all
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES


def _booking_day(year: int, month: int, recurring_day: int) -> int:
    """Spiegelt die Produktionslogik aus add_fixcosts (Tag-Ableitung)."""
    last_day = calendar.monthrange(year, month)[1]
    day = int(recurring_day or 1)
    if day < 1:
        day = 1
    if day > last_day:
        day = last_day
    return day


def _fresh():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = open_db(p)
    migrate_all(
        conn,
        db_path=p,
        backup_dir=os.path.join(os.path.dirname(p), "migration_backups"),
    )
    return conn, p


# ── Reine Logik: Clamping des Soll-Tags ──────────────────────────


def test_recurring_day_is_honored_within_month():
    assert _booking_day(2026, 1, 15) == 15
    assert _booking_day(2026, 6, 1) == 1
    assert _booking_day(2026, 12, 28) == 28


def test_recurring_day_clamped_to_month_end_february_non_leap():
    # 2026 ist KEIN Schaltjahr -> Februar hat 28 Tage
    assert _booking_day(2026, 2, 31) == 28
    assert _booking_day(2026, 2, 30) == 28
    assert _booking_day(2026, 2, 29) == 28


def test_recurring_day_clamped_to_month_end_february_leap():
    # 2024 IST ein Schaltjahr -> Februar hat 29 Tage
    assert _booking_day(2024, 2, 31) == 29
    assert _booking_day(2024, 2, 29) == 29


def test_recurring_day_clamped_for_30_day_months():
    # April/Juni/September/November haben 30 Tage
    for m in (4, 6, 9, 11):
        assert _booking_day(2026, m, 31) == 30


def test_recurring_day_lower_bound_is_first():
    assert _booking_day(2026, 5, 0) == 1
    assert _booking_day(2026, 5, -3) == 1


# ── End-to-End auf der Datenschicht ──────────────────────────────


def test_booking_lands_on_recurring_day_end_to_end():
    """Buchung über die echten Modelle landet auf dem Soll-Tag."""
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        b = BudgetModel(conn)
        t = TrackingModel(conn)
        y, m = 2026, 3
        c.create(
            TYP_EXPENSES,
            "Versicherung",
            is_fix=True,
            is_recurring=True,
            recurring_day=17,
        )
        b.set_amount(y, m, TYP_EXPENSES, "Versicherung", 90.0)

        day = _booking_day(y, m, 17)
        t.add(
            date(y, m, day),
            TYP_EXPENSES,
            "Versicherung",
            90.0,
            "März - Versicherung",
            source="auto_fixcost",
        )

        rows = [r for r in t.list_all_sorted() if r.category == "Versicherung"]
        assert len(rows) == 1
        assert rows[0].date == date(y, m, 17)
    finally:
        conn.close()
        os.remove(p)


def test_booking_clamps_february_end_to_end():
    """recurring_day=31 wird im Februar auf den letzten Tag geklemmt."""
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        b = BudgetModel(conn)
        t = TrackingModel(conn)
        y, m = 2026, 2  # 28 Tage
        c.create(
            TYP_EXPENSES, "Leasing", is_fix=True, is_recurring=True, recurring_day=31
        )
        b.set_amount(y, m, TYP_EXPENSES, "Leasing", 250.0)

        day = _booking_day(y, m, 31)
        assert day == 28
        t.add(
            date(y, m, day),
            TYP_EXPENSES,
            "Leasing",
            250.0,
            "Februar - Leasing",
            source="auto_fixcost",
        )

        rows = [r for r in t.list_all_sorted() if r.category == "Leasing"]
        assert len(rows) == 1
        assert rows[0].date == date(2026, 2, 28)
    finally:
        conn.close()
        os.remove(p)


# ── Verankerung: Produktionslogik existiert weiterhin im GUI-Pfad ─


def test_production_path_still_derives_and_clamps_booking_day():
    """Stilles Abdriften des GUI-Buchungspfads soll auffallen."""
    src = (ROOT / "views" / "tabs" / "tracking_tab.py").read_text(encoding="utf-8")
    assert "calendar.monthrange(year, month)[1]" in src
    assert "cat.recurring_day" in src
    assert "if day > last_day:" in src
    assert "day = last_day" in src
