"""Tests für v2.0.12 – Übersicht-Charts:

1. Donut-Budget bereichsbezogen: bei rollierenden Bereichen (z.B. 90 Tage)
   muss das Budget über die Monate des Bereichs summiert werden, nicht über
   das (deaktivierte) Monats-Combo.
2. Top-Buchungen pro Kategorie aggregiert (mehrfacher Lohn -> eine Summe).

Läuft ohne Qt/PySide6 (reine Datenschicht + Qt-freier Aggregations-Helfer).
"""
from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.database import open_db  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.category_model import CategoryModel  # noqa: E402
from model.budget_model import BudgetModel  # noqa: E402
from model.tracking_model import TrackingModel  # noqa: E402
from model.overview_aggregation import aggregate_top_bookings  # noqa: E402
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, normalize_typ  # noqa: E402

EPS = 1e-6


def _months_between(d1: date, d2: date):
    if d2 < d1:
        d1, d2 = d2, d1
    cur = date(d1.year, d1.month, 1)
    end = date(d2.year, d2.month, 1)
    out = []
    while cur <= end:
        out.append((cur.year, cur.month))
        cur = date(cur.year + (1 if cur.month == 12 else 0),
                   1 if cur.month == 12 else cur.month + 1, 1)
    return out


def _fresh():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = open_db(p)
    migrate_all(conn, db_path=p)
    return conn, p


def _sum_for(sums: dict, typ: str) -> float:
    for k, v in sums.items():
        if normalize_typ(k) == typ:
            return v
    return 0.0


# ── 1. Donut-Budget bereichsbezogen ──────────────────────────────

def test_range_budget_spans_window_months_not_single_month():
    conn, p = _fresh()
    try:
        b = BudgetModel(conn)
        for m in (3, 4, 5, 6):
            b.set_amount(2026, m, TYP_INCOME, "Lohn", 5000.0)
            b.set_amount(2026, m, TYP_EXPENSES, "Miete", 2000.0)
        # 90-Tage-Fenster 17.03.–15.06.2026 berührt Mär..Jun = 4 Monate
        months = _months_between(date(2026, 3, 17), date(2026, 6, 15))
        assert months == [(2026, 3), (2026, 4), (2026, 5), (2026, 6)]
        sums = b.sum_by_typ_range(months)
        # bereichsbezogen: 4 Monate, NICHT 1 (Einzelmonat) und NICHT 12 (Jahr)
        assert abs(_sum_for(sums, TYP_INCOME) - 20000.0) < EPS
        assert abs(_sum_for(sums, TYP_EXPENSES) - 8000.0) < EPS
        # Einzelmonat (alte, fehlerhafte Logik) waere nur 2000 -> belegt den Unterschied
        single = b.sum_by_typ_range([(2026, 6)])
        assert abs(_sum_for(single, TYP_EXPENSES) - 2000.0) < EPS
    finally:
        conn.close()
        os.remove(p)


# ── 2. Top-Buchungen-Aggregation ─────────────────────────────────

@dataclass
class _Row:
    typ: str
    category: str
    amount: float


def test_aggregate_top_bookings_sums_salary_once():
    rows = [
        _Row(TYP_INCOME, "Lohn", 5000.0),
        _Row(TYP_INCOME, "Lohn", 5000.0),
        _Row(TYP_INCOME, "Lohn", 5000.0),
        _Row(TYP_INCOME, "Bonus", 1000.0),
        _Row(TYP_EXPENSES, "Miete", 1500.0),
        _Row(TYP_EXPENSES, "Miete", 1500.0),
        _Row(TYP_EXPENSES, "Miete", 1500.0),
        _Row(TYP_EXPENSES, "Essen", 400.0),
    ]
    top = aggregate_top_bookings(rows, top_n=5)
    as_dict = {cat: total for (typ, cat), total in top}
    # Lohn genau einmal, summiert
    assert sum(1 for (_t, cat), _v in top if cat == "Lohn") == 1
    assert abs(as_dict["Lohn"] - 15000.0) < EPS
    assert abs(as_dict["Miete"] - 4500.0) < EPS
    # größter Eintrag ist Lohn
    assert top[0][0][1] == "Lohn"


def test_aggregate_top_bookings_uses_abs_and_limits():
    rows = [
        _Row(TYP_EXPENSES, "A", -300.0),
        _Row(TYP_EXPENSES, "A", -200.0),  # |sum| = 500
        _Row(TYP_EXPENSES, "B", -100.0),
        _Row(TYP_EXPENSES, "C", -50.0),
        _Row(TYP_EXPENSES, "D", -40.0),
        _Row(TYP_EXPENSES, "E", -30.0),
        _Row(TYP_EXPENSES, "F", -20.0),
    ]
    top = aggregate_top_bookings(rows, top_n=5)
    assert len(top) == 5  # auf top_n begrenzt
    assert top[0][0][1] == "A" and abs(top[0][1] - 500.0) < EPS  # Betrag absolut


def test_aggregate_top_bookings_skips_empty_category():
    rows = [_Row(TYP_EXPENSES, "", 100.0), _Row(TYP_EXPENSES, "X", 50.0)]
    top = aggregate_top_bookings(rows)
    cats = [cat for (_t, cat), _v in top]
    assert "" not in cats and "X" in cats
