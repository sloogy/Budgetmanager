"""v2.2.17 – Logikanalyse: gefundene Fehler und ihre Absicherung.

F1: Ein komplett gebuchter Startmonat darf den Fälligkeiten-Dialog nicht mehr
    blockieren – sonst ist der integrierte Monatswechsel (v2.2.16, K3)
    unerreichbar.
F2: Bearbeiten einer Buchung darf die Merkliste "zuletzt gebuchte Kategorie
    je Typ" nicht verfälschen.
F3: Der "gebucht – Undo"-Statuszeilen-Hinweis gehört nur zum Anlegen.
F4: Die Ergebnis-Statistik nach dem Buchen bezieht sich auf den im Dialog
    gewählten Monat, nicht auf den Startmonat.

Zusätzlich: tools/fresh_logic_audit_100.py sichert die Datenschicht-Invarianten
(source-Erhalt beim Update, Sparziel-Deltas bei Typwechsel, Undo/Redo inkl.
source, Tag-Idempotenz) mit 100 Loops ab.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── F1: Dialog bleibt erreichbar ───────────────────────────────────────────
def test_fully_booked_month_does_not_block_dialog():
    src = _src("views/tabs/tracking_tab.py")
    body = src.split("def add_fixcosts", 1)[1].split("\n    def ", 1)[0]
    # Der alte Abbruch "already_booked -> return" darf nicht mehr existieren:
    assert (
        'tr("tracking.msg.already_booked")' not in body
    ), "Komplett gebuchter Monat darf den Dialog nicht mehr verweigern"
    # Abgebrochen wird nur noch, wenn es GAR keine relevanten Kategorien gibt:
    assert "skipped_existing == 0 and skipped_zero == 0" in body


def test_dialog_shows_empty_hint_and_disables_booking():
    src = _src("views/recurring_bookings_dialog.py")
    fill = src.split("def _fill", 1)[1].split("\n    def ", 1)[0]
    assert "lbl_empty" in fill
    assert 'tr("tracking.msg.no_due_bookings")' in fill
    assert "button.setEnabled(not empty)" in fill


# ── F4: Statistik für den gewählten Monat ──────────────────────────────────
def test_result_stats_use_dialog_month():
    src = _src("views/tabs/tracking_tab.py")
    body = src.split("def add_fixcosts", 1)[1].split("\n    def ", 1)[0]
    assert "current_month()" in body
    assert "_collect_pending(*final_month)" in body
    d = _src("views/recurring_bookings_dialog.py")
    assert "def current_month" in d


# ── F2/F3: Edit hat keine Anlege-Nebenwirkungen ────────────────────────────
def test_edit_mode_has_no_create_side_effects():
    src = _src("views/quick_add_dialog.py")
    save = src.split("def _save_entry", 1)[1].split("\n    def ", 1)[0]
    guard_pos = save.find("if self._edit_row_id is None:")
    assert guard_pos >= 0, "Guard fuer Anlege-Nebenwirkungen fehlt"
    hint_pos = save.find("booked_undo_hint")
    last_pos = save.find("tracking_last_category")
    assert hint_pos > guard_pos, "Undo-Hinweis laeuft auch im Edit-Modus"
    assert last_pos > guard_pos, "last_category wird auch im Edit-Modus gesetzt"


# ── Funktional: die F2-Kernaussage auf der Datenschicht ────────────────────
def test_update_keeps_source_and_savings_in_sync(tmp_path):
    """Kern der Analyse funktional: update erhält source; Typwechsel
    synchronisiert Sparziele exakt (siehe tools/fresh_logic_audit_100.py)."""
    import sys

    sys.path.insert(0, str(ROOT))
    from model.category_model import CategoryModel
    from model.migrations import migrate_all
    from model.savings_goals_model import SavingsGoalsModel
    from model.tracking_model import TrackingModel
    from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    migrate_all(conn)

    cats = CategoryModel(conn)
    tm = TrackingModel(conn)
    sg = SavingsGoalsModel(conn)
    cats.create(TYP_SAVINGS, "Urlaub")
    cats.create(TYP_EXPENSES, "Rest")
    sg.create("Urlaub", 1000.0, category="Urlaub")

    rid = tm.add(
        date(2026, 5, 1), TYP_SAVINGS, "Urlaub", 200.0, "s", source="auto_recurring"
    )
    tm.update(rid, date(2026, 5, 2), TYP_EXPENSES, "Rest", 200.0, "umgebucht")

    row = conn.execute("SELECT * FROM tracking WHERE id=?", (rid,)).fetchone()
    assert row["source"] == "auto_recurring", "source ging beim Update verloren"
    assert (
        abs(float(sg.get_by_category("Urlaub").current_amount)) < 1e-6
    ), "Sparziel nach Wegbuchen nicht zurueckgesetzt"
    conn.close()


def test_fresh_logic_audit_tool_exists_and_covers_new_invariants():
    tool = ROOT / "tools" / "fresh_logic_audit_100.py"
    assert tool.is_file()
    src = tool.read_text(encoding="utf-8")
    for theme in (
        "edit_source",
        "savings_switch",
        "savings_guard",
        "undo_update",
        "tags_idempotent",
    ):
        assert theme in src


def test_recurring_dialog_refresh_code_is_reachable():
    """Regression: Signal/Filter/Status dürfen nicht hinter return stehen."""
    src = _src("views/recurring_bookings_dialog.py")
    setup = src.split("def _setup_ui", 1)[1].split("\n    def ", 1)[0]
    fill = src.split("def _fill", 1)[1].split("\n    def ", 1)[0]
    current = src.split("def current_month", 1)[1].split("\n    def ", 1)[0]
    assert "table.itemChanged.connect" in setup
    assert "self._apply_filters()" in fill
    assert "itemChanged.connect" not in current
    assert "_apply_filters()" not in current


def test_empty_due_month_disables_all_booking_actions():
    src = _src("views/recurring_bookings_dialog.py")
    fill = src.split("def _fill", 1)[1].split("\n    def ", 1)[0]
    for name in ("btn_ok", "btn_all", "btn_none", "btn_overdue_only", "btn_fix_only"):
        assert name in fill
    assert 'tr("tracking.msg.no_due_bookings")' in fill
    assert 'tr("tracking.msg.already_booked")' not in fill
