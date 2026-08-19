from __future__ import annotations

"""Rückstellungs-/POT-Auswertung für Kategorien wie Franchise/Selbstbehalt.

Ein POT ist fachlich kein normales Monatsbudget. Der sichtbare Rest ist deshalb
nicht nur Budget minus Ist des aktuellen Monats, sondern der Topfstand seit dem
Startmonat bis zum gewählten Monat.
"""

import calendar
import logging
import sqlite3
from dataclasses import dataclass
from datetime import date

from model.category_forecast_mode import (
    FORECAST_MODE_POT,
    effective_forecast_mode,
    normalize_forecast_mode,
)
from model.typ_constants import TYP_EXPENSES, is_income, normalize_typ

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PotReserveStatus:
    typ: str
    category: str
    cap: float
    spent: float
    rest: float
    start: date
    end: date
    is_overdrawn: bool
    has_budget: bool


class PotReserveModel:
    """Berechnet den Rest eines POT-/Rückstellungs-Systems.

    Regeln:
    - Nur Ausgaben-Kategorien können als POT angezeigt werden.
    - Expliziter forecast_mode='pot' oder Auto-Regel: fix=True und recurring=False.
    - Topf-Cap = höchster positiver Budgetwert im Zeitraum. Dadurch wird ein
      über alle Monate kopierter 750er Franchise-Wert als EIN 750er Topf
      interpretiert, nicht als 12×750.
    - Ohne Budget wird trotzdem ein Status geliefert, sobald Buchungen vorhanden
      sind: cap=0, rest negativ. Das ist wichtig, damit Cockpit/Warnings nicht
      stumm bleiben, wenn Tracking-only begonnen wurde.
    """

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def is_pot_category(self, typ: str, category: str) -> bool:
        typ_db = normalize_typ(str(typ))
        if typ_db != TYP_EXPENSES or is_income(typ_db):
            return False
        try:
            cols = {
                str(r[1])
                for r in self.conn.execute("PRAGMA table_info(categories)").fetchall()
            }
            if not {"typ", "name"}.issubset(cols):
                return False
            select_cols = ["COALESCE(is_fix,0)", "COALESCE(is_recurring,0)"]
            if "forecast_mode" in cols:
                select_cols.append("forecast_mode")
            else:
                select_cols.append("NULL")
            row = self.conn.execute(
                f"SELECT {', '.join(select_cols)} FROM categories WHERE typ=? AND name=? LIMIT 1",  # nosec B608
                (typ_db, str(category)),
            ).fetchone()
            if not row:
                return False
            is_fix = bool(int(row[0] or 0))
            is_recurring = bool(int(row[1] or 0))
            stored = normalize_forecast_mode(row[2]) if row[2] is not None else None
            return (
                effective_forecast_mode(stored, is_fix, is_recurring)
                == FORECAST_MODE_POT
            )
        except Exception as exc:
            logger.debug("is_pot_category(%s/%s): %s", typ, category, exc)
            return False

    def status(
        self,
        year: int,
        month: int,
        typ: str,
        category: str,
        *,
        start_month: int = 1,
        start_year: int | None = None,
    ) -> PotReserveStatus | None:
        typ_db = normalize_typ(str(typ))
        cat = str(category)
        if not self.is_pot_category(typ_db, cat):
            return None
        y = int(year)
        m = max(1, min(12, int(month or 1)))
        sy = int(start_year) if start_year else y
        sm = max(1, min(12, int(start_month or 1)))
        start = date(sy, sm, 1)
        last_day = calendar.monthrange(y, m)[1]
        end = date(y, m, last_day)
        if start > end:
            start = date(y, 1, 1)

        cap = self._max_budget_cap(start, end, typ_db, cat)
        spent = self._spent_sum(start, end, typ_db, cat)
        rest = cap - spent
        if cap <= 0.0 and spent <= 0.0:
            return None
        return PotReserveStatus(
            typ=typ_db,
            category=cat,
            cap=float(cap),
            spent=float(spent),
            rest=float(rest),
            start=start,
            end=end,
            is_overdrawn=bool(spent > cap + 1e-6),
            has_budget=bool(cap > 0.0),
        )

    def _max_budget_cap(self, start: date, end: date, typ: str, category: str) -> float:
        rows = self.conn.execute(
            """
            SELECT COALESCE(MAX(amount), 0)
            FROM budget
            WHERE typ=? AND category=?
              AND (year > ? OR (year = ? AND month >= ?))
              AND (year < ? OR (year = ? AND month <= ?))
            """,
            (
                typ,
                category,
                start.year,
                start.year,
                start.month,
                end.year,
                end.year,
                end.month,
            ),
        ).fetchone()
        try:
            return max(0.0, float(rows[0] if rows and rows[0] is not None else 0.0))
        except Exception:
            return 0.0

    def _spent_sum(self, start: date, end: date, typ: str, category: str) -> float:
        rows = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM tracking
            WHERE typ=? AND category=? AND date>=? AND date<=?
            """,
            (typ, category, start.isoformat(), end.isoformat()),
        ).fetchone()
        try:
            return abs(float(rows[0] if rows and rows[0] is not None else 0.0))
        except Exception:
            return 0.0
