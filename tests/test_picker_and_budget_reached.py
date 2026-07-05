"""Tests für v2.0.10:

1. Gruppierter Tracker-Picker (Favoriten, häufig manuell, normale Buchungen,
   variable Fix-/Wiederkehrend-Gruppen, echte Fixkosten).
2. "Abgeschlossen = Budget erreicht" für Kategorien mit genau einem Flag
   (fix XOR wiederkehrend), inkl. Franchise-Anwendungsfall.

Läuft ohne Qt/PySide6 (reine Datenschicht).
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.database import open_db  # noqa: E402
from model.migrations import migrate_all  # noqa: E402
from model.category_model import CategoryModel  # noqa: E402
from model.budget_model import BudgetModel  # noqa: E402
from model.tracking_model import TrackingModel  # noqa: E402
from model.favorites_model import FavoritesModel  # noqa: E402
from model.typ_constants import TYP_EXPENSES  # noqa: E402

EPS = 1e-6


def _fresh():
    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = open_db(p)
    migrate_all(conn, db_path=p)
    return conn, p


# ── 1. Gruppierter Picker ────────────────────────────────────────

def test_grouped_picker_groups_and_order():
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        t = TrackingModel(conn)
        fav = FavoritesModel(conn)
        c.create(TYP_EXPENSES, "Miete", is_fix=True, is_recurring=True)
        c.create(TYP_EXPENSES, "Franchise", is_fix=True)
        c.create(TYP_EXPENSES, "Strom", is_recurring=True)
        c.create(TYP_EXPENSES, "Hobby")
        c.create(TYP_EXPENSES, "Lieblingsshop")
        fav.add(TYP_EXPENSES, "Lieblingsshop")
        for i in range(3):
            t.add(date(2026, 1, i + 1), TYP_EXPENSES, "Hobby", 10.0, "", source="manual")

        grouped = c.list_for_tracking_dropdown_grouped(TYP_EXPENSES)
        headers = [lbl for kind, lbl, _ in grouped if kind == "header"]
        # Reihenfolge der Gruppen: erst Favoriten, dann normale manuelle Buchungen,
        # dann variable/fixe Sondergruppen. So bleibt der Tracker für Alltagsbuchungen
        # übersichtlich und wird nicht von Automatik-Kategorien dominiert.
        assert headers.index([h for h in headers if "Favorit" in h][0]) == 0
        groups, cur = {}, None
        for kind, lbl, val in grouped:
            if kind == "header":
                cur = lbl
                groups[cur] = []
            else:
                groups[cur].append(val)
        fav_h = [h for h in headers if "Favorit" in h][0]
        freq_h = [h for h in headers if "Häufig" in h][0]
        fix_var_h = [h for h in headers if h == "Fix / variabel"][0]
        rec_var_h = [h for h in headers if h == "Wiederkehrend / variabel"][0]
        real_fix_h = [h for h in headers if h == "Echte Fixkosten"][0]
        assert groups[fav_h] == ["Lieblingsshop"]
        assert groups[freq_h] == ["Hobby"]
        assert groups[fix_var_h] == ["Franchise"]
        assert groups[rec_var_h] == ["Strom"]
        assert groups[real_fix_h] == ["Miete"]
        assert headers.index(freq_h) < headers.index(fix_var_h) < headers.index(rec_var_h) < headers.index(real_fix_h)
    finally:
        conn.close()
        os.remove(p)


def test_grouped_picker_no_duplicates_and_headers_have_no_value():
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        c.create(TYP_EXPENSES, "Miete", is_fix=True, is_recurring=True)
        c.create(TYP_EXPENSES, "Hobby")
        grouped = c.list_for_tracking_dropdown_grouped(TYP_EXPENSES)
        item_values = [v for k, _, v in grouped if k == "item"]
        assert len(item_values) == len(set(item_values))            # keine Duplikate
        assert all(v is None for k, _, v in grouped if k == "header")  # Header ohne Wert
    finally:
        conn.close()
        os.remove(p)


# ── 2. Budget-erreicht-Logik (fix XOR wiederkehrend) ─────────────

def _status(c, b, t, cat, y, m):
    """Spiegelt die Produktionslogik aus add_fixcosts/_refresh_missing."""
    is_fix, is_rec, _ = c.get_flags(TYP_EXPENSES, cat)
    budget = float(b.get_amount(y, m, TYP_EXPENSES, cat) or 0)
    booked = float(t.get_month_total(y, m, TYP_EXPENSES, cat) or 0)
    both = is_fix and is_rec
    single = bool(is_fix) ^ bool(is_rec)
    if both:
        exists = t.exists_in_month(year=y, month=m, typ=TYP_EXPENSES, category=cat)
        return ("offen" if not exists else "abgeschlossen", budget if not exists else 0.0)
    if single:
        if budget > EPS and abs(booked) >= abs(budget) - EPS:
            return ("abgeschlossen", 0.0)
        return ("offen", (budget - booked) if budget > EPS else 0.0)
    return ("n/a", 0.0)


def test_franchise_open_until_budget_reached():
    conn, p = _fresh()
    Y, M = 2026, 3
    try:
        c = CategoryModel(conn)
        b = BudgetModel(conn)
        t = TrackingModel(conn)
        c.create(TYP_EXPENSES, "Franchise", is_fix=True)  # fix, nicht wiederkehrend
        b.set_amount(Y, M, TYP_EXPENSES, "Franchise", 300.0)

        # noch nichts gebucht -> offen, Rest 300
        s, rest = _status(c, b, t, "Franchise", Y, M)
        assert s == "offen" and abs(rest - 300.0) < EPS

        # Teilbuchung 80 -> weiterhin offen, Rest 220
        t.add(date(Y, M, 5), TYP_EXPENSES, "Franchise", 80.0, "", source="auto_fixcost")
        s, rest = _status(c, b, t, "Franchise", Y, M)
        assert s == "offen" and abs(rest - 220.0) < EPS

        # auf 300 aufstocken -> abgeschlossen
        t.add(date(Y, M, 20), TYP_EXPENSES, "Franchise", 220.0, "", source="auto_fixcost")
        s, _ = _status(c, b, t, "Franchise", Y, M)
        assert s == "abgeschlossen"
    finally:
        conn.close()
        os.remove(p)


def test_recurring_only_completes_when_budget_reached():
    conn, p = _fresh()
    Y, M = 2026, 4
    try:
        c = CategoryModel(conn)
        b = BudgetModel(conn)
        t = TrackingModel(conn)
        c.create(TYP_EXPENSES, "Strom", is_recurring=True)  # wiederkehrend, nicht fix
        b.set_amount(Y, M, TYP_EXPENSES, "Strom", 100.0)

        t.add(date(Y, M, 5), TYP_EXPENSES, "Strom", 60.0, "", source="auto_recurring")
        s, rest = _status(c, b, t, "Strom", Y, M)
        assert s == "offen" and abs(rest - 40.0) < EPS

        t.add(date(Y, M, 25), TYP_EXPENSES, "Strom", 40.0, "", source="auto_recurring")
        s, _ = _status(c, b, t, "Strom", Y, M)
        assert s == "abgeschlossen"
    finally:
        conn.close()
        os.remove(p)


def test_both_flags_complete_after_single_booking():
    conn, p = _fresh()
    Y, M = 2026, 5
    try:
        c = CategoryModel(conn)
        b = BudgetModel(conn)
        t = TrackingModel(conn)
        c.create(TYP_EXPENSES, "Miete", is_fix=True, is_recurring=True)  # beide Flags
        b.set_amount(Y, M, TYP_EXPENSES, "Miete", 1500.0)

        s, rest = _status(c, b, t, "Miete", Y, M)
        assert s == "offen" and abs(rest - 1500.0) < EPS

        # eine Buchung -> abgeschlossen (fixer Monatsbetrag, nicht teilbar)
        t.add(date(Y, M, 1), TYP_EXPENSES, "Miete", 1500.0, "", source="auto_fixcost")
        s, _ = _status(c, b, t, "Miete", Y, M)
        assert s == "abgeschlossen"
    finally:
        conn.close()
        os.remove(p)


def test_fix_only_quick_button_selects_only_real_fixed_costs():
    src = (ROOT / "views" / "recurring_bookings_dialog.py").read_text(encoding="utf-8")
    assert "item.is_fix and item.is_recurring" in src
    assert "Fix-only Kategorien wie Franchise/Selbstbehalt bleiben bewusst außen vor" in src


def test_tracking_picker_shows_child_names_without_parent_prefix():
    """Tracking soll kurz bleiben: Parent ausblenden, Child nur als Blattname anzeigen."""
    conn, p = _fresh()
    try:
        c = CategoryModel(conn)
        parent_id = c.create(TYP_EXPENSES, "Wohnen")
        c.create(TYP_EXPENSES, "Miete", parent_id=parent_id)
        c.create(TYP_EXPENSES, "Internet", parent_id=parent_id)
        c.create(TYP_EXPENSES, "Lebensmittel")

        grouped = c.list_for_tracking_dropdown_grouped(TYP_EXPENSES)
        items = [(label, value) for kind, label, value in grouped if kind == "item"]
        labels = [label for label, _ in items]
        values = [value for _, value in items]

        assert "Wohnen" not in labels
        assert "Wohnen" not in values
        assert "Miete" in labels
        assert "Internet" in labels
        assert "Wohnen › Miete" not in labels
        assert "Wohnen - Miete" not in labels
        assert "Lebensmittel" in labels
    finally:
        conn.close()
        os.remove(p)


def test_tracker_dialog_keeps_unlisted_preset_category_editable_fallback():
    """v2.1.7-Blocker-Schutz: ``_set_combo_by_data`` braucht den
    Editable-Fallback, damit alte Buchungen auf Parent-Kategorien beim
    Bearbeiten nicht still auf den ersten Picker-Eintrag umgehängt werden."""
    src = (ROOT / "views" / "tracker_dialog.py").read_text(encoding="utf-8")
    marker = src.split("def _set_combo_by_data", 1)[1].split("def ", 1)[0]
    assert "isEditable()" in marker
    assert "setEditText(value)" in marker
    assert "setCurrentIndex(-1)" in marker
