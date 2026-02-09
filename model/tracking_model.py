from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta, datetime

# Undo/Redo (global)
from model.undo_redo_model import UndoRedoModel

@dataclass(frozen=True)
class TrackingRow:
    id: int
    d: date
    typ: str
    category: str
    amount: float
    details: str
    
    # Aliases für Kompatibilität mit verschiedenen Code-Teilen
    @property
    def date(self) -> date:
        """Alias für d - für Kompatibilität"""
        return self.d
    
    @property
    def description(self) -> str:
        """Alias für details - für Kompatibilität"""
        return self.details

def _to_date_iso(d: date | str) -> str:
    if isinstance(d, date):
        return d.isoformat()
    s = str(d).strip()
    # accept dd.mm.yyyy too
    if "." in s:
        try:
            dt = datetime.strptime(s, "%d.%m.%Y").date()
            return dt.isoformat()
        except Exception:
            pass
    # fallback assume already ISO
    return s

def _from_iso(s: str) -> date:
    return date.fromisoformat(s)

class TrackingModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.undo = UndoRedoModel(conn)

    def add(self, d: date | str, typ: str, category: str, amount: float, details: str = "") -> None:
        cur = self.conn.execute(
            "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
            (_to_date_iso(d), typ, category, float(amount), details or ""),
        )
        self.conn.commit()

        # Undo/Redo: INSERT
        try:
            rid = int(cur.lastrowid)
            row = self.conn.execute(
                "SELECT * FROM tracking WHERE id=?",
                (rid,),
            ).fetchone()
            if row:
                self.undo.record_operation("tracking", "INSERT", None, dict(row))
        except Exception:
            pass

        # Sparziel-Synchronisation: Bei Ersparnisse in verknüpfte Kategorie
        if typ == "Ersparnisse":
            self._sync_savings_goals_add(category, amount)

    def update(self, row_id: int, d: date | str, typ: str, category: str, amount: float, details: str = "") -> None:
        # Alte Werte abrufen für Undo/Redo + Sparziel-Korrektur
        old_full = self.conn.execute(
            "SELECT * FROM tracking WHERE id=?",
            (int(row_id),)
        ).fetchone()

        self.conn.execute(
            "UPDATE tracking SET date=?, typ=?, category=?, amount=?, details=? WHERE id=?",
            (_to_date_iso(d), typ, category, float(amount), details or "", int(row_id)),
        )
        self.conn.commit()

        # Undo/Redo: UPDATE
        try:
            new_full = self.conn.execute(
                "SELECT * FROM tracking WHERE id=?",
                (int(row_id),)
            ).fetchone()
            if old_full and new_full:
                self.undo.record_operation("tracking", "UPDATE", dict(old_full), dict(new_full))
        except Exception:
            pass

        # Sparziel-Synchronisation
        if old_full:
<<<<<<< Updated upstream
            old_typ = str(old_full["typ"]) if isinstance(old_full, sqlite3.Row) else old_full[0]
            old_cat = str(old_full["category"]) if isinstance(old_full, sqlite3.Row) else old_full[1]
            old_amt = float(old_full["amount"]) if isinstance(old_full, sqlite3.Row) else float(old_full[2])
=======
            # row_factory ist normalerweise sqlite3.Row. Falls nicht, ist die Spaltenreihenfolge:
            # (id, date, typ, category, amount, details)
            if isinstance(old_full, sqlite3.Row):
                old_typ = str(old_full["typ"])
                old_cat = str(old_full["category"])
                old_amt = float(old_full["amount"])
            else:
                old_typ = str(old_full[2])
                old_cat = str(old_full[3])
                old_amt = float(old_full[4])
>>>>>>> Stashed changes

            # Alte Buchung rückgängig machen
            if old_typ == "Ersparnisse":
                self._sync_savings_goals_remove(old_cat, old_amt)

            # Neue Buchung hinzufügen
            if typ == "Ersparnisse":
                self._sync_savings_goals_add(category, amount)

    def delete(self, row_id: int) -> None:
        # Alte Werte abrufen für Undo/Redo + Sparziel-Korrektur
        old_full = self.conn.execute(
            "SELECT * FROM tracking WHERE id=?",
            (int(row_id),)
        ).fetchone()

        self.conn.execute("DELETE FROM tracking WHERE id=?", (int(row_id),))
        self.conn.commit()

        # Undo/Redo: DELETE
        try:
            if old_full:
                self.undo.record_operation("tracking", "DELETE", dict(old_full), None)
        except Exception:
            pass

        # Sparziel-Synchronisation: Betrag abziehen
        if old_full:
<<<<<<< Updated upstream
            old_typ = str(old_full["typ"]) if isinstance(old_full, sqlite3.Row) else old_full[0]
            if old_typ == "Ersparnisse":
                old_cat = str(old_full["category"]) if isinstance(old_full, sqlite3.Row) else old_full[1]
                old_amt = float(old_full["amount"]) if isinstance(old_full, sqlite3.Row) else float(old_full[2])
=======
            # row_factory ist normalerweise sqlite3.Row. Falls nicht, ist die Spaltenreihenfolge:
            # (id, date, typ, category, amount, details)
            if isinstance(old_full, sqlite3.Row):
                old_typ = str(old_full["typ"])
            else:
                old_typ = str(old_full[2])
            if old_typ == "Ersparnisse":
                if isinstance(old_full, sqlite3.Row):
                    old_cat = str(old_full["category"])
                    old_amt = float(old_full["amount"])
                else:
                    old_cat = str(old_full[3])
                    old_amt = float(old_full[4])
>>>>>>> Stashed changes
                self._sync_savings_goals_remove(old_cat, old_amt)

    def exists_in_month(self, *, year: int, month: int, typ: str, category: str) -> bool:
        """True, wenn im gegebenen Monat bereits mindestens 1 Eintrag für typ+category existiert."""
        ym = f"{int(year):04d}-{int(month):02d}"
        row = self.conn.execute(
            "SELECT 1 FROM tracking WHERE typ=? AND category=? AND substr(date,1,7)=? LIMIT 1",
            (typ, category, ym),
        ).fetchone()
        return bool(row)

    def list_recent_sorted(self, days: int = 14) -> list[TrackingRow]:
        cutoff = (date.today() - timedelta(days=int(days))).isoformat()
        cur = self.conn.execute(
            "SELECT id, date, typ, category, amount, COALESCE(details,'') AS details "
            "FROM tracking WHERE date>=? ORDER BY date DESC, id DESC",
            (cutoff,),
        )
        out: list[TrackingRow] = []
        for r in cur.fetchall():
            out.append(
                TrackingRow(
                    int(r["id"]),
                    _from_iso(r["date"]),
                    str(r["typ"]),
                    str(r["category"]),
                    float(r["amount"]),
                    str(r["details"] or ""),
                )
            )
        return out

    def list_all_sorted(self) -> list[TrackingRow]:
        cur = self.conn.execute(
            "SELECT id, date, typ, category, amount, COALESCE(details,'') AS details "
            "FROM tracking ORDER BY date DESC, id DESC"
        )
        out: list[TrackingRow] = []
        for r in cur.fetchall():
            out.append(
                TrackingRow(
                    int(r["id"]),
                    _from_iso(r["date"]),
                    str(r["typ"]),
                    str(r["category"]),
                    float(r["amount"]),
                    str(r["details"] or ""),
                )
            )
        return out

    def list_filtered(
        self,
        typ: str | None = None,
        category: str | None = None,
        categories: list[str] | None = None,
        date_from: date | str | None = None,
        date_to: date | str | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        search_text: str | None = None,
        year: int | None = None,
    ) -> list[TrackingRow]:
        """
        Flexible Filtermethode für Tracking-Einträge.
        
        Args:
            typ: Filter nach Typ (Ausgaben/Einkommen/Ersparnisse)
            category: Filter nach Kategorie
            date_from: Von-Datum (inklusiv)
            date_to: Bis-Datum (inklusiv)
            min_amount: Minimalbetrag (absolut)
            max_amount: Maximalbetrag (absolut)
            search_text: Suche in Details und Kategorie
            year: Filter nach Jahr
        """
        where_parts = []
        params = []

        if typ:
            where_parts.append("typ = ?")
            params.append(typ)

        # Mehrfach-Kategorien-Filter (z. B. für Tags).
        if categories is not None and not category:
            categories = [str(c).strip() for c in categories if str(c).strip()]
            if not categories:
                return []

        if category:
            where_parts.append("category = ?")
            params.append(category)
        elif categories:
            placeholders = ','.join(['?'] * len(categories))
            where_parts.append(f"category IN ({placeholders})")
            params.extend(categories)

        if date_from:
            where_parts.append("date >= ?")
            params.append(_to_date_iso(date_from))

        if date_to:
            where_parts.append("date <= ?")
            params.append(_to_date_iso(date_to))

        if min_amount is not None:
            where_parts.append("ABS(amount) >= ?")
            params.append(float(min_amount))

        if max_amount is not None:
            where_parts.append("ABS(amount) <= ?")
            params.append(float(max_amount))

        if search_text:
            where_parts.append("(LOWER(details) LIKE ? OR LOWER(category) LIKE ?)")
            search_pattern = f"%{search_text.lower()}%"
            params.append(search_pattern)
            params.append(search_pattern)
        
        if year is not None:
            where_parts.append("substr(date,1,4) = ?")
            params.append(f"{int(year):04d}")

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"
        
        query = f"""
            SELECT id, date, typ, category, amount, COALESCE(details,'') AS details
            FROM tracking
            WHERE {where_clause}
            ORDER BY date DESC, id DESC
        """

        cur = self.conn.execute(query, tuple(params))
        out: list[TrackingRow] = []
        for r in cur.fetchall():
            out.append(
                TrackingRow(
                    int(r["id"]),
                    _from_iso(r["date"]),
                    str(r["typ"]),
                    str(r["category"]),
                    float(r["amount"]),
                    str(r["details"] or ""),
                )
            )
        return out


    def last_n_by_abs_amount(self, n: int = 5) -> list[TrackingRow]:
        cur = self.conn.execute(
            "SELECT id, date, typ, category, amount, COALESCE(details,'') AS details "
            "FROM tracking ORDER BY ABS(amount) DESC, date DESC, id DESC LIMIT ?",
            (int(n),),
        )
        out: list[TrackingRow] = []
        for r in cur.fetchall():
            out.append(
                TrackingRow(
                    int(r["id"]),
                    _from_iso(r["date"]),
                    str(r["typ"]),
                    str(r["category"]),
                    float(r["amount"]),
                    str(r["details"] or ""),
                )
            )
        return out

    def sum_by_typ(self, year: int | None = None, month: int | None = None) -> dict[str, float]:
        where = []
        args = []
        if year is not None:
            where.append("substr(date,1,4)=?")
            args.append(f"{int(year):04d}")
        if month is not None:
            where.append("substr(date,6,2)=?")
            args.append(f"{int(month):02d}")
        w = ("WHERE " + " AND ".join(where)) if where else ""
        cur = self.conn.execute(
            f"SELECT typ, SUM(amount) AS s FROM tracking {w} GROUP BY typ",
            tuple(args),
        )
        return {str(r["typ"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_category(self, typ: str, year: int | None = None, month: int | None = None) -> dict[str, float]:
        where = ["typ=?"]
        args = [typ]
        if year is not None:
            where.append("substr(date,1,4)=?")
            args.append(f"{int(year):04d}")
        if month is not None:
            where.append("substr(date,6,2)=?")
            args.append(f"{int(month):02d}")
        w = "WHERE " + " AND ".join(where)
        cur = self.conn.execute(
            f"SELECT category, SUM(amount) AS s FROM tracking {w} GROUP BY category ORDER BY ABS(s) DESC",
            tuple(args),
        )
        return {str(r["category"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_month(self, year: int, typ: str | None = None) -> dict[int, float]:
        where = ["substr(date,1,4)=?"]
        args = [f"{int(year):04d}"]
        if typ is not None:
            where.append("typ=?")
            args.append(typ)
        w = "WHERE " + " AND ".join(where)
        cur = self.conn.execute(
            f"SELECT CAST(substr(date,6,2) AS INTEGER) AS m, SUM(amount) AS s "
            f"FROM tracking {w} GROUP BY m ORDER BY m",
            tuple(args),
        )
        out = {int(r["m"]): float(r["s"] or 0.0) for r in cur.fetchall()}
        for m in range(1,13):
            out.setdefault(m, 0.0)
        return out


    def years(self) -> list[int]:
        cur = self.conn.execute(
            "SELECT DISTINCT CAST(substr(date,1,4) AS INTEGER) AS y FROM tracking ORDER BY y"
        )
        return [int(r["y"]) for r in cur.fetchall()]
    
    def get_available_years(self) -> list[int]:
        """Alias für years() - für Kompatibilität mit overview_tab"""
        return self.years()
    
    def get_entries_in_range(self, date_from: date, date_to: date) -> list[TrackingRow]:
        """
        Gibt alle Einträge in einem Datumsbereich zurück.
        
        Args:
            date_from: Start-Datum (inklusiv)
            date_to: End-Datum (inklusiv)
            
        Returns:
            Liste von TrackingRow Objekten
        """
        return self.list_filtered(date_from=date_from, date_to=date_to)

    def sum_by_month_all(self, typ: str | None = None) -> dict[int, float]:
        where = []
        args = []
        if typ is not None:
            where.append("typ=?")
            args.append(typ)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        cur = self.conn.execute(
            f"SELECT CAST(substr(date,6,2) AS INTEGER) AS m, SUM(amount) AS s FROM tracking {w} GROUP BY m ORDER BY m",
            tuple(args),
        )
        out = {int(r["m"]): float(r["s"] or 0.0) for r in cur.fetchall()}
        for m in range(1,13):
            out.setdefault(m, 0.0)
        return out

    def _sync_savings_goals_add(self, category: str, amount: float) -> None:
        """
        Fügt einen Betrag zu allen Sparzielen hinzu, die mit dieser Kategorie verknüpft sind.
        Wird automatisch bei Tracking-Buchung aufgerufen.
        """
        # Alle Sparziele finden, die mit dieser Kategorie verknüpft sind
        goals = self.conn.execute(
            "SELECT id, current_amount FROM savings_goals WHERE category = ?",
            (category,)
        ).fetchall()
        
        for goal in goals:
            goal_id, current = goal[0], float(goal[1])
            new_amount = current + amount
            self.conn.execute(
                "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
                (new_amount, goal_id)
            )
        
        if goals:
            self.conn.commit()
    
    def _sync_savings_goals_remove(self, category: str, amount: float) -> None:
        """
        Zieht einen Betrag von allen Sparzielen ab, die mit dieser Kategorie verknüpft sind.
        Wird automatisch beim Löschen/Ändern von Tracking-Buchungen aufgerufen.
        """
        # Alle Sparziele finden, die mit dieser Kategorie verknüpft sind
        goals = self.conn.execute(
            "SELECT id, current_amount FROM savings_goals WHERE category = ?",
            (category,)
        ).fetchall()
        
        for goal in goals:
            goal_id, current = goal[0], float(goal[1])
            new_amount = current - amount
            # Nicht unter 0 fallen
            new_amount = max(0, new_amount)
            self.conn.execute(
                "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
                (new_amount, goal_id)
            )
        
        if goals:
            self.conn.commit()

