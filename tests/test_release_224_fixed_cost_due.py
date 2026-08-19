"""Regression v2.2.4: Fixkosten-Fälligkeit im Cockpit-„Fehlt"-Check.

Vor v2.2.4 galt jede unbezahlte Fixkosten-/Wiederkehrend-Position sofort als
"offen" – auch am Monatsanfang, obwohl der Soll-Tag (z.B. 25) noch nicht
erreicht war. Das meldete am 3. des Monats jede Miete fälschlich als fehlend.
Neu: im laufenden Monat erst ab dem Fälligkeitstag offen; vergangene Monate
immer fällig.
"""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.fixed_cost_due import is_open_this_month  # noqa: E402


def test_not_due_yet_in_current_month_is_not_open():
    o, rest = is_open_this_month(
        is_fix=True,
        is_recurring=True,
        budget=1410,
        booked=0,
        due_day=25,
        year=2026,
        month=7,
        today=date(2026, 7, 3),
    )
    assert o is False
    assert rest == 0.0


def test_due_reached_in_current_month_is_open():
    o, rest = is_open_this_month(
        is_fix=True,
        is_recurring=True,
        budget=1410,
        booked=0,
        due_day=25,
        year=2026,
        month=7,
        today=date(2026, 7, 25),
    )
    assert o is True
    assert rest == 1410.0


def test_past_month_always_due_regardless_of_day():
    o, _ = is_open_this_month(
        is_fix=True,
        is_recurring=True,
        budget=1410,
        booked=0,
        due_day=25,
        year=2026,
        month=5,
        today=date(2026, 7, 3),
    )
    assert o is True


def test_already_booked_is_not_open():
    o, _ = is_open_this_month(
        is_fix=True,
        is_recurring=True,
        budget=1410,
        booked=1410,
        due_day=25,
        year=2026,
        month=7,
        today=date(2026, 7, 26),
    )
    assert o is False


def test_xor_recurring_partial_booking_open_after_due():
    # nur wiederkehrend (nicht fix): offen solange Budget nicht erreicht,
    # aber erst ab Fälligkeitstag im laufenden Monat.
    o, rest = is_open_this_month(
        is_fix=False,
        is_recurring=True,
        budget=200,
        booked=50,
        due_day=10,
        year=2026,
        month=7,
        today=date(2026, 7, 15),
    )
    assert o is True
    assert rest == 150.0
    o2, _ = is_open_this_month(
        is_fix=False,
        is_recurring=True,
        budget=200,
        booked=50,
        due_day=10,
        year=2026,
        month=7,
        today=date(2026, 7, 5),
    )
    assert o2 is False


def test_no_budget_no_flags_is_never_open():
    o, _ = is_open_this_month(
        is_fix=False,
        is_recurring=True,
        budget=0,
        booked=0,
        due_day=1,
        year=2026,
        month=5,
        today=date(2026, 7, 3),
    )
    assert o is False


def test_cockpit_uses_due_logic():
    src = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    assert "from model.fixed_cost_due import is_open_this_month" in src
    assert "is_open_this_month(" in src
