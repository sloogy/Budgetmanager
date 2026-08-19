from __future__ import annotations
import logging

logger = logging.getLogger(__name__)
import re
import sqlite3
from dataclasses import dataclass
from datetime import date, timedelta, datetime

"""Tracking-Datenmodell.

Verwaltet Buchungseinträge (Ist-Werte) mit Datum, Typ, Kategorie, Betrag
und Bemerkung. Unterstützt Filter, Suche und Duplikaterkennung.
"""

# Undo/Redo (global)
from model.undo_redo_model import UndoRedoModel
from model.typ_constants import (
    TYP_INCOME,
    TYP_EXPENSES,
    TYP_SAVINGS,
    normalize_typ,
    is_income,
    rest_sign,
    ALL_TYPEN,
)
from model.database import db_transaction
from model.date_ranges import month_bounds, year_bounds
from model.savings_goals_model import (
    SavingsGoalBoundsError,
    ACTION_CORRECTION,
    ACTION_DEPOSIT,
    ACTION_WITHDRAWAL,
    STATUS_RELEASED,
    STATUS_SAVING,
    VALID_SAVINGS_ACTIONS,
    validate_savings_goal_flow_bounds,
)


@dataclass(frozen=True)
class TrackingRow:
    id: int
    d: date
    typ: str
    category: str
    amount: float
    details: str
    source: str = "manual"

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
        self._cols_cache: dict[str, set[str]] = {}

    def _cols(self, table: str) -> set[str]:
        cached = self._cols_cache.get(table)
        if cached is not None:
            return cached
        # v2.2.25 (d1-Härtung): Identifier-Guard wie migrations._cols –
        # Nicht-Identifier erreichen weder PRAGMA noch den Cache.
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            return set()
        try:
            cols = {
                str(r[1])
                for r in self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            }
        except Exception as e:
            logger.debug("_cols(%s): %s", table, e)
            cols = set()
        self._cols_cache[table] = cols
        return cols

    def _has_source_col(self) -> bool:
        return "source" in self._cols("tracking")

    def _has_savings_action_col(self) -> bool:
        return "savings_action" in self._cols("tracking")

    @staticmethod
    def _normalize_savings_action(
        typ: str, amount: float, action: str | None
    ) -> str | None:
        if typ != TYP_SAVINGS:
            return None
        candidate = str(action or "").strip().lower()
        if candidate in VALID_SAVINGS_ACTIONS:
            if amount >= 0 and candidate == ACTION_WITHDRAWAL:
                return ACTION_DEPOSIT
            return candidate
        return ACTION_WITHDRAWAL if amount < 0 else ACTION_DEPOSIT

    def _source_select_expr(self) -> str:
        return (
            "COALESCE(source, 'manual') AS source"
            if self._has_source_col()
            else "'manual' AS source"
        )

    def _entry_tag_ids(self, entry_id: int) -> list[int]:
        """Liest die vollständige Tag-Belegung einer Buchung für Undo/Redo."""
        try:
            rows = self.conn.execute(
                "SELECT tag_id FROM entry_tags WHERE entry_id=? ORDER BY tag_id",
                (int(entry_id),),
            ).fetchall()
            return [int(row[0]) for row in rows]
        except sqlite3.OperationalError:
            return []

    def _category_tag_ids(self, typ: str, category: str) -> set[int]:
        """Gibt die fest an einer Kategorie hinterlegten Tag-IDs zurück."""
        try:
            rows = self.conn.execute(
                """
                SELECT ct.tag_id
                FROM category_tags ct
                JOIN categories c ON c.id = ct.category_id
                WHERE c.typ=? AND c.name=?
                """,
                (str(typ), str(category)),
            ).fetchall()
            return {int(row[0]) for row in rows}
        except sqlite3.OperationalError:
            return set()

    def _sync_category_fixed_tags(
        self,
        entry_id: int,
        *,
        new_typ: str,
        new_category: str,
        old_typ: str | None = None,
        old_category: str | None = None,
    ) -> None:
        """Synchronisiert feste Kategorie-Tags und bewahrt manuelle Tags.

        Beim Kategorienwechsel werden nur Tags entfernt, die fest an der alten
        Kategorie hingen und nicht ebenfalls an der neuen Kategorie fest sind.
        Alle übrigen, manuell gesetzten Tags bleiben erhalten.
        """
        try:
            new_fixed = self._category_tag_ids(new_typ, new_category)
            old_fixed = (
                self._category_tag_ids(old_typ, old_category)
                if old_typ is not None and old_category is not None
                else set()
            )
            for tag_id in sorted(old_fixed - new_fixed):
                self.conn.execute(
                    "DELETE FROM entry_tags WHERE entry_id=? AND tag_id=?",
                    (int(entry_id), int(tag_id)),
                )
            for tag_id in sorted(new_fixed):
                self.conn.execute(
                    "INSERT OR IGNORE INTO entry_tags(entry_id, tag_id) VALUES(?, ?)",
                    (int(entry_id), int(tag_id)),
                )
        except sqlite3.OperationalError:
            # Alte/teilmigrierte DBs ohne Tag-Tabellen: Tracking darf nicht crashen.
            return

    def _apply_category_fixed_tags(
        self, entry_id: int, typ: str, category: str
    ) -> None:
        """Heftet fix an der Kategorie definierte Tags an eine Buchung.

        Zusätzliche manuelle Tags bleiben erhalten. Der Kategorienwechsel nutzt
        ``_sync_category_fixed_tags`` und entfernt dabei veraltete feste Tags.
        """
        self._sync_category_fixed_tags(
            int(entry_id), new_typ=str(typ), new_category=str(category)
        )

    def add(
        self,
        d: date | str,
        typ: str,
        category: str,
        amount: float,
        details: str = "",
        source: str = "manual",
        savings_action: str | None = None,
    ) -> int:
        from utils.money import require_finite_amount

        amount = require_finite_amount(amount, field="Buchungsbetrag")
        action = self._normalize_savings_action(typ, float(amount), savings_action)
        if typ == TYP_SAVINGS:
            self.validate_savings_goal_booking(category, float(amount), action)

        source = (source or "manual").strip() or "manual"
        with db_transaction(self.conn):
            columns = ["date", "typ", "category", "amount", "details"]
            values: list[object] = [
                _to_date_iso(d),
                typ,
                category,
                float(amount),
                details or "",
            ]
            if self._has_source_col():
                columns.append("source")
                values.append(source)
            if self._has_savings_action_col():
                columns.append("savings_action")
                values.append(action)
            placeholders = ",".join("?" for _ in values)
            cur = self.conn.execute(
                f"INSERT INTO tracking({','.join(columns)}) VALUES({placeholders})",  # nosec B608
                tuple(values),
            )
            rid = int(cur.lastrowid)
            self._apply_category_fixed_tags(rid, typ, category)
            if typ == TYP_SAVINGS:
                self._sync_savings(category, amount, action=action, add=True)

        try:
            row = self.conn.execute(
                "SELECT * FROM tracking WHERE id=?", (rid,)
            ).fetchone()
            if row:
                new_data = dict(row)
                new_data["_tag_ids"] = self._entry_tag_ids(rid)
                self.undo.record_operation("tracking", "INSERT", None, new_data)
        except Exception as exc:
            logger.warning(
                "Undo-Recording fehlgeschlagen nach INSERT (id=%s): %s", rid, exc
            )
        return rid

    def update(
        self,
        row_id: int,
        d: date | str,
        typ: str,
        category: str,
        amount: float,
        details: str = "",
        savings_action: str | None = None,
    ) -> None:
        from utils.money import require_finite_amount

        amount = require_finite_amount(amount, field="Buchungsbetrag")
        new_action = self._normalize_savings_action(typ, float(amount), savings_action)
        old_full = self.conn.execute(
            "SELECT * FROM tracking WHERE id=?", (int(row_id),)
        ).fetchone()
        old_tag_ids = self._entry_tag_ids(int(row_id)) if old_full else []

        changes: dict[str, list[float]] = {}
        if old_full:
            old_typ, old_cat, old_amt = self._tracking_row_type_category_amount(
                old_full
            )
            old_action = self._tracking_row_savings_action(old_full)
            if old_typ == TYP_SAVINGS:
                self._accumulate_savings_change(
                    changes, old_cat, old_amt, old_action, factor=-1.0
                )
        if typ == TYP_SAVINGS:
            self._accumulate_savings_change(
                changes, category, float(amount), new_action, factor=1.0
            )
        self._validate_savings_changes(changes)

        with db_transaction(self.conn):
            assignments = ["date=?", "typ=?", "category=?", "amount=?", "details=?"]
            values: list[object] = [
                _to_date_iso(d),
                typ,
                category,
                float(amount),
                details or "",
            ]
            if self._has_savings_action_col():
                assignments.append("savings_action=?")
                values.append(new_action)
            values.append(int(row_id))
            self.conn.execute(
                f"UPDATE tracking SET {','.join(assignments)} WHERE id=?",  # nosec B608
                tuple(values),
            )
            if old_full:
                old_typ, old_cat, old_amt = self._tracking_row_type_category_amount(
                    old_full
                )
                old_action = self._tracking_row_savings_action(old_full)
                self._sync_category_fixed_tags(
                    int(row_id),
                    old_typ=old_typ,
                    old_category=old_cat,
                    new_typ=typ,
                    new_category=category,
                )
                if old_typ == TYP_SAVINGS:
                    self._sync_savings(old_cat, old_amt, action=old_action, add=False)
            else:
                self._apply_category_fixed_tags(int(row_id), typ, category)
            if typ == TYP_SAVINGS:
                self._sync_savings(category, amount, action=new_action, add=True)

        try:
            new_full = self.conn.execute(
                "SELECT * FROM tracking WHERE id=?", (int(row_id),)
            ).fetchone()
            if old_full and new_full:
                old_data = dict(old_full)
                old_data["_tag_ids"] = old_tag_ids
                new_data = dict(new_full)
                new_data["_tag_ids"] = self._entry_tag_ids(int(row_id))
                self.undo.record_operation("tracking", "UPDATE", old_data, new_data)
        except Exception as exc:
            logger.warning(
                "Undo-Recording fehlgeschlagen nach UPDATE (id=%s): %s", row_id, exc
            )

    def delete(self, row_id: int) -> None:
        old_full = self.conn.execute(
            "SELECT * FROM tracking WHERE id=?", (int(row_id),)
        ).fetchone()
        old_tag_ids = self._entry_tag_ids(int(row_id)) if old_full else []
        if old_full:
            old_typ, old_cat, old_amt = self._tracking_row_type_category_amount(
                old_full
            )
            old_action = self._tracking_row_savings_action(old_full)
            changes: dict[str, list[float]] = {}
            if old_typ == TYP_SAVINGS:
                self._accumulate_savings_change(
                    changes, old_cat, old_amt, old_action, factor=-1.0
                )
            self._validate_savings_changes(changes)

        with db_transaction(self.conn):
            try:
                self.conn.execute(
                    "DELETE FROM entry_tags WHERE entry_id=?", (int(row_id),)
                )
            except sqlite3.OperationalError:
                pass
            self.conn.execute("DELETE FROM tracking WHERE id=?", (int(row_id),))
            if old_full:
                old_typ, old_cat, old_amt = self._tracking_row_type_category_amount(
                    old_full
                )
                old_action = self._tracking_row_savings_action(old_full)
                if old_typ == TYP_SAVINGS:
                    self._sync_savings(old_cat, old_amt, action=old_action, add=False)

        try:
            if old_full:
                old_data = dict(old_full)
                old_data["_tag_ids"] = old_tag_ids
                self.undo.record_operation("tracking", "DELETE", old_data, None)
        except Exception as exc:
            logger.warning(
                "Undo-Recording fehlgeschlagen nach DELETE (id=%s): %s", row_id, exc
            )

    def exists_in_month(
        self, *, year: int, month: int, typ: str, category: str
    ) -> bool:
        """True, wenn im gegebenen Monat bereits mindestens 1 Eintrag für typ+category existiert."""
        start, end = month_bounds(year, month)
        row = self.conn.execute(
            "SELECT 1 FROM tracking "
            "WHERE date >= ? AND date < ? AND typ=? AND category=? LIMIT 1",
            (start, end, typ, category),
        ).fetchone()
        return bool(row)

    def list_recent_sorted(self, days: int = 14) -> list[TrackingRow]:
        cutoff = (date.today() - timedelta(days=int(days))).isoformat()
        if self._has_source_col():
            cur = self.conn.execute(
                "SELECT id, date, typ, category, amount, "
                "COALESCE(details,'') AS details, "
                "COALESCE(source, 'manual') AS source "
                "FROM tracking WHERE date>=? ORDER BY date DESC, id DESC",
                (cutoff,),
            )
        else:
            cur = self.conn.execute(
                "SELECT id, date, typ, category, amount, "
                "COALESCE(details,'') AS details, 'manual' AS source "
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
                    str(r["source"] or "manual"),
                )
            )
        return out

    def list_all_sorted(self) -> list[TrackingRow]:
        if self._has_source_col():
            cur = self.conn.execute(
                "SELECT id, date, typ, category, amount, "
                "COALESCE(details,'') AS details, "
                "COALESCE(source, 'manual') AS source "
                "FROM tracking ORDER BY date DESC, id DESC"
            )
        else:
            cur = self.conn.execute(
                "SELECT id, date, typ, category, amount, "
                "COALESCE(details,'') AS details, 'manual' AS source "
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
                    str(r["source"] or "manual"),
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
        where_parts: list[str] = []
        params: list[object] = []

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
            placeholders = ",".join(["?"] * len(categories))
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
            start, end = year_bounds(year)
            where_parts.append("date >= ?")
            where_parts.append("date < ?")
            params.extend([start, end])

        # Tag-Filter: über Subquery auf entry_tags
        if tag_id is not None:
            where_parts.append(
                "id IN (SELECT entry_id FROM entry_tags WHERE tag_id = ?)"
            )
            params.append(int(tag_id))

        where_clause = " AND ".join(where_parts) if where_parts else "1=1"

        query = f"""
            SELECT id, date, typ, category, amount, COALESCE(details,'') AS details,
                   {self._source_select_expr()}
            FROM tracking
            WHERE {where_clause}
            ORDER BY date DESC, id DESC
        """  # nosec B608

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
                    str(r["source"] or "manual"),
                )
            )
        return out

    def category_usage_counts(
        self, typ: str | None = None, *, manual_only: bool = False
    ) -> dict[str, int]:
        """Zählt Buchungen je Kategorie.

        Args:
            typ: Optional – nur Buchungen dieses Typs zählen.
            manual_only: True = automatische Fixkosten-/Wiederkehrend-Buchungen
                nicht mitzählen. Für alte Datenbanken ohne ``tracking.source`` greift
                zusätzlich eine konservative Detail-Heuristik.

        Returns:
            Dict {Kategoriename: Anzahl}, nach Häufigkeit absteigend aufgebaut.
        """
        if not manual_only:
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

        source_expr = (
            "COALESCE(t.source, 'manual')" if self._has_source_col() else "'manual'"
        )
        where = ["1=1"]
        args: list[object] = []
        if typ:
            where.append("t.typ = ?")
            args.append(typ)
        cur = self.conn.execute(
            f"""
            SELECT
                t.typ,
                t.category,
                COALESCE(t.details, '') AS details,
                {source_expr} AS source,
                COALESCE(c.is_fix, 0) AS is_fix,
                COALESCE(c.is_recurring, 0) AS is_recurring
            FROM tracking t
            LEFT JOIN categories c
              ON c.typ = t.typ AND c.name = t.category
            WHERE {' AND '.join(where)}
            """,  # nosec B608
            tuple(args),
        )

        counts: dict[str, int] = {}
        for r in cur.fetchall():
            category = str(r["category"] if isinstance(r, sqlite3.Row) else r[1])
            details = str(r["details"] if isinstance(r, sqlite3.Row) else r[2])
            source = str(r["source"] if isinstance(r, sqlite3.Row) else r[3])
            is_fix = bool(r["is_fix"] if isinstance(r, sqlite3.Row) else r[4])
            is_recurring = bool(
                r["is_recurring"] if isinstance(r, sqlite3.Row) else r[5]
            )
            if self._is_automatic_usage(
                details=details,
                category=category,
                source=source,
                is_flagged=(is_fix or is_recurring),
            ):
                continue
            counts[category] = counts.get(category, 0) + 1

        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0].casefold())))

    @staticmethod
    def _is_automatic_usage(
        *, details: str, category: str, source: str, is_flagged: bool
    ) -> bool:
        """Bestimmt, ob eine Buchung für Nutzungs-Ranking als automatisch gilt."""
        src = (source or "manual").strip().lower()
        if src.startswith("auto"):
            return True

        det = (details or "").strip()
        if "Wiederkehrend (ID:" in det:
            return True

        # Altbestand hatte früher keine source-Spalte. Fixkosten/Wiederkehrend wurden
        # mit exakt "Monat - Kategorie" erzeugt. Nur bei geflaggten Kategorien
        # ausblenden, damit normale Kategorien mit leerer Bemerkung nicht verschwinden.
        if not is_flagged or not det or not category:
            return False
        month_names = {
            "januar",
            "februar",
            "märz",
            "maerz",
            "april",
            "mai",
            "juni",
            "juli",
            "august",
            "september",
            "oktober",
            "november",
            "dezember",
            "january",
            "february",
            "march",
            "april",
            "may",
            "june",
            "july",
            "august",
            "september",
            "october",
            "november",
            "december",
            "janvier",
            "février",
            "fevrier",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "août",
            "aout",
            "septembre",
            "octobre",
            "novembre",
            "décembre",
            "decembre",
        }
        low = det.casefold()
        cat = category.strip().casefold()
        if " - " not in low:
            return False
        prefix, suffix = low.split(" - ", 1)
        return prefix.strip() in month_names and suffix.strip() == cat

    def last_n_by_abs_amount(self, n: int = 5) -> list[TrackingRow]:
        if self._has_source_col():
            cur = self.conn.execute(
                "SELECT id, date, typ, category, amount, "
                "COALESCE(details,'') AS details, "
                "COALESCE(source, 'manual') AS source "
                "FROM tracking "
                "ORDER BY ABS(amount) DESC, date DESC, id DESC LIMIT ?",
                (int(n),),
            )
        else:
            cur = self.conn.execute(
                "SELECT id, date, typ, category, amount, "
                "COALESCE(details,'') AS details, 'manual' AS source "
                "FROM tracking "
                "ORDER BY ABS(amount) DESC, date DESC, id DESC LIMIT ?",
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
                    str(r["source"] or "manual"),
                )
            )
        return out

    def sum_by_typ(
        self, year: int | None = None, month: int | None = None
    ) -> dict[str, float]:
        where: list[str] = []
        args: list[object] = []
        if year is not None and month is not None:
            start, end = month_bounds(year, month)
            where.extend(["date >= ?", "date < ?"])
            args.extend([start, end])
        elif year is not None:
            start, end = year_bounds(year)
            where.extend(["date >= ?", "date < ?"])
            args.extend([start, end])
        elif month is not None:
            # Kein Jahr angegeben: Monatsvergleich über alle Jahre bleibt bewusst möglich.
            where.append("substr(date,6,2)=?")
            args.append(f"{int(month):02d}")
        w = ("WHERE " + " AND ".join(where)) if where else ""
        cur = self.conn.execute(
            f"SELECT typ, SUM(amount) AS s FROM tracking {w} GROUP BY typ",  # nosec B608
            tuple(args),
        )
        return {str(r["typ"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def get_month_total(self, year: int, month: int, typ: str, category: str) -> float:
        """Gibt die Summe aller Buchungen für eine Kategorie in einem Monat zurück."""
        start_date, end_date = month_bounds(year, month)
        cur = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) AS total FROM tracking "
            "WHERE date >= ? AND date < ? AND typ = ? AND category = ?",
            (start_date, end_date, typ, category),
        )
        row = cur.fetchone()
        return float(row["total"] if row else 0.0)

    def sum_by_category(
        self, typ: str, year: int | None = None, month: int | None = None
    ) -> dict[str, float]:
        where: list[str] = ["typ=?"]
        args: list[object] = [typ]
        if year is not None and month is not None:
            start, end = month_bounds(year, month)
            where.extend(["date >= ?", "date < ?"])
            args.extend([start, end])
        elif year is not None:
            start, end = year_bounds(year)
            where.extend(["date >= ?", "date < ?"])
            args.extend([start, end])
        elif month is not None:
            # Kein Jahr angegeben: Monatsvergleich über alle Jahre bleibt bewusst möglich.
            where.append("substr(date,6,2)=?")
            args.append(f"{int(month):02d}")
        w = "WHERE " + " AND ".join(where)
        cur = self.conn.execute(
            f"SELECT category, SUM(amount) AS s FROM tracking {w} GROUP BY category ORDER BY ABS(s) DESC",  # nosec B608
            tuple(args),
        )
        return {str(r["category"]): float(r["s"] or 0.0) for r in cur.fetchall()}

    def sum_by_month(self, year: int, typ: str | None = None) -> dict[int, float]:
        start, end = year_bounds(year)
        where: list[str] = ["date >= ?", "date < ?"]
        args: list[object] = [start, end]
        if typ is not None:
            where.append("typ=?")
            args.append(typ)
        w = "WHERE " + " AND ".join(where)
        cur = self.conn.execute(
            f"SELECT CAST(substr(date,6,2) AS INTEGER) AS m, SUM(amount) AS s "  # nosec B608
            f"FROM tracking {w} GROUP BY m ORDER BY m",
            tuple(args),
        )
        out = {int(r["m"]): float(r["s"] or 0.0) for r in cur.fetchall()}
        for m in range(1, 13):
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

    def get_entries_in_range(
        self, date_from: date, date_to: date, tag_id: int | None = None
    ) -> list[TrackingRow]:
        """
        Gibt alle Einträge in einem Datumsbereich zurück.

        Args:
            date_from: Start-Datum (inklusiv)
            date_to: End-Datum (inklusiv)
            tag_id: optionaler Tag-Filter (entry_tags JOIN)

        Returns:
            Liste von TrackingRow Objekten
        """
        return self.list_filtered(date_from=date_from, date_to=date_to, tag_id=tag_id)

    def sum_by_month_all(self, typ: str | None = None) -> dict[int, float]:
        where = []
        args = []
        if typ is not None:
            where.append("typ=?")
            args.append(typ)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        cur = self.conn.execute(
            f"SELECT CAST(substr(date,6,2) AS INTEGER) AS m, SUM(amount) AS s FROM tracking {w} GROUP BY m ORDER BY m",  # nosec B608
            tuple(args),
        )
        out = {int(r["m"]): float(r["s"] or 0.0) for r in cur.fetchall()}
        for m in range(1, 13):
            out.setdefault(m, 0.0)
        return out

    def _tracking_row_type_category_amount(self, row) -> tuple[str, str, float]:
        """Liest Typ/Kategorie/Betrag robust aus sqlite3.Row oder Tupel."""
        if isinstance(row, sqlite3.Row):
            return str(row["typ"]), str(row["category"]), float(row["amount"])
        return str(row[2]), str(row[3]), float(row[4])

    def _tracking_row_savings_action(self, row) -> str | None:
        typ, _category, amount = self._tracking_row_type_category_amount(row)
        raw = None
        if self._has_savings_action_col():
            try:
                raw = row["savings_action"] if isinstance(row, sqlite3.Row) else None
            except Exception:
                raw = None
        return self._normalize_savings_action(typ, amount, raw)

    @staticmethod
    def _flow_delta(
        amount: float, action: str | None, factor: float
    ) -> tuple[float, float, float]:
        """Liefert (Bestand, Einzahlungen, Bezüge) für Hinzufügen/Entfernen."""
        value = float(amount)
        stock_delta = factor * value
        if action == ACTION_WITHDRAWAL:
            return stock_delta, 0.0, factor * abs(value)
        return stock_delta, factor * value, 0.0

    def _accumulate_savings_change(
        self,
        changes: dict[str, list[float]],
        category: str,
        amount: float,
        action: str | None,
        *,
        factor: float,
    ) -> None:
        bucket = changes.setdefault(str(category), [0.0, 0.0, 0.0])
        deltas = self._flow_delta(float(amount), action, factor)
        for index, delta in enumerate(deltas):
            bucket[index] += delta

    def _active_goal_rows(self, category: str):
        cols = self._cols("savings_goals")
        if {"contributed_amount", "withdrawn_amount"}.issubset(cols):
            flow = "contributed_amount, withdrawn_amount"
        else:
            flow = "current_amount AS contributed_amount, 0 AS withdrawn_amount"
        return self.conn.execute(
            f"""
            SELECT id, name, current_amount, target_amount, {flow}
            FROM savings_goals
            WHERE category=? AND status IN (?, ?)
            """,  # nosec B608
            (category, STATUS_SAVING, STATUS_RELEASED),
        ).fetchall()

    def _validate_savings_changes(self, changes: dict[str, list[float]]) -> None:
        for category, (
            stock_delta,
            contribution_delta,
            withdrawal_delta,
        ) in changes.items():
            for goal in self._active_goal_rows(category):
                validate_savings_goal_flow_bounds(
                    goal_name=str(goal[1]),
                    target_amount=float(goal[3]),
                    current_stock=float(goal[2]),
                    contributed_amount=float(goal[4]),
                    stock_delta=stock_delta,
                    contribution_delta=contribution_delta,
                )
                if float(goal[5]) + withdrawal_delta < -0.005:
                    raise SavingsGoalBoundsError(
                        "savings.bounds.withdrawal_history_negative",
                        goal_name=str(goal[1]),
                        current_amount=float(goal[5]),
                        target_amount=float(goal[3]),
                        attempted_amount=abs(withdrawal_delta),
                        resulting_amount=float(goal[5]) + withdrawal_delta,
                        max_allowed=float(goal[5]),
                    )

    def _validate_savings_goal_category_delta(
        self, category: str, delta: float, action: str | None = None
    ) -> None:
        changes: dict[str, list[float]] = {}
        normalized = self._normalize_savings_action(TYP_SAVINGS, float(delta), action)
        self._accumulate_savings_change(
            changes, category, float(delta), normalized, factor=1.0
        )
        self._validate_savings_changes(changes)

    def _sync_savings(
        self,
        category: str,
        amount: float,
        *,
        action: str | None = None,
        add: bool,
    ) -> None:
        normalized = self._normalize_savings_action(TYP_SAVINGS, float(amount), action)
        factor = 1.0 if add else -1.0
        stock_delta, contribution_delta, withdrawal_delta = self._flow_delta(
            float(amount), normalized, factor
        )
        changes = {str(category): [stock_delta, contribution_delta, withdrawal_delta]}
        self._validate_savings_changes(changes)

        flow_cols = {"contributed_amount", "withdrawn_amount"}.issubset(
            self._cols("savings_goals")
        )
        for goal in self._active_goal_rows(category):
            goal_id = int(goal[0])
            if flow_cols:
                self.conn.execute(
                    """
                    UPDATE savings_goals
                    SET current_amount=current_amount+?,
                        contributed_amount=contributed_amount+?,
                        withdrawn_amount=withdrawn_amount+?
                    WHERE id=?
                    """,
                    (stock_delta, contribution_delta, withdrawal_delta, goal_id),
                )
            else:
                self.conn.execute(
                    "UPDATE savings_goals SET current_amount=current_amount+? WHERE id=?",
                    (stock_delta, goal_id),
                )

    def validate_savings_goal_booking(
        self, category: str, amount: float, action: str | None = None
    ) -> None:
        normalized = self._normalize_savings_action(TYP_SAVINGS, float(amount), action)
        changes: dict[str, list[float]] = {}
        self._accumulate_savings_change(
            changes, category, float(amount), normalized, factor=1.0
        )
        self._validate_savings_changes(changes)

    def check_savings_goal_conflict(self, category: str, amount: float) -> dict | None:
        if amount >= 0:
            return None
        cols = self._cols("savings_goals")
        contributed = (
            "contributed_amount" if "contributed_amount" in cols else "current_amount"
        )
        withdrawn = "withdrawn_amount" if "withdrawn_amount" in cols else "0"
        row = self.conn.execute(
            f"""
            SELECT id, name, status, current_amount, target_amount,
                   {contributed}, {withdrawn}, COALESCE(released_amount,0)
            FROM savings_goals
            WHERE category=? AND status IN (?, ?)
            ORDER BY id LIMIT 1
            """,  # nosec B608
            (category, STATUS_SAVING, STATUS_RELEASED),
        ).fetchone()
        if not row:
            return None
        return {
            "goal_id": int(row[0]),
            "goal_name": str(row[1]),
            "goal_status": str(row[2]),
            "current_amount": float(row[3]),
            "target_amount": float(row[4]),
            "contributed_amount": float(row[5]),
            "withdrawn_amount": float(row[6]),
            "released_amount": float(row[7]),
        }

    def get_savings_action(self, row_id: int) -> str | None:
        if not self._has_savings_action_col():
            return None
        row = self.conn.execute(
            "SELECT typ, amount, savings_action FROM tracking WHERE id=?",
            (int(row_id),),
        ).fetchone()
        if not row:
            return None
        return self._normalize_savings_action(str(row[0]), float(row[1]), row[2])

    # Legacy-Aliases
    def _sync_savings_goals_add(
        self, category: str, amount: float, action: str | None = None
    ) -> None:
        self._sync_savings(category, amount, action=action, add=True)
        self.conn.commit()

    def _sync_savings_goals_remove(
        self, category: str, amount: float, action: str | None = None
    ) -> None:
        self._sync_savings(category, amount, action=action, add=False)
        self.conn.commit()

    def count(self) -> int:
        """Anzahl der Tracking-Buchungen."""
        row = self.conn.execute("SELECT COUNT(*) FROM tracking").fetchone()
        return int(row[0]) if row else 0
