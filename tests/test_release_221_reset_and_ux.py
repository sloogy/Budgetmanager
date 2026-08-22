"""Regression v2.2.1: Reset-Fixes (Bericht 1–3), Hub-Fehler, Tracking-Komfort.

- Teilreset ("keep_user_data"): Kategorien UND Buchungen bleiben; geleert
  werden nur Budgets + budgetbezogene Nebentabellen (Warnungen, akzeptierte
  Vorschläge, Lernstatus). Vorher wurden Kategorien gelöscht, Tracking blieb
  verwaist zurück.
- Vollreset: leert dynamisch alle Nutzertabellen inkl. tracking_learning_state,
  schützt system_flags, legt Standard-Kategorien neu an.
- Statisch: Setup-Reset führt den Reset direkt aus; Tracking-Tabelle nutzt
  Kurzlabel + Pfad-Tooltip; Schnelleingabe erzwingt Auswahl bei Mehrdeutigkeit;
  Daten-Hub zeigt Fehler sichtbar; Vorschlagsbericht erklärt "Warum?" und
  kennzeichnet Lernvorschläge; Buchung zeigt Undo-Hinweis.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.database_management_model import DatabaseManagementModel
from model.migrations import migrate_all
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _seed(conn):
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) "
        "VALUES(?, 'Essen', 0, 0, 1)",
        (TYP_EXPENSES,),
    )
    conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) "
        "VALUES(2026, 6, ?, 'Essen', 400)",
        (TYP_EXPENSES,),
    )
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) "
        "VALUES('2026-06-10', ?, 'Essen', 123.0, 't', 'manual')",
        (TYP_EXPENSES,),
    )
    cols = [r[1] for r in conn.execute("PRAGMA table_info(budget_warnings)").fetchall()]
    if "year" in cols:
        conn.execute(
            "INSERT INTO budget_warnings(year, month, typ, category, threshold_percent, enabled) "
            "VALUES(2026, 6, ?, 'Essen', 90, 1)",
            (TYP_EXPENSES,),
        )
    else:
        conn.execute(
            "INSERT INTO budget_warnings(typ, category, threshold_percent, enabled) "
            "VALUES(?, 'Essen', 90, 1)",
            (TYP_EXPENSES,),
        )
    conn.execute(
        "INSERT INTO tracking_learning_state(typ, category, status) "
        "VALUES(?, 'Essen', 'ignored')",
        (TYP_EXPENSES,),
    )
    conn.commit()


def _count(conn, table):
    return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def test_partial_reset_keeps_categories_and_tracking(conn):
    _seed(conn)
    mgmt = DatabaseManagementModel("", conn=conn)
    ok, message = mgmt.reset_database(create_backup=False, keep_user_data=True)
    assert ok
    assert message == "database.msg.reset_budget_only"
    # Kategorien + Buchungen bleiben
    assert _count(conn, "tracking") == 1
    assert (
        conn.execute("SELECT COUNT(*) FROM categories WHERE name='Essen'").fetchone()[0]
        == 1
    )
    # Budgets + budgetbezogene Nebentabellen geleert
    assert _count(conn, "budget") == 0
    assert _count(conn, "budget_warnings") == 0
    assert _count(conn, "tracking_learning_state") == 0


def test_full_reset_clears_learning_state_and_keeps_system_flags(conn):
    _seed(conn)
    conn.execute("INSERT OR REPLACE INTO system_flags(key, value) VALUES('probe', '1')")
    conn.commit()
    mgmt = DatabaseManagementModel("", conn=conn)
    ok, _ = mgmt.reset_database(create_backup=False, keep_user_data=False)
    assert ok
    assert _count(conn, "tracking") == 0
    assert _count(conn, "budget") == 0
    assert _count(conn, "tracking_learning_state") == 0
    # system_flags geschützt
    assert (
        conn.execute("SELECT value FROM system_flags WHERE key='probe'").fetchone()[0]
        == "1"
    )
    # Standard-Kategorien wieder vorhanden
    assert _count(conn, "categories") > 0


def test_savings_data_survives_partial_reset(conn):
    conn.execute(
        "INSERT INTO categories(typ, name, is_fix, is_recurring, recurring_day) "
        "VALUES(?, 'Notgroschen', 0, 0, 1)",
        (TYP_SAVINGS,),
    )
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) "
        "VALUES('2026-05-31', ?, 'Notgroschen', 500.0, 't', 'manual')",
        (TYP_SAVINGS,),
    )
    conn.commit()
    ok, _ = DatabaseManagementModel("", conn=conn).reset_database(
        create_backup=False, keep_user_data=True
    )
    assert ok
    assert (
        conn.execute(
            "SELECT COALESCE(SUM(amount),0) FROM tracking WHERE typ=?",
            (TYP_SAVINGS,),
        ).fetchone()[0]
        == 500.0
    )


# ── Statische Zusicherungen ──────────────────────────────────────
def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_reset_executes_directly():
    src = _src("views/setup_assistant_dialog.py")
    assert "mgmt.reset_database(create_backup=True, keep_user_data=False)" in src
    # Der alte Umweg (nur Dialog öffnen) ist raus
    assert "DatabaseManagementDialog(self, self.conn, self.settings)" not in src


def test_tracking_table_uses_short_label_with_path_tooltip():
    src = _src("views/tabs/tracking_tab.py")
    assert "_cat_item.setToolTip(_cat_full)" in src
    assert "QTableWidgetItem(_cat_name)" in src


def test_quickadd_forces_choice_on_ambiguous_query():
    src = _src("views/quick_add_dialog.py")
    assert "quickadd.ambiguous_category" in src
    assert "showPopup" in src
    assert "tracking.booked_undo_hint" in src


def test_hub_shows_errors_visibly():
    src = _src("views/account_data_hub.py")
    assert "lbl_hub_error" in src
    for key in ("hub.error_save_location", "hub.error_action", "hub.error_refresh"):
        assert key in src


def test_adjustment_dialog_explains_and_marks_learning_rows():
    src = _src("views/budget_adjustment_dialog.py")
    for key in (
        "suggestion.why_deficit",
        "suggestion.why_surplus",
        "suggestion.why_learning",
    ):
        assert key in src
    assert '"🆕 {typ_display}"' in src or "🆕 {typ_display}" in src


# ── v2.2.2: Tag-Filter + Express-Setup (statisch) ────────────────
def test_overview_has_tag_filter_wired():
    src = _src("views/tabs/overview_tab.py")
    budget_src = _src("views/tabs/overview_budget_panel.py")
    right_src = _src("views/tabs/overview_right_panel.py")
    tracking_src = _src("model/tracking_model.py")

    assert "tag_filter_combo" in src
    assert "overview.tag_filter_all" in src
    assert "tag_filter_combo.currentIndexChanged.connect" in src
    assert "get_entries_in_range(date_from, date_to, tag_id=tag_id)" in src
    compact_src = "".join(src.split())
    assert (
        "refresh_budget_overview(year,month_idx,self._cat_caches,tag_id=tag_id)"
        in compact_src
    )
    assert "refresh_tabular(" in src and "tag_id=tag_id" in src
    assert "refresh_budget_table(" in src and "tag_id=tag_id" in src
    assert (
        "right_panel.load(date_from, date_to, cat_tree=cat_tree, tag_id=tag_id)" in src
    )

    # Der Filter läuft zentral über TrackingModel/entry_tags und wird in den
    # Listen-/Budgetpanels wiederverwendet, statt im Orchestrator dupliziert.
    assert "SELECT entry_id FROM entry_tags WHERE tag_id = ?" in tracking_src
    assert "def _actual_by_category_for_tag" in budget_src
    assert 'QLabel(tr("header.tags"))' in right_src


def test_tracking_range_accepts_tag_filter(conn):
    from model.tracking_model import TrackingModel
    from model.typ_constants import TYP_EXPENSES

    tag_id = conn.execute(
        "INSERT INTO tags(name, color) VALUES('Urlaub', '#336699')"
    ).lastrowid
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) "
        "VALUES('2026-06-10', ?, 'Essen', 10.0, 'mit tag', 'manual')",
        (TYP_EXPENSES,),
    )
    tagged_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details, source) "
        "VALUES('2026-06-11', ?, 'Essen', 20.0, 'ohne tag', 'manual')",
        (TYP_EXPENSES,),
    )
    conn.execute(
        "INSERT INTO entry_tags(entry_id, tag_id) VALUES(?, ?)", (tagged_id, tag_id)
    )
    conn.commit()

    rows = TrackingModel(conn).get_entries_in_range(
        date(2026, 6, 1), date(2026, 6, 30), tag_id=tag_id
    )
    assert [r.id for r in rows] == [tagged_id]


def test_setup_has_express_path():
    src = _src("views/setup_assistant_dialog.py")
    assert "def _express_setup" in src
    assert "setup.express_confirm" in src
    assert "insert_default_categories" in src
    # Express aktiviert den Lernmodus und springt zur Abschluss-Seite
    assert "cb_setup_learning_enabled.setChecked(True)" in src
    assert "self._set_step(len(self.steps) - 1)" in src


def test_i18n_222_keys_parity():
    import json

    keys = {}
    for lang in ("de", "en", "fr"):
        data = json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8"))
        flat = set()

        def walk(d, p=""):
            for k, v in d.items():
                if isinstance(v, dict):
                    walk(v, p + k + ".")
                else:
                    flat.add(p + k)

        walk(data)
        keys[lang] = flat
        for needle in (
            "overview.tag_filter_all",
            "overview.tag_filter_tip",
            "setup.express_button",
            "setup.express_confirm",
        ):
            assert needle in flat, (lang, needle)
    assert keys["de"] == keys["en"] == keys["fr"]


# ── v2.2.3 (Führung): Nächste Schritte im Cockpit ────────────────
def test_cockpit_next_steps_wired():
    src = _src("views/tabs/cockpit_tab.py")
    assert "def _refresh_next_steps" in src
    assert "from utils.i18n import display_typ, tr, trf" in src
    assert "_missing_count = open_count" in src
    assert "open_count += 1" in src
    for key in (
        "cockpit.next_steps_title",
        "cockpit.next_first_booking",
        "cockpit.next_missing_fix",
        "cockpit.next_past_month_close",
        "cockpit.next_month_close",
        "cockpit.next_all_good",
    ):
        assert key in src, key
    # Empty State und Monatsabschluss-Hinweis nutzen echte Daten
    assert "SELECT COUNT(*) FROM tracking WHERE date >= ? AND date < ?" in src
    assert "list_open_months_before(y, m, limit=12)" in src
    assert "month_close_model.is_closed(y, m)" in src
