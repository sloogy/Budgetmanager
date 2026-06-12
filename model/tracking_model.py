from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta, datetime

"""Tracking-Datenmodell.

Verwaltet Buchungseinträge (Ist-Werte) mit Datum, Typ, Kategorie, Betrag
und Bemerkung. Unterstützt Filter, Suche und Duplikaterkennung.
"""

# Undo/Redo (global)
from model.undo_redo_model import UndoRedoModel
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, normalize_typ, is_income, rest_sign, ALL_TYPEN
from model.database import db_transaction

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
        except Exception as e:
            logger.debug("dt = datetime.strptime(s, '%d.%m.%Y').date(): %s", e)
    # fallback assume already ISO
    return s

def _from_iso(s: str) -> date:
    return date.fromisoformat(s)

class TrackingModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.undo = UndoRedoModel(conn)

    def add(self, d: date | str, typ: str, category: str, amount: float, details: str = "") -> None:
        # Atomare Transaktion: INSERT + Sparziel-Sync
        with db_transaction(self.conn):
            cur = self.conn.execute(
                "INSERT INTO tracking(date, typ, category, amount, details) VALUES(?,?,?,?,?)",
                (_to_date_iso(d), typ, category, float(amount), details or ""),
            )
            rid = int(cur.lastrowid)
            # Sparziel-Synchronisation innerhalb der Transaktion
            if typ == TYP_SAVINGS:
                self._sync_savings(category, amount, add=True)

        # Undo/Redo: nach Commit (Metadaten, nicht geschäftskritisch)
        try:
            row = self.conn.execute(
                "SELECT * FROM tracking WHERE id=?", (rid,),
            ).fetchone()
            if row:
                self.undo.record_operation("tracking", "INSERT", None, dict(row))
        except Exception as e:
            logger.warning("Undo-Recording fehlgeschlagen nach INSERT (id=%s): %s", rid, e)

    def update(self, row_id: int, d: date | str, typ: str, category: str, amount: float, details: str = "") -> None:
        # Alte Werte für Undo + Sparziel-Korrektur LESEN (vor Transaktion)
        old_full = self.conn.execute(
            "SELECT * FROM tracking WHERE id=?", (int(row_id),)
        ).fetchone()

        # Atomare Transaktion: UPDATE + Sparziel-Korrekturen
        with db_transaction(self.conn):
            self.conn.execute(
                "UPDATE tracking SET date=?, typ=?, category=?, amount=?, details=? WHERE id=?",
                (_to_date_iso(d), typ, category, float(amount), details or "", int(row_id)),
            )

            # Sparziel-Synchronisation
            if old_full:
                if isinstance(old_full, sqlite3.Row):
                    old_typ, old_cat, old_amt = str(old_full["typ"]), str(old_full["category"]), float(old_full["amount"])
                else:
                    old_typ, old_cat, old_amt = str(old_full[2]), str(old_full[3]), float(old_full[4])

                if old_typ == TYP_SAVINGS:
                    self._sync_savings(old_cat, old_amt, add=False)
                if typ == TYP_SAVINGS:
                    self._sync_savings(category, amount, add=True)

        # Undo/Redo: nach Commit
        try:
            new_full = self.conn.execute(
                "SELECT * FROM tracking WHERE id=?", (int(row_id),)
            ).fetchone()
            if old_full and new_full:
                self.undo.record_operation("tracking", "UPDATE", dict(old_full), dict(new_full))
        except Exception as e:
            logger.warning("Undo-Recording fehlgeschlagen nach UPDATE (id=%s): %s", row_id, e)

    def delete(self, row_id: int) -> None:
        # Alte Werte lesen (vor Transaktion)
        old_full = self.conn.execute(
            "SELECT * FROM tracking WHERE id=?", (int(row_id),)
        ).fetchone()

        # Atomare Transaktion: DELETE + Sparziel-Korrektur
        with db_transaction(self.conn):
            self.conn.execute("DELETE FROM tracking WHERE id=?", (int(row_id),))

            if old_full:
                if isinstance(old_full, sqlite3.Row):
                    old_typ, old_cat, old_amt = str(old_full["typ"]), str(old_full["category"]), float(old_full["amount"])
                else:
                    old_typ, old_cat, old_amt = str(old_full[2]), str(old_full[3]), float(old_full[4])
                if old_typ == TYP_SAVINGS:
                    self._sync_savings(old_cat, old_amt, add=False)

        # Undo/Redo: nach Commit
        try:
            if old_full:
                self.undo.record_operation("tracking", "DELETE", dict(old_full), None)
        except Exception as e:
            logger.warning("Undo-Recording fehlgeschlagen nach DELETE (id=%s): %s", row_id, e)

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
        tag_id: int | None = None,
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
            tag_id: Filter nach Tag (entry_tags JOIN)
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

        # Tag-Filter: über Subquery auf entry_tags
        if tag_id is not None:
            where_parts.append("id IN (SELECT entry_id FROM entry_tags WHERE tag_id = ?)")
            params.append(int(tag_id))

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

    def category_usage_counts(self, typ: str | None = None) -> dict[str, int]:
        """Zählt wie oft jede Kategorie gebucht wurde.

        Args:
            typ: Optional – nur Buchungen dieses Typs zählen.

        Returns:
            Dict {Kategoriename: Anzahl}, absteigend nach Häufigkeit.
        """
        if typ:
            cur = self.conn.execute(
                "SELECT category, COUNT(*) AS cnt FROM tracking "
                "WHERE typ = ? GROUP BY category ORDER BY cnt DESC",
                (typ,),
            )
        else:
            cur = self.conn.execute(
                "SELECT category, COUNT(*) AS cnt FROM tracking "
                "GROUP BY category ORDER BY cnt DESC"
            )
        return {str(r[0]): int(r[1]) for r in cur.fetchall()}


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

    def get_month_total(self, year: int, month: int, typ: str, category: str) -> float:
        """Gibt die Summe aller Buchungen für eine Kategorie in einem Monat zurück."""
        start_date = f"{year:04d}-{month:02d}-01"
        if month == 12:
            end_date = f"{year + 1:04d}-01-01"
        else:
            end_date = f"{year:04d}-{month + 1:02d}-01"
        cur = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM tracking "
            "WHERE date >= ? AND date < ? AND typ = ? AND category = ?",
            (start_date, end_date, typ, category)
        )
        row = cur.fetchone()
        return float(row["total"] if row else 0.0)

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

    def _sync_savings(self, category: str, amount: float, *, add: bool) -> None:
        """Synchronisiert Sparziele innerhalb einer laufenden Transaktion.

        Args:
            category: Kategorie-Name
            amount:   Betrag
            add:      True = addieren, False = subtrahieren
        """
        goals = self.conn.execute(
            "SELECT id, current_amount FROM savings_goals WHERE category = ?",
            (category,),
        ).fetchall()

        for goal in goals:
            goal_id, current = goal[0], float(goal[1])
            if add:
                new_amount = current + amount
            else:
                # Kein max(0) – negative Stände sind gültig (Entnahme / Undo).
                # max(0) würde Korrekturbuchungen und Undo-Operationen still verfälschen.
                new_amount = current - amount
            self.conn.execute(
                "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
                (new_amount, goal_id),
            )
        # KEIN commit() – wird von db_transaction erledigt

    def check_savings_goal_conflict(self, category: str, amount: float) -> dict | None:
        """Prüft ob eine negative Buchung auf eine Spar-Kategorie mit aktivem Sparziel kollidiert.

        Wird VOR der Buchung von der UI aufgerufen, damit ein Dialog angezeigt werden kann.

        Args:
            category: Kategorie-Name
            amount:   Betrag (negativ = Entnahme)

        Returns:
            None wenn kein Konflikt, sonst dict mit:
            {
                'goal_id': int,
                'goal_name': str,
                'goal_status': str,     # 'sparend' | 'freigegeben'
                'current_amount': float,
                'target_amount': float,
            }
        """
        if amount >= 0:
            return None

        row = self.conn.execute(
            """
            SELECT id, name, status, current_amount, target_amount
            FROM savings_goals
            WHERE category = ? AND status IN ('sparend', 'freigegeben')
            LIMIT 1
            """,
            (category,),
        ).fetchone()

        if not row:
            return None

        return {
            'goal_id': row[0],
            'goal_name': row[1],
            'goal_status': row[2],
            'current_amount': float(row[3]),
            'target_amount': float(row[4]),
        }

    # Legacy-Aliases – VERALTET, nicht innerhalb db_transaction verwenden!
    # Diese Methoden enthalten conn.commit() und brechen verschachtelte Transaktionen.
    def _sync_savings_goals_add(self, category: str, amount: float) -> None:
        """VERALTET: Nutze stattdessen _sync_savings(category, amount, add=True) innerhalb db_transaction."""
        self._sync_savings(category, amount, add=True)
        self.conn.commit()

    def _sync_savings_goals_remove(self, category: str, amount: float) -> None:
        """VERALTET: Nutze stattdessen _sync_savings(category, amount, add=False) innerhalb db_transaction."""
        self._sync_savings(category, amount, add=False)
        self.conn.commit()


    def count(self) -> int:
        """Anzahl der Tracking-Buchungen."""
        row = self.conn.execute("SELECT COUNT(*) FROM tracking").fetchone()
        return int(row[0]) if row else 0
