from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4


@dataclass(frozen=True)
class UndoRow:
    id: int
    ts: str
    group_id: str
    table_name: str
    operation: str
    old_data: Optional[dict]
    new_data: Optional[dict]


class UndoRedoModel:
    """Technisch sauberes Undo/Redo für DB-Operationen.

    - Persistenter undo_stack + redo_stack (SQLite)
    - Gruppierung über group_id (z. B. Mass-Löschen, Rename-Cascade)
    - Unterstützt INSERT/UPDATE/DELETE + Spezialop "RENAME_CASCADE"

    WICHTIG:
    - Nur für Tabellen gedacht, die eine INTEGER PRIMARY KEY Spalte "id" haben
      (categories, tracking, budget, ...). Spezialfälle können via Custom-Op.
    """

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
        old_data: Optional[dict] = None,
        new_data: Optional[dict] = None,
        *,
        group_id: Optional[str] = None,
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
            except Exception:
                pass

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
        values.extend([
            str(table_name),
            str(operation),
            json.dumps(old_data, ensure_ascii=False) if old_data is not None else None,
            json.dumps(new_data, ensure_ascii=False) if new_data is not None else None,
        ])
        
        placeholders = ",".join(["?"] * len(col_names))
        col_sql = ",".join(col_names)
        
        self.conn.execute(
            f"INSERT INTO undo_stack({col_sql}) VALUES({placeholders})",
            values,
        )
        self.conn.commit()

    def undo(self) -> bool:
        """Undoes the last group. Returns True if something changed."""
        last_gid = self._last_group_id("undo_stack")
        if not last_gid:
            return False

        rows = self._read_group("undo_stack", last_gid, order="DESC")
        # inverse order for undo
        for r in rows:
            self._apply_inverse(r)
            self._push_to_other_stack("redo_stack", r)

        self.conn.execute("DELETE FROM undo_stack WHERE group_id=?", (last_gid,))
        self.conn.commit()

        self._post_recalc(rows)
        return True

    def redo(self) -> bool:
        """Redoes the last undone group. Returns True if something changed."""
        last_gid = self._last_group_id("redo_stack")
        if not last_gid:
            return False

        rows = self._read_group("redo_stack", last_gid, order="ASC")
        for r in rows:
            self._apply_forward(r)
            self._push_to_other_stack("undo_stack", r, clear_redo=False)

        self.conn.execute("DELETE FROM redo_stack WHERE group_id=?", (last_gid,))
        self.conn.commit()

        self._post_recalc(rows)
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
                pass
        
        # ts column for older dbs (alte Version hatte 'timestamp')
        if "ts" not in cols:
            try:
                self.conn.execute("ALTER TABLE undo_stack ADD COLUMN ts TEXT")
                # Falls timestamp existiert, Daten kopieren
                if "timestamp" in cols:
                    self.conn.execute("UPDATE undo_stack SET ts = timestamp WHERE ts IS NULL")
            except sqlite3.OperationalError:
                pass

        self.conn.commit()

    def _cols(self, table: str) -> set[str]:
        try:
            cur = self.conn.execute(f"PRAGMA table_info({table});")
            return {r[1] for r in cur.fetchall()}
        except Exception:
            return set()

    def _last_group_id(self, table: str) -> Optional[str]:
        row = self.conn.execute(
            f"SELECT group_id FROM {table} ORDER BY id DESC LIMIT 1"
        ).fetchone()
        if not row:
            return None
        gid = row[0] if isinstance(row, (tuple, list)) else row["group_id"]
        return str(gid) if gid else None

    def _read_group(self, table: str, group_id: str, *, order: str) -> list[UndoRow]:
        # Dynamisch prüfen ob ts oder timestamp Spalte existiert
        cols = self._cols(table)
        ts_col = "ts" if "ts" in cols else "timestamp" if "timestamp" in cols else "ts"
        
        cur = self.conn.execute(
            f"SELECT id, COALESCE({ts_col}, ''), COALESCE(group_id,''), table_name, operation, old_data, new_data "
            f"FROM {table} WHERE group_id=? ORDER BY id {order}",
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

    def _push_to_other_stack(self, target_table: str, r: UndoRow, *, clear_redo: bool = False) -> None:
        # for redo→undo we must not clear redo stack
        ts = datetime.now().isoformat(sep=" ", timespec="seconds")
        if clear_redo:
            try:
                self.conn.execute("DELETE FROM redo_stack")
            except Exception:
                pass

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
        values.extend([
            r.table_name,
            r.operation,
            json.dumps(r.old_data, ensure_ascii=False) if r.old_data is not None else None,
            json.dumps(r.new_data, ensure_ascii=False) if r.new_data is not None else None,
        ])
        
        placeholders = ",".join(["?"] * len(col_names))
        col_sql = ",".join(col_names)
        
        self.conn.execute(
            f"INSERT INTO {target_table}({col_sql}) VALUES({placeholders})",
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
        elif op == "UPDATE":
            # undo update => restore old row
            if r.old_data:
                self._update_by_id(r.table_name, r.old_data)
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
        elif op == "DELETE":
            if r.old_data:
                self._delete_by_id(r.table_name, r.old_data)
        elif op == "UPDATE":
            if r.new_data:
                self._update_by_id(r.table_name, r.new_data)
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

    def _delete_by_id(self, table: str, data: dict[str, Any]) -> None:
        if "id" not in data:
            return
        self.conn.execute(f"DELETE FROM {table} WHERE id=?", (int(data["id"]),))
        self.conn.commit()

    def _insert_row(self, table: str, data: dict[str, Any]) -> None:
        cols = self._cols(table)
        insert_cols = [k for k in data.keys() if k in cols]
        if not insert_cols:
            return
        placeholders = ",".join(["?"] * len(insert_cols))
        col_sql = ",".join(insert_cols)
        values = [data[k] for k in insert_cols]
        self.conn.execute(
            f"INSERT OR REPLACE INTO {table}({col_sql}) VALUES({placeholders})",
            values,
        )
        self.conn.commit()

    def _update_by_id(self, table: str, data: dict[str, Any]) -> None:
        cols = self._cols(table)
        if "id" not in data or "id" not in cols:
            return
        set_cols = [k for k in data.keys() if k in cols and k != "id"]
        if not set_cols:
            return
        set_sql = ", ".join([f"{k}=?" for k in set_cols])
        values = [data[k] for k in set_cols] + [int(data["id"])]
        self.conn.execute(f"UPDATE {table} SET {set_sql} WHERE id=?", values)
        self.conn.commit()

    def _rename_cascade(self, *, cat_id: int, typ: str, old_name: str, new_name: str) -> None:
        self.conn.execute("UPDATE categories SET name=? WHERE id=?", (new_name, int(cat_id)))
        # Cascade (budget/tracking referenzieren Kategorie per Text)
        self.conn.execute(
            "UPDATE budget SET category=? WHERE typ=? AND category=?",
            (new_name, typ, old_name),
        )
        self.conn.execute(
            "UPDATE tracking SET category=? WHERE typ=? AND category=?",
            (new_name, typ, old_name),
        )
        self.conn.commit()

    def _post_recalc(self, rows: list[UndoRow]) -> None:
        """Nach Undo/Redo abhängige Daten korrigieren (Sparziele).
        
        WICHTIG: Wir berechnen NICHT pauschal neu, da das manuell eingetragene
        Sparziel-Beträge überschreiben würde. Stattdessen passen wir den Betrag
        entsprechend der rückgängig gemachten/wiederholten Operation an.
        """
        for r in rows:
            if r.table_name != "tracking":
                continue
                
            try:
                # Prüfe ob es eine Ersparnisse-Buchung ist
                old_typ = r.old_data.get("typ") if r.old_data else None
                new_typ = r.new_data.get("typ") if r.new_data else None
                
                # Bei Undo einer INSERT: Die Buchung wurde gelöscht
                # → Betrag vom Sparziel abziehen
                if r.operation.upper() == "INSERT" and new_typ == "Ersparnisse":
                    category = r.new_data.get("category")
                    amount = float(r.new_data.get("amount", 0))
                    if category and amount:
                        self._adjust_savings_goal(category, -amount)
                
                # Bei Undo einer DELETE: Die Buchung wurde wiederhergestellt
                # → Betrag zum Sparziel addieren
                elif r.operation.upper() == "DELETE" and old_typ == "Ersparnisse":
                    category = r.old_data.get("category")
                    amount = float(r.old_data.get("amount", 0))
                    if category and amount:
                        self._adjust_savings_goal(category, amount)
                
                # Bei Undo einer UPDATE: alte Werte wiederherstellen
                elif r.operation.upper() == "UPDATE":
                    # Alte Ersparnisse-Buchung wiederherstellen
                    if old_typ == "Ersparnisse":
                        old_cat = r.old_data.get("category")
                        old_amt = float(r.old_data.get("amount", 0))
                        if old_cat and old_amt:
                            self._adjust_savings_goal(old_cat, old_amt)
                    # Neue Ersparnisse-Buchung rückgängig machen
                    if new_typ == "Ersparnisse":
                        new_cat = r.new_data.get("category")
                        new_amt = float(r.new_data.get("amount", 0))
                        if new_cat and new_amt:
                            self._adjust_savings_goal(new_cat, -new_amt)
                            
            except Exception as e:
                print(f"Fehler bei Sparziel-Korrektur: {e}")
                pass
    
    def _adjust_savings_goal(self, category: str, amount_change: float) -> None:
        """Passt den Betrag eines Sparziels um einen Wert an."""
        try:
            goals = self.conn.execute(
                "SELECT id, current_amount FROM savings_goals WHERE category = ?",
                (category,)
            ).fetchall()
            
            for goal in goals:
                goal_id, current = goal[0], float(goal[1])
                new_amount = max(0, current + amount_change)  # Nicht unter 0
                self.conn.execute(
                    "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
                    (new_amount, goal_id)
                )
            
            if goals:
                self.conn.commit()
        except Exception:
            pass
