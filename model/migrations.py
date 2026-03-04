from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime

# Aktuelle Schema-Version
CURRENT_VERSION = 11
def _cols(conn: sqlite3.Connection, table: str) -> set[str]:
    """Gibt alle Spaltennamen einer Tabelle zurück"""
    try:
        cur = conn.execute(f"PRAGMA table_info({table});")
        return {row[1] for row in cur.fetchall()}
    except sqlite3.OperationalError:
        return set()

def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    """Prüft ob eine Tabelle existiert"""
    cur = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (table,)
    )
    return cur.fetchone() is not None

def _get_db_version(conn: sqlite3.Connection) -> int:
    """Gibt die aktuelle Datenbank-Version zurück"""
    if not _table_exists(conn, "system_flags"):
        return 0
    
    try:
        cur = conn.execute(
            "SELECT value FROM system_flags WHERE key='schema_version'"
        )
        row = cur.fetchone()
        return int(row[0]) if row else 0
    except (sqlite3.OperationalError, ValueError, TypeError):
        return 0

def _set_db_version(conn: sqlite3.Connection, version: int) -> None:
    """Setzt die Datenbank-Version"""
    conn.execute(
        "INSERT OR REPLACE INTO system_flags (key, value) VALUES ('schema_version', ?)",
        (str(version),)
    )
    conn.commit()

def _create_migration_backup(db_path: str, backup_dir: str = None) -> str:
    """Erstellt ein Backup vor der Migration"""
    if not db_path or not Path(db_path).exists():
        return ""
    
    # Backup-Ordner aus Einstellungen oder Standard
    if backup_dir is None:
        backup_dir = str(Path.home() / "BudgetManager_Backups")
    
    backup_path_obj = Path(backup_dir)
    backup_path_obj.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_name = f"budgetmanager_pre_migration_{timestamp}.bmr"
    backup_path = backup_path_obj / backup_name

    try:
        from model.restore_bundle import create_bundle
        from app_info import APP_NAME, APP_VERSION
        create_bundle(
            source_db=Path(db_path),
            out_path=backup_path,
            app=APP_NAME,
            app_version=APP_VERSION,
            note="Pre Migration",
        )
        return str(backup_path)
    except Exception as e:
        logger.warning("Backup vor Migration konnte nicht erstellt werden: %s", e)
        return ""

def migrate_all(conn: sqlite3.Connection, db_path: str = None, backup_dir: str = None) -> dict:
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
        migrations_applied.append("v6→v7: Kategorien-Baum (parent_id) + Funding + sort_order")

    if old_version < 8:
        _migrate_v7_to_v8(conn)
        migrations_applied.append("v7→v8: Undo/Redo Redo-Stack + Grouping")

    if old_version < 9:
        _migrate_v8_to_v9(conn)
        migrations_applied.append("v8→v9: Performance-Indizes für Tracking & Budget")

    if old_version < 10:
        _migrate_v9_to_v10(conn)
        migrations_applied.append("v9→v10: Sparziele Lebenszyklus (Status/Freigabe/Verbrauch)")

    if old_version < 11:
        _migrate_v10_to_v11(conn)
        migrations_applied.append("v10→v11: suggestion_accepted (Vorschläge pro Monat nicht wiederholen)")

    # Version setzen
    if migrations_applied:
        _set_db_version(conn, CURRENT_VERSION)
    
    return {
        'old_version': old_version,
        'new_version': CURRENT_VERSION,
        'migrations_applied': migrations_applied,
        'backup_created': backup_path
    }

def _migrate_v0_to_v1(conn: sqlite3.Connection) -> None:
    """Migration v0 → v1: Basis-Schema"""
    # categories
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS categories(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            name TEXT NOT NULL,
            UNIQUE(typ, name)
        );
        '''
    )
    
    # budget
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS budget(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            UNIQUE(year, month, typ, category)
        );
        '''
    )
    
    # tracking
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS tracking(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            amount REAL NOT NULL,
            details TEXT
        );
        '''
    )
    
    # Basis-Indizes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_tracking_date ON tracking(date);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_budget_year_typ ON budget(year, typ);")
    
    conn.commit()

def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """Migration v1 → v2: Fixkosten & Wiederkehrend"""
    cols = _cols(conn, "categories")
    
    if "is_fix" not in cols:
        conn.execute("ALTER TABLE categories ADD COLUMN is_fix INTEGER NOT NULL DEFAULT 0;")
    
    if "is_recurring" not in cols:
        conn.execute("ALTER TABLE categories ADD COLUMN is_recurring INTEGER NOT NULL DEFAULT 0;")
    
    if "recurring_day" not in cols:
        conn.execute("ALTER TABLE categories ADD COLUMN recurring_day INTEGER NOT NULL DEFAULT 1;")
    
    conn.commit()

def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """Migration v2 → v3: System-Flags"""
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS system_flags(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        '''
    )
    conn.commit()

def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """Migration v3 → v4: Neue Features (v0.16.0)"""
    
    # Tags
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS tags(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            color TEXT NOT NULL DEFAULT '#3498db'
        );
        '''
    )
    
    # Category Tags
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS category_tags(
            category_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (category_id, tag_id),
            FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        '''
    )
    
    # Budget Warnings
    conn.execute(
        '''
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
        '''
    )
    
    # Favorites
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS favorites(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            UNIQUE(typ, category)
        );
        '''
    )
    
    # Savings Goals
    conn.execute(
        '''
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
        '''
    )
    
    # Undo Stack
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS undo_stack(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            table_name TEXT NOT NULL,
            operation TEXT NOT NULL,
            old_data TEXT,
            new_data TEXT
        );
        '''
    )
    
    # Theme Profiles
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS theme_profiles(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            settings TEXT NOT NULL
        );
        '''
    )
    
    # Neue Indizes
    conn.execute("CREATE INDEX IF NOT EXISTS idx_undo_timestamp ON undo_stack(timestamp);")
    
    conn.commit()

def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """Migration v4 → v5: Wiederkehrende Transaktionen (v0.17.0)"""
    
    # Recurring Transactions Tabelle
    conn.execute(
        '''
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
        '''
    )
    
    # Index für Performance
    conn.execute("CREATE INDEX IF NOT EXISTS idx_recurring_active ON recurring_transactions(is_active, day_of_month);")
    
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
        'categories', 'budget', 'tracking', 'system_flags',
        'tags', 'category_tags', 'entry_tags', 'budget_warnings', 'favorites',
        'savings_goals', 'undo_stack', 'theme_profiles', 'recurring_transactions'
    ]
    
    missing_tables = [
        table for table in expected_tables
        if not _table_exists(conn, table)
    ]
    
    return {
        'current_version': current,
        'target_version': CURRENT_VERSION,
        'needs_migration': current < CURRENT_VERSION or bool(missing_tables),
        'missing_tables': missing_tables
    }



def _migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """Migration v5 → v6: entry_tags Tabelle (Tags ↔ Tracking-Einträge)"""

    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS entry_tags(
            entry_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY (entry_id, tag_id),
            FOREIGN KEY (entry_id) REFERENCES tracking(id) ON DELETE CASCADE,
            FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );
        '''
    )

    conn.execute("CREATE INDEX IF NOT EXISTS idx_entry_tags_entry ON entry_tags(entry_id);")
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
        conn.execute("ALTER TABLE categories ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0;")

    conn.execute("CREATE INDEX IF NOT EXISTS idx_categories_parent_id ON categories(parent_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_categories_funded_by ON categories(funded_by_category_id);")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_categories_sort ON categories(typ, sort_order, name);")

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
                logger.debug("ALTER TABLE undo_stack ADD COLUMN group_id: Spalte bereits vorhanden")
        
        # ts Spalte hinzufügen (für neue undo_redo_model.py)
        # Falls alte 'timestamp' Spalte existiert, kopieren wir die Daten
        if "ts" not in cols:
            try:
                conn.execute("ALTER TABLE undo_stack ADD COLUMN ts TEXT")
                # Daten aus timestamp kopieren falls vorhanden
                if "timestamp" in cols:
                    conn.execute("UPDATE undo_stack SET ts = timestamp WHERE ts IS NULL")
            except sqlite3.OperationalError:
                logger.debug("ALTER TABLE undo_stack ADD COLUMN ts: Spalte bereits vorhanden")

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
        conn.execute("CREATE INDEX IF NOT EXISTS idx_undo_group ON undo_stack(group_id, id)")
    except Exception as e:
        logger.debug("conn.execute('CREATE INDEX IF NOT EXISTS idx_undo_: %s", e)
    try:
        conn.execute("CREATE INDEX IF NOT EXISTS idx_redo_group ON redo_stack(group_id, id)")
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
            conn.execute("ALTER TABLE savings_goals ADD COLUMN status TEXT DEFAULT 'sparend'")
        except sqlite3.OperationalError:
            logger.debug("ALTER TABLE savings_goals ADD COLUMN status: Spalte bereits vorhanden")

    if "released_amount" not in cols:
        try:
            conn.execute("ALTER TABLE savings_goals ADD COLUMN released_amount REAL DEFAULT 0")
        except sqlite3.OperationalError:
            logger.debug("ALTER TABLE savings_goals ADD COLUMN released_amount: Spalte bereits vorhanden")

    if "released_date" not in cols:
        try:
            conn.execute("ALTER TABLE savings_goals ADD COLUMN released_date TEXT")
        except sqlite3.OperationalError:
            logger.debug("ALTER TABLE savings_goals ADD COLUMN released_date: Spalte bereits vorhanden")

    conn.commit()


def _migrate_v10_to_v11(conn: sqlite3.Connection) -> None:
    """Migration v10 → v11: Angenommene Vorschläge tracken (pro Monat nicht wiederholen)."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS suggestion_accepted (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            typ TEXT NOT NULL,
            category TEXT NOT NULL,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            accepted_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(typ, category, year, month)
        )
    """)
    conn.commit()
