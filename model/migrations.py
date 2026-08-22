from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Aktuelle Schema-Version
CURRENT_VERSION = 18


def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    """Gibt alle Spaltennamen einer Tabelle zurück.

    v2.2.25 (d1-Härtung): Der Tabellenname wird strikt als SQL-Identifier
    validiert, bevor er das PRAGMA erreicht – alle Aufrufer sind interne
    Migrationsschritte mit Literalnamen, der Guard schließt das Muster
    strukturell ab (Defense-in-Depth wie category_model._safe_table).
    """
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
        return set()
    try:
        cur = conn.execute(f"PRAGMA table_info({table});")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Prüft ob eine Tabelle existiert"""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
    )
    return cur.fetchone() is not None


def _get_db_version(conn: sqlite3.Connection) -> int:
    """Gibt die aktuelle Datenbank-Version zurück"""
    if not _table_exists(conn, "system_flags"):
        return 0

    try:
        cur = conn.execute("SELECT value FROM system_flags WHERE key='schema_version'")
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except (sqlite3.OperationalError, ValueError, TypeError):
        return 0


def _set_db_version(conn: sqlite3.Connection, version: int) -> None:
    """Setzt die Datenbank-Version"""
    conn.execute(
        "INSERT OR REPLACE INTO system_flags (key, value) VALUES ('schema_version', ?)",
        (str(version),),
    )
    conn.commit()


def _create_migration_backup(db_path: str, backup_dir: str = None) -> str:
    """Erstellt ein Backup vor der Migration"""
    if not db_path or not Path(db_path).exists():
        return ""

    # Backup-Ordner aus Einstellungen oder Standard
    if backup_dir is None:
        from model.app_paths import backups_dir

        backup_dir = str(backups_dir())

    backup_path_obj = Path(backup_dir)
    backup_path_obj.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_name = f"budgetmanager_pre_migration_{timestamp}.bmr"
    backup_path = backup_path_obj / backup_name

    try:
        from app_info import APP_NAME, APP_VERSION
        from model.app_paths import settings_path as _settings_path
        from model.restore_bundle import create_bundle
        from model.user_model import _users_file_path

        u_path = _users_file_path()
        s_path = _settings_path()
        create_bundle(
            source_db=Path(db_path),
            out_path=backup_path,
            app=APP_NAME,
            app_version=APP_VERSION,
            note="Pre Migration",
            settings_path=s_path if s_path.exists() else None,
            users_json_path=u_path if u_path.exists() else None,
        )
        return str(backup_path)
    except Exception as e:
        logger.warning("Backup vor Migration konnte nicht erstellt werden: %s", e)
        return ""


def _migrate_v17_cleanup_orphaned_entry_tags(conn) -> None:
    """v2.2.25 (KILLCRITIC k2): Entfernt verwaiste entry_tags-Zeilen.

    Der Undo-/Redo-Loeschpfad liess bis v2.2.24 Tag-Zuordnungen geloeschter
    Buchungen stehen (PRAGMA foreign_keys ist in SQLite per Default aus,
    CASCADE griff daher nicht). Idempotente Bestandsbereinigung; der
    Schreibpfad ist seit v2.2.25 symmetrisch abgesichert.
    """
    try:
        conn.execute(
            "DELETE FROM entry_tags WHERE entry_id NOT IN" " (SELECT id FROM tracking)"
        )
    except Exception:
        # Tabelle kann in sehr alten Bestaenden fehlen; migrate_all legt
        # sie in frueheren Schritten an.
        pass


def migrate_all(
    conn: sqlite3.Connection, db_path: str = None, backup_dir: str = None
) -> dict:
    """
    Migriert die Datenbank auf die aktuelle Version.

    Returns:
        dict mit Informationen über die Migration:
        {
            'old_version': int,
            'new_version': int,
            'migrations_applied': list[str],
            'backup_created': str (Pfad zum Backup)
        }
    """
    old_version = _get_db_version(conn)
    migrations_applied = []
    backup_path = ""

    # Backup erstellen wenn Migration nötig
    if old_version < CURRENT_VERSION and db_path:
        backup_path = _create_migration_backup(db_path, backup_dir)
        if backup_path:
            migrations_applied.append(f"Backup erstellt: {Path(backup_path).name}")

    # Version 0 → 1: Basis-Schema
    if old_version < 1:
        _migrate_v0_to_v1(conn)
        migrations_applied.append("v0→v1: Basis-Schema erstellt")

    # Version 1 → 2: Fixkosten & Wiederkehrend
    if old_version < 2:
        _migrate_v1_to_v2(conn)
        migrations_applied.append("v1→v2: Fixkosten & Wiederkehrend hinzugefügt")

    # Version 2 → 3: System-Flags
    if old_version < 3:
        _migrate_v2_to_v3(conn)
        migrations_applied.append("v2→v3: System-Flags hinzugefügt")

    # Version 3 → 4: Neue Features (Tags, Favorites, etc.)
    if old_version < 4:
        _migrate_v3_to_v4(conn)
        migrations_applied.append("v3→v4: Tags, Favorites, Sparziele, etc.")

    # Version 4 → 5: Wiederkehrende Transaktionen
    if old_version < 5:
        _migrate_v4_to_v5(conn)
        migrations_applied.append("v4→v5: Wiederkehrende Transaktionen mit Soll-Datum")

    # Version 5 → 6: Entry Tags (Tags ↔ Tracking)
    if old_version < 6:
        _migrate_v5_to_v6(conn)
        migrations_applied.append("v5→v6: entry_tags (Tags ↔ Transaktionen)")
    if old_version < 7:
        _migrate_v6_to_v7(conn)
        migrations_applied.append(
            "v6→v7: Kategorien-Baum (parent_id) + Funding + sort_order"
        )

    if old_version < 8:
        _migrate_v7_to_v8(conn)
        migrations_applied.append("v7→v8: Undo/Redo Redo-Stack + Grouping")

    if old_version < 9:
        _migrate_v8_to_v9(conn)
        migrations_applied.append("v8→v9: Performance-Indizes für Tracking & Budget")

    if old_version < 10:
        _migrate_v9_to_v10(conn)
        migrations_applied.append(
            "v9→v10: Sparziele Lebenszyklus (Status/Freigabe/Verbrauch)"
        )

    if old_version < 11:
        _migrate_v10_to_v11(conn)
        migrations_applied.append(
            "v10→v11: suggestion_accepted (Vorschläge pro Monat nicht wiederholen)"
        )

    if old_version < 12:
        _migrate_v11_to_v12(conn)
        migrations_applied.append("v11→v12: Tracking-Quelle für manuell/automatisch")

    if old_version < 13:
        _migrate_v12_to_v13(conn)
        migrations_applied.append("v12→v13: Forecast-Modus für Pot/inkrementell")

    if old_version < 14:
        _migrate_v13_to_v14(conn)
        migrations_applied.append("v13→v14: Performance-Indizes für Cockpit/Tracking")

    # Version 14 → 15: Tracking-Lernmodus-Status
    if old_version < 15:
        _migrate_v14_to_v15(conn)
        migrations_applied.append(
            "v14→v15: Tracking-Lernmodus-Status (tracking_learning_state)"
        )

    # Version 15 → 16: Tag-Aktionstexte
    if old_version < 16:
        _migrate_v15_to_v16(conn)
        migrations_applied.append("v15→v16: Tag-Aktionstexte für Buchungsdetails")

    if old_version < 17:
        _migrate_v17_cleanup_orphaned_entry_tags(conn)
        migrations_applied.append("v16→v17: verwaiste entry_tags-Zuordnungen bereinigt")

    if old_version < 18:
        _migrate_v17_to_v18(conn)
        migrations_applied.append(
            "v17→v18: Sparziel-Flussbestand, Teilfreigaben und Buchungsarten"
        )

    # Version setzen
    if migrations_applied:
        _set_db_version(conn, CURRENT_VERSION)

    return {
        "old_version": old_version,
        "new_version": CURRENT_VERSION,
        "migrations_applied": migrations_applied,
        "backup_created": backup_path,
    }


def _migrate_v0_to_v1(conn: sqlite3.Connection) -> None:
    """Migration v0 → v1: Basis-Schema"""
    # categories
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(typ, name)
        );
        """
    )

    # budget
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS budget(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            UNIQUE(year, month, typ, category)
        );
        """
    )

    # tracking
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracking(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            details TEXT
        );
        """
    )

    # Basis-Indizes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tracking_date ON tracking(date);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_year_typ ON budget(year, typ);")

    conn.commit()


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migration v1 → v2: Fixkosten & Wiederkehrend"""
    cols = _cols(conn, "categories")

    if "is_fix" not in cols:
        conn.execute(
            "ALTER TABLE categories ADD COLUMN is_fix INTEGER NOT NULL DEFAULT 0;"
        )

    if "is_recurring" not in cols:
        conn.execute(
            "ALTER TABLE categories ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0;"
        )

    if "recurring_day" not in cols:
        conn.execute(
            "ALTER TABLE categories ADD COLUMN recurring_day INTEGER NOT NULL DEFAULT 1;"
        )

    conn.commit()


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migration v2 → v3: System-Flags"""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS system_flags(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    conn.commit()


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Migration v3 → v4: Neue Features (v0.16.0)"""

    # Tags
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tags(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#3498db'
        );
        """
    )

    # Category Tags
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS category_tags(
            category_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (category_id, tag_id),
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        """
    )

    # Budget Warnings
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS budget_warnings(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            threshold_percent INTEGER NOT NULL DEFAULT 90,
            enabled INTEGER NOT NULL DEFAULT 1,
            UNIQUE(year, month, typ, category)
        );
        """
    )

    # Favorites
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS favorites(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(typ, category)
        );
        """
    )

    # Savings Goals
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS savings_goals(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            target_amount REAL NOT NULL,
            current_amount REAL NOT NULL DEFAULT 0,
            deadline TEXT,
            category TEXT,
            notes TEXT,
            created_date TEXT NOT NULL
        );
        """
    )

    # Undo Stack
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS undo_stack(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            old_data TEXT,
            new_data TEXT
        );
        """
    )

    # Theme Profiles
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS theme_profiles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            settings TEXT NOT NULL
        );
        """
    )

    # Neue Indizes
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_undo_timestamp ON undo_stack(timestamp);"
    )

    conn.commit()


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Migration v4 → v5: Wiederkehrende Transaktionen (v0.17.0)"""

    # Recurring Transactions Tabelle
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS recurring_transactions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            details TEXT,
            day_of_month INTEGER NOT NULL,
            is_active INTEGER NOT NULL DEFAULT 1,
            start_date TEXT NOT NULL,
            end_date TEXT,
            created_date TEXT NOT NULL,
            last_booking_date TEXT
        );
        """
    )

    # Index für Performance
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_transactions(is_active, day_of_month);"
    )

    conn.commit()


def _migrate_v11_to_v12(conn: sqlite3.Connection) -> None:
    """Migration v11 → v12: Tracking-Quelle markieren.

    source:
      - manual         = vom Nutzer erfasst/bearbeitet
      - auto_fixcost   = aus Fixkosten/Wiederkehrend-buchen erzeugt
      - auto_recurring = aus wiederkehrender Buchungsliste erzeugt

    Die Spalte ist rückwärtskompatibel mit DEFAULT 'manual', damit alte
    Datenbanken und alte INSERTs ohne source weiter funktionieren.
    """
    cols = _cols(conn, "tracking")
    if "source" not in cols:
        try:
            conn.execute(
                "ALTER TABLE tracking ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'"
            )
        except sqlite3.OperationalError:
            logger.debug(
                "ALTER TABLE tracking ADD COLUMN source: Spalte bereits vorhanden"
            )

    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_tracking_source_typ_cat ON tracking(source, typ, category)"
        )
    except Exception as e:
        logger.debug("idx_tracking_source_typ_cat konnte nicht erstellt werden: %s", e)

    conn.commit()


def _migrate_v17_to_v18(conn: sqlite3.Connection) -> None:
    """Migration v17 → v18: Sparziele als Flussbestand.

    ``current_amount`` bleibt der physisch vorhandene Bestand. Neu werden
    Einzahlungen und Bezüge getrennt geführt. Negative Ersparnisbuchungen
    gelten rückwärtskompatibel standardmässig als Bezug; eine ausdrücklich
    gewählte Korrektur wird über ``tracking.savings_action`` markiert.
    """
    tracking_cols = _cols(conn, "tracking")
    if "savings_action" not in tracking_cols:
        conn.execute("ALTER TABLE tracking ADD COLUMN savings_action TEXT")

    goal_cols = _cols(conn, "savings_goals")
    if "contributed_amount" not in goal_cols:
        conn.execute(
            "ALTER TABLE savings_goals ADD COLUMN contributed_amount REAL NOT NULL DEFAULT 0"
        )
    if "withdrawn_amount" not in goal_cols:
        conn.execute(
            "ALTER TABLE savings_goals ADD COLUMN withdrawn_amount REAL NOT NULL DEFAULT 0"
        )

    # Bestehende Buchungen eindeutig klassifizieren. Positiv = Einzahlung,
    # negativ = Bezug. Erst zukünftige Fehlbuchungskorrekturen erhalten bewusst
    # ``correction`` und werden dadurch nicht als Verwendung ausgewiesen.
    conn.execute(
        """
        UPDATE tracking
        SET savings_action = CASE WHEN amount < 0 THEN 'withdrawal' ELSE 'deposit' END
        WHERE typ = 'Ersparnisse'
          AND (savings_action IS NULL OR TRIM(savings_action) = '')
        """
    )

    # Flusswerte aus dem Trackingbestand rekonstruieren. Manuell erfasste alte
    # Anfangsstände bleiben erhalten, wenn keine passende Buchung existiert.
    conn.execute(
        """
        UPDATE savings_goals
        SET contributed_amount = CASE
                WHEN EXISTS(
                    SELECT 1 FROM tracking t
                    WHERE t.typ='Ersparnisse' AND t.category=savings_goals.category
                ) THEN COALESCE((
                    SELECT SUM(CASE
                        WHEN COALESCE(NULLIF(t.savings_action,''),
                             CASE WHEN t.amount < 0 THEN 'withdrawal' ELSE 'deposit' END)
                             = 'withdrawal'
                        THEN 0 ELSE t.amount END)
                    FROM tracking t
                    WHERE t.typ='Ersparnisse' AND t.category=savings_goals.category
                ), 0)
                ELSE current_amount
            END,
            withdrawn_amount = COALESCE((
                SELECT SUM(CASE
                    WHEN COALESCE(NULLIF(t.savings_action,''),
                         CASE WHEN t.amount < 0 THEN 'withdrawal' ELSE 'deposit' END)
                         = 'withdrawal'
                    THEN ABS(t.amount) ELSE 0 END)
                FROM tracking t
                WHERE t.typ='Ersparnisse' AND t.category=savings_goals.category
            ), 0)
        """
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_tracking_savings_action "
        "ON tracking(typ, category, savings_action)"
    )
    conn.commit()


def get_migration_info(conn: sqlite3.Connection) -> dict:
    """
    Gibt Informationen über den Migrations-Status zurück.

    Returns:
        dict mit:
        {
            'current_version': int,
            'target_version': int,
            'needs_migration': bool,
            'missing_tables': list[str]
        }
    """
    current = _get_db_version(conn)

    # Liste aller erwarteten Tabellen
    expected_tables = [
        "categories",
        "budget",
        "tracking",
        "system_flags",
        "tags",
        "category_tags",
        "entry_tags",
        "budget_warnings",
        "favorites",
        "savings_goals",
        "undo_stack",
        "theme_profiles",
        "recurring_transactions",
    ]

    missing_tables = [
        table for table in expected_tables if not _table_exists(conn, table)
    ]

    return {
        "current_version": current,
        "target_version": CURRENT_VERSION,
        "needs_migration": current < CURRENT_VERSION or bool(missing_tables),
        "missing_tables": missing_tables,
    }


def _migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Migration v5 → v6: entry_tags Tabelle (Tags ↔ Tracking-Einträge)"""

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS entry_tags(
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (entry_id, tag_id),
            FOREIGN KEY (entry_id) REFERENCES tracking(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        """
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_entry_tags_entry ON entry_tags(entry_id);"
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_tags_tag ON entry_tags(tag_id);")

    conn.commit()


def _migrate_v6_to_v7(conn: sqlite3.Connection) -> None:
    """Migration v6 → v7: Kategorien-Baum/Unterkategorien + Funding + Sortierung.

    v6 in 0.18.3 hat entry_tags eingeführt.
    Ab v7 erweitern wir categories um parent_id / funded_by_category_id / sort_order
    und Indizes, damit Tree-UI & spätere Funding-Zuordnung funktionieren.
    """
    cols = _cols(conn, "categories")

    if "parent_id" not in cols:
        conn.execute("ALTER TABLE categories ADD COLUMN parent_id INTEGER;")

    if "funded_by_category_id" not in cols:
        conn.execute("ALTER TABLE categories ADD COLUMN funded_by_category_id INTEGER;")

    if "sort_order" not in cols:
        conn.execute(
            "ALTER TABLE categories ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;"
        )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_categories_funded_by ON categories(funded_by_category_id);"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_categories_sort ON categories(typ, sort_order, name);"
    )

    conn.commit()


def _migrate_v7_to_v8(conn: sqlite3.Connection) -> None:
    """Migration v7 → v8: Redo-Stack + Grouping für Undo/Redo."""
    # undo_stack erweitern
    if _table_exists(conn, "undo_stack"):
        cols = _cols(conn, "undo_stack")

        # group_id Spalte hinzufügen
        if "group_id" not in cols:
            try:
                conn.execute("ALTER TABLE undo_stack ADD COLUMN group_id TEXT")
            except sqlite3.OperationalError:
                logger.debug(
                    "ALTER TABLE undo_stack ADD COLUMN group_id: Spalte bereits vorhanden"
                )

        # ts Spalte hinzufügen (für neue undo_redo_model.py)
        # Falls alte 'timestamp' Spalte existiert, kopieren wir die Daten
        if "ts" not in cols:
            try:
                conn.execute("ALTER TABLE undo_stack ADD COLUMN ts TEXT")
                # Daten aus timestamp kopieren falls vorhanden
                if "timestamp" in cols:
                    conn.execute(
                        "UPDATE undo_stack SET ts = timestamp WHERE ts IS NULL"
                    )
            except sqlite3.OperationalError:
                logger.debug(
                    "ALTER TABLE undo_stack ADD COLUMN ts: Spalte bereits vorhanden"
                )

    # redo_stack Tabelle
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS redo_stack(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            group_id TEXT,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            old_data TEXT,
            new_data TEXT
        );
        """
    )

    # Indizes (optional)
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_undo_group ON undo_stack(group_id, id)"
        )
    except Exception as e:
        logger.debug("conn.execute('CREATE INDEX IF NOT EXISTS idx_undo_: %s", e)
    try:
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_redo_group ON redo_stack(group_id, id)"
        )
    except Exception as e:
        logger.debug("conn.execute('CREATE INDEX IF NOT EXISTS idx_redo_: %s", e)

    conn.commit()


def _migrate_v8_to_v9(conn: sqlite3.Connection) -> None:
    """Migration v8 → v9: Performance-Indizes für häufige Filter-Queries.

    - idx_tracking_date_typ: Beschleunigt Budgetübersicht (Range-Queries nach Datum + Typ)
    - idx_tracking_typ_cat: Beschleunigt Kategorie-Aggregationen
    - idx_budget_composite: Beschleunigt Budget-Lookups (Jahr/Monat/Typ)
    """
    index_defs = [
        "CREATE INDEX IF NOT EXISTS idx_tracking_date_typ ON tracking(date, typ)",
        "CREATE INDEX IF NOT EXISTS idx_tracking_typ_cat ON tracking(typ, category)",
        "CREATE INDEX IF NOT EXISTS idx_budget_composite ON budget(year, month, typ, category)",
    ]
    for stmt in index_defs:
        try:
            conn.execute(stmt)
        except Exception as e:
            logger.debug("conn.execute(stmt): %s", e)

    conn.commit()


def _migrate_v9_to_v10(conn: sqlite3.Connection) -> None:
    """Migration v9 → v10: Sparziele Lebenszyklus.

    Neue Spalten auf savings_goals:
    - status TEXT DEFAULT 'sparend'  (sparend | freigegeben | abgeschlossen)
    - released_amount REAL DEFAULT 0  (eingefrorener Stand bei Freigabe)
    - released_date TEXT              (Datum der Freigabe)
    """
    cols = _cols(conn, "savings_goals")

    if "status" not in cols:
        try:
            conn.execute(
                "ALTER TABLE savings_goals ADD COLUMN status TEXT DEFAULT 'sparend'"
            )
        except sqlite3.OperationalError:
            logger.debug(
                "ALTER TABLE savings_goals ADD COLUMN status: Spalte bereits vorhanden"
            )

    if "released_amount" not in cols:
        try:
            conn.execute(
                "ALTER TABLE savings_goals ADD COLUMN released_amount REAL DEFAULT 0"
            )
        except sqlite3.OperationalError:
            logger.debug(
                "ALTER TABLE savings_goals ADD COLUMN released_amount: Spalte bereits vorhanden"
            )

    if "released_date" not in cols:
        try:
            conn.execute("ALTER TABLE savings_goals ADD COLUMN released_date TEXT")
        except sqlite3.OperationalError:
            logger.debug(
                "ALTER TABLE savings_goals ADD COLUMN released_date: Spalte bereits vorhanden"
            )

    conn.commit()


def _migrate_v10_to_v11(conn: sqlite3.Connection) -> None:
    """Migration v10 → v11: Angenommene Vorschläge tracken (pro Monat nicht wiederholen)."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS suggestion_accepted (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(typ, category, year, month)
        )
    """
    )
    conn.commit()


def _migrate_v12_to_v13(conn: sqlite3.Connection) -> None:
    """Migration v12 → v13: Kategorie-Forecast-Modus.

    ``auto`` bleibt rückwärtskompatibel. Die Engine leitet daraus ab:
    fix+nicht wiederkehrend = Pot, fix/wiederkehrend = inkrementell.
    """
    cols = _cols(conn, "categories")
    if "forecast_mode" not in cols:
        conn.execute(
            "ALTER TABLE categories ADD COLUMN forecast_mode TEXT NOT NULL DEFAULT 'auto';"
        )
    conn.commit()


def _migrate_v13_to_v14(conn: sqlite3.Connection) -> None:
    """Migration v13 → v14: zusätzliche Performance-Indizes.

    Beschleunigt die häufigsten Release-Hotspots:
    - Cockpit-KPIs und Warnungen nach Monatsbereich + Typ/Kategorie
    - Tracking-Filter nach Jahr/Monat ohne substr(date, ...)
    - offene Sparziel-Validierung pro Kategorie
    - budget_warnings im aktuellen Monat
    """
    index_defs = [
        "CREATE INDEX IF NOT EXISTS idx_tracking_date_typ_category ON tracking(date, typ, category)",
        "CREATE INDEX IF NOT EXISTS idx_tracking_typ_category_date ON tracking(typ, category, date)",
        "CREATE INDEX IF NOT EXISTS idx_savings_goals_category_status ON savings_goals(category, status)",
        "CREATE INDEX IF NOT EXISTS idx_budget_warnings_year_month_enabled ON budget_warnings(year, month, enabled)",
        "CREATE INDEX IF NOT EXISTS idx_categories_flags ON categories(is_fix, is_recurring, typ, name)",
    ]
    for stmt in index_defs:
        try:
            conn.execute(stmt)
        except Exception as e:
            logger.debug("Performance-Index konnte nicht erstellt werden: %s", e)
    conn.commit()


def _migrate_v14_to_v15(conn: sqlite3.Connection) -> None:
    """Migration v14 → v15: Statusverwaltung für den Tracking-Lernmodus.

    Speichert Nutzerentscheidungen aus dem Budgetvorschlagsbericht getrennt
    von Budgetwerten. Dadurch kann der Nutzer Lernvorschläge zurückstellen,
    ignorieren oder bewusst als unregelmäßige Rückstellung markieren, ohne die
    normale Budget-Vorschlagslogik zu beeinflussen.
    """
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracking_learning_state(
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'watch',
            snooze_until TEXT,
            changed_at TEXT,
            PRIMARY KEY(typ, category)
        );
        """
    )
    conn.commit()


def _migrate_v15_to_v16(conn: sqlite3.Connection) -> None:
    """Migration v15 → v16: Freier Aktionstext pro Tag.

    Tags können beim Anhaken Buchungsdetails vorschlagen, z. B.
    "{datum} UBS essen". Bestehende Datenbanken bleiben kompatibel.
    """
    cols = _cols(conn, "tags")
    if "action_text" not in cols:
        conn.execute(
            "ALTER TABLE tags ADD COLUMN action_text TEXT NOT NULL DEFAULT '';"
        )
    conn.commit()
