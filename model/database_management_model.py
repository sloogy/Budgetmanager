from __future__ import annotations

"""
Database Management Model - Erweitert mit Reset-Funktionalität
Version 2.3.0.1

Neue Features:
- Datenbank auf Standard zurücksetzen
- Optionale Backup-Erstellung vor Reset
- Standard-Kategorien vordefiniert
"""

import logging
import sqlite3
import os
from pathlib import Path
import shutil
from datetime import datetime
from typing import Any, Tuple, List

logger = logging.getLogger(__name__)

from model.database import open_db
from model.restore_bundle import create_bundle
from app_info import APP_NAME, APP_VERSION


class DatabaseManagementModel:
    """Verwaltung von Datenbank-Operationen inkl. Reset."""

    # Standard-Kategorien die beim Reset erstellt werden
    # DEFAULT_CATEGORIES wurde in v1.0.30 entfernt — zentrale Quelle ist
    # jetzt model/default_categories.py (data/default_categories.json).

    def __init__(self, db_path: str, conn: sqlite3.Connection = None):
        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        # Bestehende Connection nutzen statt eigene zu öffnen
        self._shared_conn = conn

    def _get_conn(self) -> sqlite3.Connection:
        """Gibt die geteilte Connection zurück oder öffnet eine neue als Fallback."""
        if self._shared_conn is not None:
            return self._shared_conn
        return open_db(self.db_path)

    def _close_if_own(self, conn: sqlite3.Connection) -> None:
        """Schließt die Connection nur, wenn sie nicht die geteilte ist."""
        if conn is not self._shared_conn:
            conn.close()

    def create_backup(self, prefix: str = "manual") -> Tuple[bool, Any]:
        """
        Erstellt ein Backup der Datenbank.

        Args:
            prefix: Präfix für Backup-Dateiname

        Returns:
            (success, backup_path_or_error_message)
        """
        try:
            os.makedirs(self.backup_dir, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{prefix}_backup_{timestamp}.bmr"
            backup_path = os.path.join(self.backup_dir, backup_filename)

            src = Path(self.db_path)
            if not src.exists():
                return False, ("database.msg.db_not_found", {"path": str(src)})

            create_bundle(
                source_db=src,
                out_path=Path(backup_path),
                app=APP_NAME,
                app_version=APP_VERSION,
                note=f"DB-Management: {prefix}",
            )

            return True, backup_path
        except Exception as e:
            return False, ("database.msg.backup_failed", {"err": str(e)})

    def get_available_backups(self) -> List[dict]:
        """
        Gibt Liste verfügbarer Backups zurück.

        Returns:
            Liste mit Backup-Informationen
        """
        if not os.path.exists(self.backup_dir):
            return []

        backups = []
        for filename in os.listdir(self.backup_dir):
            if filename.endswith(".bmr"):
                filepath = os.path.join(self.backup_dir, filename)
                stat = os.stat(filepath)
                backups.append(
                    {
                        "filename": filename,
                        "path": filepath,
                        "size": stat.st_size,
                        "created": datetime.fromtimestamp(stat.st_mtime),
                        "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    }
                )

        return sorted(backups, key=lambda x: x["created"], reverse=True)

    # HINWEIS (v1.0.30): Die frühere Methode restore_backup() wurde entfernt.
    # Sie kopierte Backup-Dateien per shutil.copy2 direkt über die aktive DB —
    # ohne Format-Prüfung. Aktuelle Backups sind .bmr-Bundles (ZIP), die so
    # die Datenbank zerstört hätten. Sie wurde nirgends aufgerufen (toter Code).
    # Restore läuft ausschließlich über views/backup_restore_dialog.py
    # (Bundle-Logik + SQLite-Backup-API bzw. verschlüsselter Pfad).

    def reset_database(
        self, create_backup: bool = True, keep_user_data: bool = False
    ) -> Tuple[bool, Any]:
        """
        Setzt Datenbank auf Standard zurück.

        Args:
            create_backup: Backup vor Reset erstellen
            keep_user_data: Wenn True, behält Tracking-Daten (nur Budget/Kategorien zurücksetzen)

        Returns:
            (success, message)
        """
        try:
            # Backup erstellen
            if create_backup:
                success, backup_info = self.create_backup("before_reset")
                if not success:
                    return False, (
                        "database.msg.backup_failed_prefix",
                        {"info": str(backup_info)},
                    )

            conn = self._get_conn()
            cursor = conn.cursor()

            if keep_user_data:
                # v2.2.1 (Bericht-Punkt 2+3): Teilreset sauber definiert.
                # Alte Semantik löschte budget UND categories, liess aber
                # Tracking stehen – Buchungen zeigten danach auf gelöschte
                # Kategorien und 7 Nebentabellen (Warnungen, Favoriten,
                # Wiederkehrend, Vorschlags-/Lernstatus, Tags) behielten
                # Leichen. NEU: "Nur Budgets zurücksetzen" – Kategorien UND
                # Buchungen bleiben vollständig erhalten; geleert werden nur
                # Budgets plus die budgetbezogenen Nebentabellen.
                for table in (
                    "budget",
                    "budget_warnings",
                    "suggestion_accepted",
                    "tracking_learning_state",
                ):
                    try:
                        cursor.execute(f"DELETE FROM {table}")
                    except sqlite3.OperationalError as e:
                        logger.debug("Teilreset %s: %s", table, e)
                message = "database.msg.reset_budget_only"
            else:
                # Kompletter Reset - alle User-Tabellen dynamisch aus DB lesen.
                # Nur SQLite-interne Tabellen und system_flags werden geschützt.
                _NEVER_DELETE = {
                    "sqlite_sequence",
                    "sqlite_stat1",
                    "sqlite_stat2",
                    "sqlite_stat3",
                    "sqlite_stat4",
                    "system_flags",  # Schema-Version & App-Flags – NIE löschen
                }
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
                )
                tables = [
                    row[0]
                    for row in cursor.fetchall()
                    if row[0] not in _NEVER_DELETE and not row[0].startswith("sqlite_")
                ]
                logger.info(
                    "Reset: %d Tabellen werden geleert: %s", len(tables), tables
                )

                for table in tables:
                    # Nochmal gegen interne Tabellen absichern (Defense-in-Depth)
                    if table.startswith("sqlite_") or table in _NEVER_DELETE:
                        logger.warning("DELETE übersprungen (geschützt): %s", table)
                        continue
                    try:
                        cursor.execute(f"DELETE FROM {table}")
                    except sqlite3.OperationalError as e:
                        logger.debug("DELETE FROM %s: %s", table, e)

                message = "database.msg.reset_all"

            # Standard-Kategorien erstellen
            self._create_default_categories(conn)

            conn.commit()
            self._close_if_own(conn)

            return True, message

        except Exception as e:
            return False, f"Fehler beim Reset: {str(e)}"

    def _create_default_categories(self, conn: sqlite3.Connection):
        """Erstellt Standard-Kategorien."""
        cursor = conn.cursor()

        # Prüfe ob categories Tabelle existiert
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='categories'
        """)
        if not cursor.fetchone():
            # Tabelle existiert nicht - erstellen
            cursor.execute("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typ TEXT NOT NULL,
                    name TEXT NOT NULL,
                    parent_id INTEGER DEFAULT NULL,
                    is_fix INTEGER DEFAULT 0,
                    is_recurring INTEGER DEFAULT 0,
                    recurring_day INTEGER DEFAULT 1,
                    forecast_mode TEXT NOT NULL DEFAULT 'auto',
                    is_favorite INTEGER DEFAULT 0,
                    UNIQUE(typ, name),
                    FOREIGN KEY (parent_id) REFERENCES categories(id)
                )
            """)

        # Zentrale Quelle (v1.0.30): identisch mit Erststart (ensure_defaults),
        # damit Reset und Erststart dieselben Kategorien erzeugen.
        # Ab v1.0.34: gemeinsame Insert-Routine inkl. Unterkategorien (parent_id).
        from model.default_categories import insert_default_categories

        insert_default_categories(cursor.connection)

        # Flag setzen, damit ensure_defaults() beim nächsten Start nicht
        # erneut einfügt (gleiche Quelle, aber konsistentes Verhalten).
        try:
            cursor.execute(
                "INSERT OR REPLACE INTO system_flags(key, value) VALUES('defaults_loaded', 'true')"
            )
        except sqlite3.OperationalError:
            logger.debug("system_flags-Tabelle nicht vorhanden — Flag übersprungen")

    def cleanup_database(self) -> Tuple[bool, str, dict]:
        """
        Bereinigt Datenbank (löscht verwaiste Einträge, optimiert).

        Returns:
            (success, message, statistics)
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            MAX_UNDO = 100

            stats = {
                "deleted_orphaned_budgets": 0,
                "deleted_orphaned_tags": 0,
                "deleted_invalid_dates": 0,
                "deleted_reserved_categories": 0,
                "trimmed_undo_stack": 0,
                "cleared_redo_stack": 0,
            }

            # Vorhandene Tabellen ermitteln (für alte DBs die evtl. fehlen)
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            _existing = {row[0] for row in cursor.fetchall()}

            # 1. Lösche Budget-Einträge für nicht existierende Kategorien
            cursor.execute("""
                DELETE FROM budget 
                WHERE NOT EXISTS (
                    SELECT 1 FROM categories 
                    WHERE categories.typ = budget.typ 
                    AND categories.name = budget.category
                )
            """)
            stats["deleted_orphaned_budgets"] = cursor.rowcount

            # 2. Lösche reservierte Kategorien
            reserved_patterns = ["%BUDGET-SALDO%", "%TOTAL%", "%SUMME%", "%📊%"]
            for pattern in reserved_patterns:
                cursor.execute("DELETE FROM budget WHERE category LIKE ?", (pattern,))
                stats["deleted_reserved_categories"] += cursor.rowcount

            # 3. Lösche verwaiste Tags
            cursor.execute("""
                DELETE FROM entry_tags 
                WHERE entry_id NOT IN (SELECT id FROM tracking)
            """)
            stats["deleted_orphaned_tags"] = cursor.rowcount

            # 4. Lösche Tracking-Einträge mit ungültigen Daten
            cursor.execute("""
                DELETE FROM tracking 
                WHERE date IS NULL 
                OR date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            """)
            stats["deleted_invalid_dates"] = cursor.rowcount

            # 5. Undo-Stack auf letzte MAX_UNDO Einträge kürzen
            if "undo_stack" in _existing:
                cursor.execute(
                    "DELETE FROM undo_stack WHERE id NOT IN "
                    "(SELECT id FROM undo_stack ORDER BY id DESC LIMIT ?)",
                    (MAX_UNDO,),
                )
                stats["trimmed_undo_stack"] = cursor.rowcount

            # 6. Redo-Stack komplett leeren (Redo nach Cleanup nicht sinnvoll)
            if "redo_stack" in _existing:
                cursor.execute("DELETE FROM redo_stack")
                stats["cleared_redo_stack"] = cursor.rowcount

            conn.commit()

            # 7. VACUUM separat (kann nicht in Transaktion laufen)
            try:
                cursor.execute("VACUUM")
            except sqlite3.OperationalError as e:
                logger.debug("VACUUM übersprungen (aktive Statements): %s", e)

            self._close_if_own(conn)

            total_deleted = sum(stats.values())
            message = f"Bereinigung abgeschlossen: {total_deleted} Einträge gelöscht"

            return True, message, stats

        except Exception as e:
            return False, f"Fehler bei Bereinigung: {str(e)}", {}

    def get_database_statistics(self) -> dict:
        """
        Gibt umfassende Statistiken über die Datenbank zurück.

        Returns:
            Dictionary mit Statistiken (Größe, Zählungen, Tabellen, Jahre).
        """
        try:
            conn = self._get_conn()
            cursor = conn.cursor()

            stats: dict = {}

            # Dateigröße
            file_size = os.path.getsize(self.db_path)
            stats["db_size_kb"] = round(file_size / 1024, 1)
            stats["db_size_mb"] = round(file_size / (1024 * 1024), 2)

            # Vorhandene Tabellen
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            stats["tables"] = [row[0] for row in cursor.fetchall()]

            # Tabellen-Zählungen
            count_tables = {
                "categories": "Kategorien",
                "budget": "Budget-Einträge",
                "tracking": "Buchungen",
                "savings_goals": "Sparziele",
                "tags": "Tags",
                "entry_tags": "Tag-Zuweisungen",
                "favorites": "Favoriten",
                "recurring_transactions": "Wiederkehrende Transaktionen",
                "budget_warnings": "Budgetwarnungen",
                "undo_stack": "Undo-Einträge",
            }

            # Stats: Nur bekannte User-Tabellen zählen (Keys sind zur Compile-Zeit fix)
            # Existenz wird zur Laufzeit geprüft - keine externe Eingabe möglich
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            existing_tables = {row[0] for row in cursor.fetchall()}
            for table, label in count_tables.items():
                if table not in existing_tables:
                    stats[label] = 0
                    continue
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[label] = cursor.fetchone()[0]
                except sqlite3.OperationalError as e:
                    logger.debug("SELECT COUNT FROM %s: %s", table, e)
                    stats[label] = 0

            # Jahre mit Daten (Budget)
            try:
                cursor.execute("SELECT DISTINCT year FROM budget ORDER BY year")
                stats["years_budget"] = [int(y[0]) for y in cursor.fetchall()]
            except sqlite3.OperationalError:
                stats["years_budget"] = []
            stats["Jahre"] = ", ".join(str(y) for y in stats["years_budget"])

            # Jahre mit Daten (Tracking)
            try:
                cursor.execute(
                    "SELECT DISTINCT CAST(substr(date,1,4) AS INTEGER) AS y "
                    "FROM tracking ORDER BY y"
                )
                stats["years_tracking"] = [int(y[0]) for y in cursor.fetchall()]
            except sqlite3.OperationalError:
                stats["years_tracking"] = []

            self._close_if_own(conn)
            return stats

        except Exception as e:
            return {
                "Fehler": str(e),
                "tables": [],
                "years_budget": [],
                "years_tracking": [],
            }

    def export_to_sql(self, output_path: str) -> Tuple[bool, str]:
        """
        Exportiert Datenbank als SQL-Dump.

        Args:
            output_path: Ziel-Dateipfad

        Returns:
            (success, message)
        """
        try:
            conn = self._get_conn()

            with open(output_path, "w", encoding="utf-8") as f:
                for line in conn.iterdump():
                    f.write(f"{line}\n")

            self._close_if_own(conn)

            return True, f"Export erfolgreich: {output_path}"

        except Exception as e:
            return False, f"Fehler beim Export: {str(e)}"


if __name__ == "__main__":
    # Test
    model = DatabaseManagementModel("test_budget.db")

    logging.basicConfig(level=logging.DEBUG)
    logger.info("=== Database Statistics ===")
    for key, value in model.get_database_statistics().items():
        logger.info("%s: %s", key, value)

    logger.info("=== Available Backups ===")
    for backup in model.get_available_backups():
        logger.info(
            "%s - %s MB - %s", backup["filename"], backup["size_mb"], backup["created"]
        )
