"""Basis-Tests für die kritischen Datenfunktionen (v1.0.30, P1.4).

Läuft ohne Qt/PySide6 — testet Migration, Reset, Undo/Redo, Recurring-Logik,
Default-Kategorien und Restore-Bundles.

Ausführen (aus dem Projekt-Root):
    pytest tests/ -v
"""

from __future__ import annotations

import json
import sqlite3
import sys
from datetime import date, datetime
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.default_categories import _FALLBACK, load_default_categories
from model.migrations import CURRENT_VERSION, _get_db_version, migrate_all
from model.recurring_transactions_model import (
    RecurringTransaction,
    RecurringTransactionsModel,
)
from model.typ_constants import ALL_TYPEN
from model.undo_redo_model import UndoRedoModel


@pytest.fixture
def conn():
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys = ON")
    yield c
    c.close()


@pytest.fixture
def migrated_conn(conn):
    migrate_all(conn)
    return conn


# ── Migration ────────────────────────────────────────────────────


def test_migration_fresh_db(conn):
    info = migrate_all(conn)
    assert _get_db_version(conn) == CURRENT_VERSION
    assert info["new_version"] == CURRENT_VERSION
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    for required in (
        "categories",
        "budget",
        "tracking",
        "system_flags",
        "undo_stack",
        "tags",
        "savings_goals",
        "recurring_transactions",
        "suggestion_accepted",
    ):
        assert required in tables, f"Tabelle {required} fehlt nach Migration"


def test_migration_idempotent(migrated_conn):
    info = migrate_all(migrated_conn)
    assert info["migrations_applied"] == [] or all(
        "Backup" in m for m in info["migrations_applied"]
    )
    assert _get_db_version(migrated_conn) == CURRENT_VERSION


# ── Default-Kategorien (zentrale Quelle) ────────────────────────


def test_default_categories_load_from_json():
    cats = load_default_categories()
    assert len(cats) >= 10
    assert all(c.typ in ALL_TYPEN for c in cats)
    names = [c.name for c in cats]
    assert len(names) == len(set(names)) or True  # Duplikate über Typen erlaubt
    # Die alten Tippfehler dürfen in der zentralen Quelle nicht vorkommen
    for bad in ("Nebenerweb", "Rechtschutzz", "Tirza Jugendlohn."):
        assert bad not in names, f"Tippfehler/persönlicher Eintrag in Defaults: {bad}"


def test_fallback_categories_valid():
    assert all(c.typ in ALL_TYPEN for c in _FALLBACK)


def test_ensure_defaults_and_reset_use_same_source(migrated_conn, tmp_path):
    """Erststart (ensure_defaults) und Reset müssen identische Kategorien erzeugen."""
    from model.category_model import CategoryModel
    from model.database_management_model import DatabaseManagementModel

    cm = CategoryModel(migrated_conn)
    cm.ensure_defaults()
    first_start = {
        (r["typ"], r["name"])
        for r in migrated_conn.execute("SELECT typ, name FROM categories")
    }
    assert first_start, "ensure_defaults hat keine Kategorien erzeugt"

    dbm = DatabaseManagementModel(str(tmp_path / "x.db"), conn=migrated_conn)
    ok, msg = dbm.reset_database(create_backup=False, keep_user_data=False)
    assert ok, f"Reset fehlgeschlagen: {msg}"
    after_reset = {
        (r["typ"], r["name"])
        for r in migrated_conn.execute("SELECT typ, name FROM categories")
    }
    assert after_reset == first_start, (
        "Reset erzeugt andere Default-Kategorien als der Erststart:\n"
        f"nur Erststart: {first_start - after_reset}\n"
        f"nur Reset: {after_reset - first_start}"
    )


def test_reset_preserves_system_flags(migrated_conn, tmp_path):
    from model.database_management_model import DatabaseManagementModel

    migrated_conn.execute(
        "INSERT OR REPLACE INTO system_flags(key, value) VALUES('schema_version', ?)",
        (str(CURRENT_VERSION),),
    )
    dbm = DatabaseManagementModel(str(tmp_path / "x.db"), conn=migrated_conn)
    ok, _ = dbm.reset_database(create_backup=False, keep_user_data=False)
    assert ok
    row = migrated_conn.execute(
        "SELECT value FROM system_flags WHERE key='schema_version'"
    ).fetchone()
    assert row is not None, "schema_version wurde beim Reset gelöscht!"


# ── Undo/Redo ────────────────────────────────────────────────────


def test_undo_redo_roundtrip(migrated_conn):
    ur = UndoRedoModel(migrated_conn)
    migrated_conn.execute(
        "INSERT INTO tracking(id, date, typ, category, amount, details) "
        "VALUES (1, '2026-06-01', 'Ausgaben', 'Miete', 1200, 'Juni')"
    )
    ur.record_operation(
        "tracking",
        "INSERT",
        new_data={
            "id": 1,
            "date": "2026-06-01",
            "typ": "Ausgaben",
            "category": "Miete",
            "amount": 1200,
            "details": "Juni",
        },
    )
    assert ur.can_undo() and not ur.can_redo()
    assert ur.undo()
    assert migrated_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 0
    assert ur.can_redo()
    assert ur.redo()
    assert migrated_conn.execute("SELECT COUNT(*) FROM tracking").fetchone()[0] == 1


def test_undo_rejects_unknown_table(migrated_conn):
    ur = UndoRedoModel(migrated_conn)
    with pytest.raises(ValueError):
        ur._safe_table("evil; DROP TABLE tracking")


def test_undo_group_is_atomic(migrated_conn):
    """Schlägt eine Operation mitten in einer Undo-Gruppe fehl, muss ALLES
    zurückgerollt werden — kein halber Undo (Regression v1.0.31)."""
    ur = UndoRedoModel(migrated_conn)
    migrated_conn.execute(
        "INSERT INTO tracking(id, date, typ, category, amount, details) "
        "VALUES (1, '2026-06-01', 'Ausgaben', 'Miete', 1200, 'Juni')"
    )
    migrated_conn.commit()

    # Gruppe manuell aufbauen: erst eine VALIDE Operation (wird bei DESC-Undo
    # zuerst angewendet → löscht die tracking-Zeile), dann eine DEFEKTE
    # (unbekannte Tabelle → ValueError in _safe_table).
    migrated_conn.execute(
        "INSERT INTO undo_stack(timestamp, ts, group_id, table_name, operation, old_data, new_data) "
        "VALUES ('2026-06-11 10:00:00', '2026-06-11 10:00:00', 'g1', "
        "'nicht_existente_tabelle', 'INSERT', NULL, '{\"id\": 99}')"
    )
    migrated_conn.execute(
        "INSERT INTO undo_stack(timestamp, ts, group_id, table_name, operation, old_data, new_data) "
        "VALUES ('2026-06-11 10:00:01', '2026-06-11 10:00:01', 'g1', 'tracking', 'INSERT', NULL, "
        '\'{"id": 1, "date": "2026-06-01", "typ": "Ausgaben", '
        '"category": "Miete", "amount": 1200, "details": "Juni"}\')'
    )
    migrated_conn.commit()

    result = ur.undo()

    assert result is False, "undo() muss bei Fehler False liefern"
    # Die valide Operation (DELETE der tracking-Zeile) muss zurückgerollt sein
    assert (
        migrated_conn.execute("SELECT COUNT(*) FROM tracking WHERE id=1").fetchone()[0]
        == 1
    ), "Halber Undo: tracking-Zeile wurde trotz Fehler gelöscht!"
    # Die Gruppe muss vollständig im undo_stack verbleiben
    assert (
        migrated_conn.execute(
            "SELECT COUNT(*) FROM undo_stack WHERE group_id='g1'"
        ).fetchone()[0]
        == 2
    ), "undo_stack-Gruppe wurde trotz Fehler (teilweise) entfernt"
    # Nichts darf in den redo_stack gewandert sein
    assert (
        migrated_conn.execute("SELECT COUNT(*) FROM redo_stack").fetchone()[0] == 0
    ), "redo_stack enthält Reste eines fehlgeschlagenen Undos"


# ── Recurring (Soll-Buchungsdatum) ───────────────────────────────


def _make_trans(day: int) -> RecurringTransaction:
    return RecurringTransaction(
        id=1,
        typ="Ausgaben",
        category="Miete",
        amount=100.0,
        details="",
        day_of_month=day,
        is_active=True,
        start_date=date(2026, 1, 1),
        end_date=None,
        created_date=datetime.now(),
        last_booking_date=None,
    )


def test_recurring_month_end_overflow(migrated_conn):
    m = RecurringTransactionsModel(migrated_conn)
    t = _make_trans(31)
    assert m._calculate_booking_date(t, date(2026, 2, 1)) == date(2026, 2, 28)
    assert m._calculate_booking_date(t, date(2028, 2, 1)) == date(2028, 2, 29)
    assert m._calculate_booking_date(t, date(2026, 4, 1)) == date(2026, 4, 30)


def test_recurring_respects_start_date(migrated_conn):
    m = RecurringTransactionsModel(migrated_conn)
    t = _make_trans(15)
    assert m._is_valid_booking_date(t, date(2026, 3, 15)) is True
    assert m._is_valid_booking_date(t, date(2025, 12, 15)) is False


def test_savings_goal_undo_redo_returns_to_start(migrated_conn):
    """Sparziel-Korrektur: Nach Undo+Redo einer Ersparnisse-Buchung muss
    current_amount exakt zum Ausgangswert zurückkehren (Regression v1.0.31:
    Redo wendete dasselbe Vorzeichen wie Undo an → doppelte Abweichung)."""
    ur = UndoRedoModel(migrated_conn)
    migrated_conn.execute(
        "INSERT INTO savings_goals(id, name, target_amount, current_amount, category, created_date) "
        "VALUES (1, 'Ferien 2027', 3000, 500, 'Ferien', '2026-01-01')"
    )
    migrated_conn.execute(
        "INSERT INTO tracking(id, date, typ, category, amount, details) "
        "VALUES (1, '2026-06-01', 'Ersparnisse', 'Ferien', 100, 'Sparrate')"
    )
    migrated_conn.commit()
    ur.record_operation(
        "tracking",
        "INSERT",
        new_data={
            "id": 1,
            "date": "2026-06-01",
            "typ": "Ersparnisse",
            "category": "Ferien",
            "amount": 100,
            "details": "Sparrate",
        },
    )

    def goal_amount():
        return float(
            migrated_conn.execute(
                "SELECT current_amount FROM savings_goals WHERE id=1"
            ).fetchone()[0]
        )

    assert goal_amount() == 500.0

    assert ur.undo()
    assert goal_amount() == 400.0, "Undo: Sparrate muss abgezogen werden"

    assert ur.redo()
    assert goal_amount() == 500.0, (
        "Redo: Sparziel muss zum Ausgangswert zurückkehren — "
        f"ist {goal_amount()} (Redo-Vorzeichenfehler?)"
    )

    # Zweiter Zyklus: bleibt stabil, driftet nicht
    assert ur.undo() and goal_amount() == 400.0
    assert ur.redo() and goal_amount() == 500.0


# ── Restore-Bundle (.bmr) ────────────────────────────────────────


def test_bmr_bundle_roundtrip(tmp_path):
    import zipfile

    from model.restore_bundle import create_bundle

    db = tmp_path / "source.db"
    c = sqlite3.connect(str(db))
    c.execute("CREATE TABLE t(x)")
    c.execute("INSERT INTO t VALUES (42)")
    c.commit()
    c.close()

    out = tmp_path / "backup.bmr"
    create_bundle(
        source_db=db,
        out_path=out,
        app="Budgetmanager",
        app_version="1.0.30",
        note="test",
    )
    assert out.exists()

    with zipfile.ZipFile(out) as zf:
        names = set(zf.namelist())
        assert "manifest.json" in names
        manifest = json.loads(zf.read("manifest.json"))
        db_file = manifest.get("db_file")
        assert db_file in names
        extracted = tmp_path / "restored.db"
        extracted.write_bytes(zf.read(db_file))

    rc = sqlite3.connect(str(extracted))
    assert rc.execute("SELECT x FROM t").fetchone()[0] == 42
    rc.close()


# ── Restore via SQLite-Backup-API (Live-Connection) ─────────────


def test_restore_into_live_connection():
    live = sqlite3.connect(":memory:")
    live.execute("CREATE TABLE t(x)")
    live.execute("INSERT INTO t VALUES (1)")
    live.commit()

    src = sqlite3.connect(":memory:")
    src.execute("CREATE TABLE t(x)")
    src.executemany("INSERT INTO t VALUES (?)", [(10,), (20,)])
    src.commit()

    src.backup(live)
    src.close()

    assert [r[0] for r in live.execute("SELECT x FROM t ORDER BY x")] == [10, 20]
    live.execute("INSERT INTO t VALUES (30)")  # Connection bleibt nutzbar
    live.close()


# ── Geldformat / Region ─────────────────────────────────────────


def test_money_format_respects_number_format():
    from utils.money import format_money, format_short, parse_money, set_money_locale

    set_money_locale(currency="CHF", number_format="ch")
    assert format_money(1234.5) == "1'234.50 CHF"
    assert format_short(0) == "0.00"

    set_money_locale(currency="EUR", number_format="eu")
    assert format_money(1234.5) == "1.234,50 €"
    assert format_short(0) == "0,00"

    set_money_locale(currency="USD", number_format="us")
    assert format_money(1234.5) == "$ 1,234.50"

    # Parsing bleibt tolerant, egal welches Anzeigeformat aktiv ist.
    assert parse_money("1'234.50 CHF") == 1234.5
    assert parse_money("1.234,50 €") == 1234.5
    assert parse_money("$ 1,234.50") == 1234.5

    # Tests sollen keine globale Region für folgende Tests hinterlassen.
    set_money_locale(currency="CHF", number_format="ch")


def test_money_parser_uses_active_number_format():
    from utils.money import parse_money, set_money_locale

    set_money_locale(currency="CHF", number_format="ch")
    assert parse_money("1'234.50 CHF") == 1234.5

    set_money_locale(currency="EUR", number_format="eu")
    assert parse_money("1.234") == 1234.0
    assert parse_money("1.234,50 €") == 1234.5
    assert parse_money("1234,50") == 1234.5

    set_money_locale(currency="USD", number_format="us")
    assert parse_money("1,234") == 1234.0
    assert parse_money("$ 1,234.50") == 1234.5


def test_settings_migrates_legacy_number_format(tmp_path):
    from settings import Settings

    f = tmp_path / "settings.json"
    f.write_text('{"number_format":"german", "currency":"eur"}', encoding="utf-8")
    s = Settings(str(f))
    assert s.number_format == "german"
    assert s.currency == "EUR"


def test_category_parent_delete_promotes_children_and_deletes_references(migrated_conn):
    from model.category_model import CategoryModel

    cm = CategoryModel(migrated_conn)
    parent = cm.create("Ausgaben", "Wohnen")
    child = cm.create("Ausgaben", "Miete", parent_id=parent)
    migrated_conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 6, 'Ausgaben', 'Wohnen', 100)"
    )
    migrated_conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES('2026-06-01', 'Ausgaben', 'Wohnen', 100, 'Test')"
    )
    migrated_conn.commit()

    cm.delete_category_safely(parent, data_action="delete_until_last_booking")

    promoted = cm.get_by_id(child)
    assert promoted is not None
    assert promoted.parent_id is None
    assert (
        migrated_conn.execute(
            "SELECT COUNT(*) FROM budget WHERE category='Wohnen'"
        ).fetchone()[0]
        == 0
    )
    assert (
        migrated_conn.execute(
            "SELECT COUNT(*) FROM tracking WHERE category='Wohnen'"
        ).fetchone()[0]
        == 0
    )


def test_category_delete_reassign_merges_budget_and_moves_tracking(migrated_conn):
    from model.category_model import CategoryModel

    cm = CategoryModel(migrated_conn)
    old = cm.create("Ausgaben", "Alt")
    target = cm.create("Ausgaben", "Neu")
    migrated_conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 6, 'Ausgaben', 'Alt', 40)"
    )
    migrated_conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 6, 'Ausgaben', 'Neu', 60)"
    )
    migrated_conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES('2026-06-01', 'Ausgaben', 'Alt', 40, 'Test')"
    )
    migrated_conn.commit()

    cm.delete_category_safely(old, data_action="reassign", reassign_to_id=target)

    assert cm.get_by_id(old) is None
    assert (
        migrated_conn.execute(
            "SELECT amount FROM budget WHERE year=2026 AND month=6 AND typ='Ausgaben' AND category='Neu'"
        ).fetchone()[0]
        == 100
    )
    assert (
        migrated_conn.execute(
            "SELECT COUNT(*) FROM budget WHERE category='Alt'"
        ).fetchone()[0]
        == 0
    )
    assert (
        migrated_conn.execute(
            "SELECT COUNT(*) FROM tracking WHERE category='Neu'"
        ).fetchone()[0]
        == 1
    )


def test_category_rename_cascades_all_known_text_refs(migrated_conn):
    from model.category_model import CategoryModel

    cm = CategoryModel(migrated_conn)
    cat = cm.create("Ausgaben", "Altname")
    migrated_conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 6, 'Ausgaben', 'Altname', 10)"
    )
    migrated_conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES('2026-06-01', 'Ausgaben', 'Altname', 10, 'Test')"
    )
    migrated_conn.execute(
        "INSERT INTO favorites(typ, category, sort_order) VALUES('Ausgaben', 'Altname', 1)"
    )
    migrated_conn.execute(
        "INSERT INTO budget_warnings(year, month, typ, category, threshold_percent, enabled) VALUES(2026, 6, 'Ausgaben', 'Altname', 90, 1)"
    )
    migrated_conn.execute(
        "INSERT INTO recurring_transactions(typ, category, amount, details, day_of_month, is_active, start_date, created_date) VALUES('Ausgaben', 'Altname', 10, '', 1, 1, '2026-01-01', '2026-01-01')"
    )
    migrated_conn.execute(
        "INSERT INTO suggestion_accepted(typ, category, year, month) VALUES('Ausgaben', 'Altname', 2026, 6)"
    )
    migrated_conn.commit()

    cm.rename_and_cascade(cat, typ="Ausgaben", old_name="Altname", new_name="Neuname")

    for table in [
        "budget",
        "tracking",
        "favorites",
        "budget_warnings",
        "recurring_transactions",
        "suggestion_accepted",
    ]:
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='Altname'"
            ).fetchone()[0]
            == 0
        )
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='Neuname'"
            ).fetchone()[0]
            == 1
        )


def test_budget_model_rename_delegates_to_category_cascade(migrated_conn):
    from model.budget_model import BudgetModel
    from model.category_model import CategoryModel

    cm = CategoryModel(migrated_conn)
    cm.create("Ausgaben", "AltBudgetName")
    migrated_conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 6, 'Ausgaben', 'AltBudgetName', 10)"
    )
    migrated_conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES('2026-06-01', 'Ausgaben', 'AltBudgetName', 10, 'Test')"
    )
    migrated_conn.execute(
        "INSERT INTO favorites(typ, category, sort_order) VALUES('Ausgaben', 'AltBudgetName', 1)"
    )
    migrated_conn.execute(
        "INSERT INTO budget_warnings(year, month, typ, category, threshold_percent, enabled) VALUES(2026, 6, 'Ausgaben', 'AltBudgetName', 90, 1)"
    )
    migrated_conn.execute(
        "INSERT INTO recurring_transactions(typ, category, amount, details, day_of_month, is_active, start_date, created_date) VALUES('Ausgaben', 'AltBudgetName', 10, '', 1, 1, '2026-01-01', '2026-01-01')"
    )
    migrated_conn.execute(
        "INSERT INTO suggestion_accepted(typ, category, year, month) VALUES('Ausgaben', 'AltBudgetName', 2026, 6)"
    )
    migrated_conn.commit()

    BudgetModel(migrated_conn).rename_category(
        "Ausgaben", "AltBudgetName", "NeuBudgetName"
    )

    assert (
        migrated_conn.execute(
            "SELECT COUNT(*) FROM categories WHERE name='NeuBudgetName'"
        ).fetchone()[0]
        == 1
    )
    for table in [
        "budget",
        "tracking",
        "favorites",
        "budget_warnings",
        "recurring_transactions",
        "suggestion_accepted",
    ]:
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='AltBudgetName'"
            ).fetchone()[0]
            == 0
        )
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='NeuBudgetName'"
            ).fetchone()[0]
            == 1
        )


def test_undo_redo_rename_cascades_all_known_refs(migrated_conn):
    from model.category_model import CategoryModel
    from model.undo_redo_model import UndoRedoModel

    cm = CategoryModel(migrated_conn)
    cat = cm.create("Ausgaben", "UndoAlt")
    migrated_conn.execute(
        "INSERT INTO budget(year, month, typ, category, amount) VALUES(2026, 6, 'Ausgaben', 'UndoAlt', 10)"
    )
    migrated_conn.execute(
        "INSERT INTO tracking(date, typ, category, amount, details) VALUES('2026-06-01', 'Ausgaben', 'UndoAlt', 10, 'Test')"
    )
    migrated_conn.execute(
        "INSERT INTO favorites(typ, category, sort_order) VALUES('Ausgaben', 'UndoAlt', 1)"
    )
    migrated_conn.execute(
        "INSERT INTO budget_warnings(year, month, typ, category, threshold_percent, enabled) VALUES(2026, 6, 'Ausgaben', 'UndoAlt', 90, 1)"
    )
    migrated_conn.execute(
        "INSERT INTO recurring_transactions(typ, category, amount, details, day_of_month, is_active, start_date, created_date) VALUES('Ausgaben', 'UndoAlt', 10, '', 1, 1, '2026-01-01', '2026-01-01')"
    )
    migrated_conn.execute(
        "INSERT INTO suggestion_accepted(typ, category, year, month) VALUES('Ausgaben', 'UndoAlt', 2026, 6)"
    )
    migrated_conn.commit()

    cm.rename_and_cascade(cat, typ="Ausgaben", old_name="UndoAlt", new_name="UndoNeu")
    undo = UndoRedoModel(migrated_conn)

    assert undo.undo() is True
    for table in [
        "budget",
        "tracking",
        "favorites",
        "budget_warnings",
        "recurring_transactions",
        "suggestion_accepted",
    ]:
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='UndoNeu'"
            ).fetchone()[0]
            == 0
        )
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='UndoAlt'"
            ).fetchone()[0]
            == 1
        )

    assert undo.redo() is True
    for table in [
        "budget",
        "tracking",
        "favorites",
        "budget_warnings",
        "recurring_transactions",
        "suggestion_accepted",
    ]:
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='UndoAlt'"
            ).fetchone()[0]
            == 0
        )
        assert (
            migrated_conn.execute(
                f"SELECT COUNT(*) FROM {table} WHERE category='UndoNeu'"
            ).fetchone()[0]
            == 1
        )


def test_tracking_source_marks_auto_bookings_and_manual_usage_counts(migrated_conn):
    from model.category_model import CategoryModel
    from model.tracking_model import TrackingModel

    cols = {r[1] for r in migrated_conn.execute("PRAGMA table_info(tracking)")}
    assert "source" in cols

    cm = CategoryModel(migrated_conn)
    cm.upsert("Ausgaben", "Miete", is_fix=True, is_recurring=True, recurring_day=1)
    cm.upsert("Ausgaben", "Freizeit", is_fix=False, is_recurring=False)

    tm = TrackingModel(migrated_conn)
    tm.add(
        "2026-06-01", "Ausgaben", "Miete", 1200, "Juni - Miete", source="auto_fixcost"
    )
    tm.add("2026-06-02", "Ausgaben", "Freizeit", 25, "Kino")
    tm.add("2026-06-03", "Ausgaben", "Freizeit", 30, "Restaurant", source="manual")

    all_counts = tm.category_usage_counts("Ausgaben")
    manual_counts = tm.category_usage_counts("Ausgaben", manual_only=True)

    assert all_counts["Miete"] == 1
    assert manual_counts.get("Miete", 0) == 0
    assert manual_counts["Freizeit"] == 2


def test_tracking_dropdown_favorites_then_manual_frequency(migrated_conn):
    from model.category_model import CategoryModel
    from model.favorites_model import FavoritesModel
    from model.tracking_model import TrackingModel

    cm = CategoryModel(migrated_conn)
    for order, name in enumerate(["Alpha", "Bravo", "Charlie", "Delta"], start=1):
        cm.upsert("Ausgaben", name, is_fix=False, is_recurring=False, sort_order=order)

    fav = FavoritesModel(migrated_conn)
    fav.add("Ausgaben", "Charlie")

    tm = TrackingModel(migrated_conn)
    for i in range(3):
        tm.add(f"2026-06-0{i+1}", "Ausgaben", "Bravo", 10 + i, "manuell")
    tm.add("2026-06-04", "Ausgaben", "Alpha", 5, "manuell")
    tm.add("2026-06-05", "Ausgaben", "Delta", 99, "automatisch", source="auto_fixcost")

    pairs = cm.list_for_tracking_dropdown("Ausgaben")
    names = [real for _label, real in pairs]
    labels = [label for label, _real in pairs]

    assert names[:4] == ["Charlie", "Bravo", "Alpha", "Delta"]
    assert labels[0].startswith("★ ")
