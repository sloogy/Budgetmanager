from __future__ import annotations

import json
import logging
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from model.typ_constants import TYP_SAVINGS

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class UndoRow:
    id: int
    ts: str
    group_id: str
    table_name: str
    operation: str
    old_data: dict | None
    new_data: dict | None


class UndoRedoModel:
    """Technisch sauberes Undo/Redo für DB-Operationen.

    - Persistenter undo_stack + redo_stack (SQLite)
    - Gruppierung über group_id (z. B. Mass-Löschen, Rename-Cascade)
    - Unterstützt INSERT/UPDATE/DELETE + Spezialop "RENAME_CASCADE"

    WICHTIG:
    - Nur für Tabellen gedacht, die eine INTEGER PRIMARY KEY Spalte "id" haben

    Tabellennamen werden gegen eine Whitelist validiert (SQL-Injection-Schutz).
    """

    # Erlaubte Tabellennamen für dynamische SQL-Queries
    MAX_UNDO_ENTRIES = 100

    _ALLOWED_TABLES = frozenset(
        {
            "tracking",
            "budget",
            "categories",
            "tags",
            "category_tags",
            "entry_tags",
            "budget_warnings",
            "favorites",
            "savings_goals",
            "recurring_transactions",
            "suggestion_accepted",
            "tracking_learning_state",
            "fixcost_tracking",
            "system_flags",
            "undo_stack",
            "redo_stack",
        }
    )

    @classmethod
    def _safe_table(cls, table: str) -> str:
        """Validiert einen Tabellennamen gegen die Whitelist.
        Raises ValueError wenn der Name nicht erlaubt ist."""
        if table not in cls._ALLOWED_TABLES:
            raise ValueError(f"Ungültiger Tabellenname: {table!r}")
        return table

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._ensure_tables()

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------
    def new_group_id(self) -> str:
        return uuid4().hex

    def can_undo(self) -> bool:
        return bool(self.conn.execute("SELECT 1 FROM undo_stack LIMIT 1").fetchone())

    def can_redo(self) -> bool:
        return bool(self.conn.execute("SELECT 1 FROM redo_stack LIMIT 1").fetchone())

    def record_operation(
        self,
        table_name: str,
        operation: str,
        old_data: dict | None = None,
        new_data: dict | None = None,
        *,
        group_id: str | None = None,
        clear_redo: bool = True,
    ) -> None:
        """Speichert eine Operation im undo_stack.

        operation: INSERT | UPDATE | DELETE | RENAME_CASCADE
        """
        gid = group_id or self.new_group_id()
        ts = datetime.now().isoformat(sep=" ", timespec="seconds")

        if clear_redo:
            try:
                self.conn.execute("DELETE FROM redo_stack")
            except Exception as e:
                logger.debug("self.conn.execute('DELETE FROM redo_stack'): %s", e)

        # Dynamisch prüfen welche Spalten existieren und entsprechend einfügen
        cols = self._cols("undo_stack")

        # Basis-Werte
        values = []
        col_names = []

        # ts oder timestamp (oder beide)
        if "ts" in cols:
            col_names.append("ts")
            values.append(ts)
        if "timestamp" in cols:
            col_names.append("timestamp")
            values.append(ts)

        # group_id (optional in alten DBs)
        if "group_id" in cols:
            col_names.append("group_id")
            values.append(gid)

        # Pflichtfelder
        col_names.extend(["table_name", "operation", "old_data", "new_data"])
        values.extend(
            [
                str(table_name),
                str(operation),
                (
                    json.dumps(old_data, ensure_ascii=False)
                    if old_data is not None
                    else None
                ),
                (
                    json.dumps(new_data, ensure_ascii=False)
                    if new_data is not None
                    else None
                ),
            ]
        )

        placeholders = ",".join(["?"] * len(col_names))
        col_sql = ",".join(col_names)

        self.conn.execute(
            f"INSERT INTO undo_stack({col_sql}) VALUES({placeholders})",  # nosec B608
            values,
        )
        self.conn.commit()

        # Pruning: Älteste Einträge entfernen wenn Stack > MAX_UNDO_ENTRIES
        try:
            self.conn.execute(
                "DELETE FROM undo_stack WHERE group_id NOT IN ("
                "  SELECT DISTINCT group_id FROM undo_stack "
                "  ORDER BY id DESC LIMIT ?"
                ")",
                (self.MAX_UNDO_ENTRIES,),
            )
        except Exception as e:
            logger.debug("undo_stack pruning: %s", e)

    def undo(self) -> bool:
        """Undoes the last group. Returns True if something changed."""
        last_gid = self._last_group_id("undo_stack")
        if not last_gid:
            return False

        rows = self._read_group("undo_stack", last_gid, order="DESC")
        # Gesamte Gruppe transaktional: Schlägt eine Operation fehl, wird ALLES
        # zurückgerollt — vorher konnte ein Fehler mitten in der Gruppe einen
        # halben Undo hinterlassen (erste Operationen committet, Rest nicht,
        # Stack-Eintrag noch vorhanden).
        try:
            # inverse order for undo
            for r in rows:
                self._apply_inverse(r)
                self._push_to_other_stack("redo_stack", r)
            self.conn.execute("DELETE FROM undo_stack WHERE group_id=?", (last_gid,))
            self.conn.commit()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as re:
                logger.debug("Rollback nach Undo-Fehler fehlgeschlagen: %s", re)
            logger.warning(
                "Undo der Gruppe %s fehlgeschlagen — vollständig zurückgerollt: %s",
                last_gid,
                e,
            )
            return False

        self._post_recalc(rows, redo=False)
        return True

    def redo(self) -> bool:
        """Redoes the last undone group. Returns True if something changed."""
        last_gid = self._last_group_id("redo_stack")
        if not last_gid:
            return False

        rows = self._read_group("redo_stack", last_gid, order="ASC")
        # Gesamte Gruppe transaktional (siehe undo())
        try:
            for r in rows:
                self._apply_forward(r)
                self._push_to_other_stack("undo_stack", r, clear_redo=False)
            self.conn.execute("DELETE FROM redo_stack WHERE group_id=?", (last_gid,))
            self.conn.commit()
        except Exception as e:
            try:
                self.conn.rollback()
            except Exception as re:
                logger.debug("Rollback nach Redo-Fehler fehlgeschlagen: %s", re)
            logger.warning(
                "Redo der Gruppe %s fehlgeschlagen — vollständig zurückgerollt: %s",
                last_gid,
                e,
            )
            return False

        self._post_recalc(rows, redo=True)
        return True

    # ------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------
    def _ensure_tables(self) -> None:
        # undo_stack exists since v4, but we ensure columns for safety
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS undo_stack(
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
        self.conn.execute(
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

        # Sicherstellen dass alle Spalten existieren (für alte DBs)
        cols = self._cols("undo_stack")

        # group_id column for older dbs
        if "group_id" not in cols:
            try:
                self.conn.execute("ALTER TABLE undo_stack ADD COLUMN group_id TEXT")
            except sqlite3.OperationalError:
                logger.debug(
                    "ALTER TABLE undo_stack ADD COLUMN group_id: Spalte bereits vorhanden"
                )

        # ts column for older dbs (alte Version hatte 'timestamp')
        if "ts" not in cols:
            try:
                self.conn.execute("ALTER TABLE undo_stack ADD COLUMN ts TEXT")
                # Falls timestamp existiert, Daten kopieren
                if "timestamp" in cols:
                    self.conn.execute(
                        "UPDATE undo_stack SET ts = timestamp WHERE ts IS NULL"
                    )
            except sqlite3.OperationalError:
                logger.debug(
                    "ALTER TABLE undo_stack ADD COLUMN ts: Spalte bereits vorhanden"
                )

        self.conn.commit()

    def _cols(self, table: str) -> set[str]:
        try:
            safe = self._safe_table(table)
            cur = self.conn.execute(f"PRAGMA table_info({safe});")
            return {r[1] for r in cur.fetchall()}
        except Exception as e:
            logger.debug("_cols(%s): %s", table, e)
            return set()

    def _table_exists(self, table: str) -> bool:
        try:
            safe = self._safe_table(table)
            row = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (safe,),
            ).fetchone()
            return row is not None
        except Exception as e:
            logger.debug("_table_exists(%s): %s", table, e)
            return False

    def _last_group_id(self, table: str) -> str | None:
        safe = self._safe_table(table)
        row = self.conn.execute(
            f"SELECT group_id FROM {safe} ORDER BY id DESC LIMIT 1"  # nosec B608
        ).fetchone()
        if not row:
            return None
        gid = row[0] if isinstance(row, (tuple, list)) else row["group_id"]
        return str(gid) if gid else None

    def _read_group(self, table: str, group_id: str, *, order: str) -> list[UndoRow]:
        safe = self._safe_table(table)
        # order muss ASC oder DESC sein
        order = "ASC" if order.upper() == "ASC" else "DESC"
        # Dynamisch prüfen ob ts oder timestamp Spalte existiert
        cols = self._cols(safe)
        ts_col = "ts" if "ts" in cols else "timestamp" if "timestamp" in cols else "ts"

        cur = self.conn.execute(
            f"SELECT id, COALESCE({ts_col}, ''), COALESCE(group_id,''), table_name, operation, old_data, new_data "  # nosec B608
            f"FROM {safe} WHERE group_id=? ORDER BY id {order}",
            (group_id,),
        )
        out: list[UndoRow] = []
        for r in cur.fetchall():
            old_data = json.loads(r[5]) if r[5] else None
            new_data = json.loads(r[6]) if r[6] else None
            out.append(
                UndoRow(
                    id=int(r[0]),
                    ts=str(r[1] or ""),
                    group_id=str(r[2] or ""),
                    table_name=str(r[3]),
                    operation=str(r[4]),
                    old_data=old_data,
                    new_data=new_data,
                )
            )
        return out

    def _push_to_other_stack(
        self, target_table: str, r: UndoRow, *, clear_redo: bool = False
    ) -> None:
        # v2.2.25 (d1-Härtung): Ziel-Stack strikt gegen die Whitelist –
        # target_table erreicht weiter unten ein f-String-INSERT.
        target_table = self._safe_table(target_table)
        # for redo→undo we must not clear redo stack
        ts = datetime.now().isoformat(sep=" ", timespec="seconds")
        if clear_redo:
            try:
                self.conn.execute("DELETE FROM redo_stack")
            except Exception as e:
                logger.debug("self.conn.execute('DELETE FROM redo_stack'): %s", e)

        # Dynamisch prüfen welche Spalten existieren
        cols = self._cols(target_table)

        values = []
        col_names = []

        if "ts" in cols:
            col_names.append("ts")
            values.append(ts)
        if "timestamp" in cols:
            col_names.append("timestamp")
            values.append(ts)
        if "group_id" in cols:
            col_names.append("group_id")
            values.append(r.group_id)

        col_names.extend(["table_name", "operation", "old_data", "new_data"])
        values.extend(
            [
                r.table_name,
                r.operation,
                (
                    json.dumps(r.old_data, ensure_ascii=False)
                    if r.old_data is not None
                    else None
                ),
                (
                    json.dumps(r.new_data, ensure_ascii=False)
                    if r.new_data is not None
                    else None
                ),
            ]
        )

        placeholders = ",".join(["?"] * len(col_names))
        col_sql = ",".join(col_names)

        self.conn.execute(
            f"INSERT INTO {target_table}({col_sql}) VALUES({placeholders})",  # nosec B608
            values,
        )

    def _apply_inverse(self, r: UndoRow) -> None:
        op = r.operation.upper()
        if op == "INSERT":
            # undo insert => delete new row
            if r.new_data:
                self._delete_by_id(r.table_name, r.new_data)
        elif op == "DELETE":
            # undo delete => insert old row
            if r.old_data:
                self._insert_row(r.table_name, r.old_data)
                self._restore_tracking_tags(r.table_name, r.old_data)
        elif op == "UPDATE":
            # undo update => restore old row
            if r.old_data:
                self._update_by_id(r.table_name, r.old_data)
                self._restore_tracking_tags(r.table_name, r.old_data)
        elif op == "RENAME_CASCADE":
            if r.old_data and r.new_data:
                # inverse => rename new_name back to old_name
                self._rename_cascade(
                    cat_id=int(r.old_data.get("cat_id")),
                    typ=str(r.old_data.get("typ")),
                    old_name=str(r.new_data.get("new_name")),
                    new_name=str(r.old_data.get("old_name")),
                )
        else:
            # unknown => ignore (safe)
            return

    def _apply_forward(self, r: UndoRow) -> None:
        op = r.operation.upper()
        if op == "INSERT":
            if r.new_data:
                self._insert_row(r.table_name, r.new_data)
                self._restore_tracking_tags(r.table_name, r.new_data)
        elif op == "DELETE":
            if r.old_data:
                self._delete_by_id(r.table_name, r.old_data)
        elif op == "UPDATE":
            if r.new_data:
                self._update_by_id(r.table_name, r.new_data)
                self._restore_tracking_tags(r.table_name, r.new_data)
        elif op == "RENAME_CASCADE":
            if r.old_data and r.new_data:
                self._rename_cascade(
                    cat_id=int(r.old_data.get("cat_id")),
                    typ=str(r.old_data.get("typ")),
                    old_name=str(r.old_data.get("old_name")),
                    new_name=str(r.new_data.get("new_name")),
                )
        else:
            return

    def _restore_tracking_tags(self, table: str, data: dict[str, Any]) -> None:
        """Stellt die Tag-Belegung einer Tracking-Zeile atomar wieder her.

        ``_tag_ids`` ist Undo-Metadateninhalt und keine DB-Spalte. Fehlende
        Tags werden übersprungen, damit ein später separat gelöschter Tag ein
        ansonsten gültiges Undo nicht blockiert.
        """
        if table != "tracking" or "id" not in data or "_tag_ids" not in data:
            return
        if not self._table_exists("entry_tags") or not self._table_exists("tags"):
            return
        entry_id = int(data["id"])
        self.conn.execute("DELETE FROM entry_tags WHERE entry_id=?", (entry_id,))
        raw_ids = data.get("_tag_ids") or []
        for raw_tag_id in raw_ids:
            try:
                tag_id = int(raw_tag_id)
            except (TypeError, ValueError):
                continue
            self.conn.execute(
                """
                INSERT OR IGNORE INTO entry_tags(entry_id, tag_id)
                SELECT ?, id FROM tags WHERE id=?
                """,
                (entry_id, tag_id),
            )

    def _delete_by_id(self, table: str, data: dict[str, Any]) -> None:
        if "id" not in data:
            return
        safe = self._safe_table(table)
        # v2.2.25 (KILLCRITIC k2): Symmetrie zu _restore_tracking_tags –
        # der Redo-/Undo-Loeschpfad muss die Tag-Zuordnungen einer Buchung
        # explizit mitentfernen. Das Schema traegt zwar ON DELETE CASCADE,
        # SQLite erzwingt Fremdschluessel aber nur bei aktivem
        # PRAGMA foreign_keys, das die App-Verbindung nicht setzt; ohne
        # diesen Schritt blieben verwaiste entry_tags-Zeilen zurueck.
        if safe == "tracking":
            self.conn.execute(
                "DELETE FROM entry_tags WHERE entry_id=?", (int(data["id"]),)
            )
        # Kein commit() hier — Transaktionsklammer liegt in undo()/redo()
        self.conn.execute(
            f"DELETE FROM {safe} WHERE id=?",  # nosec B608
            (int(data["id"]),),
        )

    def _insert_row(self, table: str, data: dict[str, Any]) -> None:
        safe = self._safe_table(table)
        cols = self._cols(safe)
        insert_cols = [
            k for k in data if k in cols and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
        ]
        if not insert_cols:
            return
        placeholders = ",".join(["?"] * len(insert_cols))
        col_sql = ",".join(insert_cols)
        values = [data[k] for k in insert_cols]
        self.conn.execute(
            f"INSERT OR REPLACE INTO {safe}({col_sql}) VALUES({placeholders})",
            values,
        )

    def _update_by_id(self, table: str, data: dict[str, Any]) -> None:
        safe = self._safe_table(table)
        cols = self._cols(safe)
        if "id" not in data or "id" not in cols:
            return
        set_cols = [
            k
            for k in data
            if k in cols and k != "id" and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", k)
        ]
        if not set_cols:
            return
        set_sql = ", ".join([f"{k}=?" for k in set_cols])
        values = [data[k] for k in set_cols] + [int(data["id"])]
        self.conn.execute(
            f"UPDATE {safe} SET {set_sql} WHERE id=?",  # nosec B608
            values,
        )

    def _rename_cascade(
        self, *, cat_id: int, typ: str, old_name: str, new_name: str
    ) -> None:
        """Undo/Redo-Helfer für Kategorie-Rename.

        Muss dieselben Text-Referenzen anfassen wie
        ``CategoryModel.rename_and_cascade``. Sonst wäre der eigentliche Rename
        sauber, aber Undo/Redo würde Favoriten, Warnungen oder wiederkehrende
        Buchungen wieder inkonsistent machen. Kein commit() hier: undo()/redo()
        committen die gesamte Gruppe atomar.
        """
        if self._table_exists("categories"):
            self.conn.execute(
                "UPDATE categories SET name=? WHERE id=?", (new_name, int(cat_id))
            )

        if self._table_exists("budget"):
            self.conn.execute(
                "UPDATE budget SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
        if self._table_exists("tracking"):
            self.conn.execute(
                "UPDATE tracking SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
        if self._table_exists("favorites"):
            self.conn.execute(
                "UPDATE OR IGNORE favorites SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM favorites WHERE typ=? AND category=?", (typ, old_name)
            )
        if self._table_exists("budget_warnings"):
            self.conn.execute(
                "UPDATE OR IGNORE budget_warnings SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM budget_warnings WHERE typ=? AND category=?",
                (typ, old_name),
            )
        if self._table_exists("recurring_transactions"):
            self.conn.execute(
                "UPDATE recurring_transactions SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
        if self._table_exists("suggestion_accepted"):
            self.conn.execute(
                "UPDATE OR IGNORE suggestion_accepted SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM suggestion_accepted WHERE typ=? AND category=?",
                (typ, old_name),
            )
        # v2.2.6 (KILLCRITIC): Muss denselben Lernzustand-Umzug spiegeln wie
        # CategoryModel.rename_and_cascade. Sonst würde Undo/Redo eines Renames
        # den Lernzustand inkonsistent zum Rest der umbenannten Referenzen lassen.
        if self._table_exists("tracking_learning_state"):
            self.conn.execute(
                "UPDATE OR IGNORE tracking_learning_state SET category=? WHERE typ=? AND category=?",
                (new_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM tracking_learning_state WHERE typ=? AND category=?",
                (typ, old_name),
            )
        if typ == TYP_SAVINGS and self._table_exists("savings_goals"):
            self.conn.execute(
                "UPDATE savings_goals SET category=? WHERE category=?",
                (new_name, old_name),
            )

    def _post_recalc(self, rows: list[UndoRow], *, redo: bool = False) -> None:
        """Spiegelt Undo/Redo in Sparziel-Bestand und Flusswerten.

        ``factor=+1`` bedeutet: Buchung wird zum Datenbestand hinzugefügt.
        ``factor=-1`` bedeutet: Buchung wird entfernt. Dadurch bleiben auch
        Bezug und Korrektur nach Undo/Redo getrennt ausgewiesen.
        """

        def apply(data: dict | None, factor: float) -> None:
            if not data or data.get("typ") != TYP_SAVINGS:
                return
            category = data.get("category")
            amount = float(data.get("amount", 0) or 0)
            if not category or abs(amount) < 1e-12:
                return
            raw_action = str(data.get("savings_action") or "").strip().lower()
            action = raw_action or ("withdrawal" if amount < 0 else "deposit")
            self._adjust_savings_goal_flow(
                str(category), amount=amount, action=action, factor=factor
            )

        for row in rows:
            if row.table_name != "tracking":
                continue
            try:
                operation = row.operation.upper()
                if operation == "INSERT":
                    apply(row.new_data, 1.0 if redo else -1.0)
                elif operation == "DELETE":
                    apply(row.old_data, -1.0 if redo else 1.0)
                elif operation == "UPDATE":
                    if redo:
                        apply(row.old_data, -1.0)
                        apply(row.new_data, 1.0)
                    else:
                        apply(row.new_data, -1.0)
                        apply(row.old_data, 1.0)
            except Exception as exc:
                logger.error("Fehler bei Sparziel-Korrektur: %s", exc)

    def _adjust_savings_goal_flow(
        self, category: str, *, amount: float, action: str, factor: float
    ) -> None:
        """Passt Bestand, Einzahlungen und Bezüge symmetrisch an."""
        try:
            cols = {
                str(row[1])
                for row in self.conn.execute("PRAGMA table_info(savings_goals)")
            }
            flow_cols = {"contributed_amount", "withdrawn_amount"}.issubset(cols)
            stock_delta = factor * float(amount)
            contribution_delta = 0.0
            withdrawal_delta = 0.0
            if action == "withdrawal":
                withdrawal_delta = factor * abs(float(amount))
            else:
                contribution_delta = factor * float(amount)

            goals = self.conn.execute(
                """
                SELECT id, current_amount
                FROM savings_goals
                WHERE category=? AND status IN ('sparend','freigegeben')
                """,
                (category,),
            ).fetchall()
            for goal in goals:
                goal_id = int(goal[0])
                if flow_cols:
                    self.conn.execute(
                        """
                        UPDATE savings_goals
                        SET current_amount=MAX(0,current_amount+?),
                            contributed_amount=MAX(0,contributed_amount+?),
                            withdrawn_amount=MAX(0,withdrawn_amount+?)
                        WHERE id=?
                        """,
                        (stock_delta, contribution_delta, withdrawal_delta, goal_id),
                    )
                else:
                    self.conn.execute(
                        "UPDATE savings_goals SET current_amount=MAX(0,current_amount+?) WHERE id=?",
                        (stock_delta, goal_id),
                    )
            if goals:
                self.conn.commit()
        except Exception as exc:
            logger.warning(
                "Fehler beim Anpassen des Sparziels für '%s': %s", category, exc
            )

    def _adjust_savings_goal(self, category: str, amount_change: float) -> None:
        """Legacy-Helfer: behandelt den Betrag als Einzahlung/Korrektur."""
        self._adjust_savings_goal_flow(
            category, amount=amount_change, action="correction", factor=1.0
        )
