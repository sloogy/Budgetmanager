"""Monatsabschluss-Assistent – Logik (v2.2.0, Qt-frei).

Rechnet den Monat ab: Einnahmen − Ausgaben − Ersparnisse.

- ÜBERSCHUSS: Vorschlag, den Rest in eine Ersparnis-Kategorie zu buchen
  (bevorzugt die Kategorie des aktivsten offenen Sparziels). Gebucht wird erst
  nach Bestätigung durch den Nutzer.
- DEFIZIT: Vorschlag, das Loch aus einer Ersparnis-Kategorie MIT Guthaben zu
  decken (Entnahme = negative Ersparnis-Buchung). Zusätzlich rein informativ:
  variable Kategorien, deren Budget im Folgemonat Spielraum bietet.
  ZENTRALE REGEL: Fixkosten und wiederkehrende Kategorien werden NIEMALS als
  Kürzungskandidaten genannt.

Der Abschluss wird pro Monat in ``system_flags`` vermerkt (rein informativ,
Buchungen bleiben normale Tracking-Einträge und sind per Undo rückholbar).
"""

from __future__ import annotations

import calendar
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import date

from model.typ_constants import (
    TYP_EXPENSES,
    TYP_INCOME,
    TYP_SAVINGS,
)

logger = logging.getLogger(__name__)

_FLAG_PREFIX = "month_closed"


@dataclass
class MonthCloseInfo:
    year: int
    month: int
    income_actual: float
    expense_actual: float
    savings_actual: float
    balance: float  # Einnahmen − Ausgaben − Ersparnisse
    already_closed: bool
    surplus_target: str | None  # Vorschlags-Kategorie (Ersparnis) bei Überschuss
    savings_with_funds: list[tuple[str, float]] = field(default_factory=list)
    reduction_hints: list[tuple[str, float, float]] = field(default_factory=list)
    # reduction_hints: (Kategorie, Budget Folgemonat, Ist Ø) – nur variable Kategorien


class MonthCloseModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    # ── Berechnung ───────────────────────────────────────────────
    def _actual_sum(self, year: int, month: int, typ: str) -> float:
        row = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM tracking "
            "WHERE typ = ? AND strftime('%Y', date) = ? AND strftime('%m', date) = ?",
            (typ, f"{year:04d}", f"{month:02d}"),
        ).fetchone()
        return float(row[0] or 0.0)

    def compute(self, year: int, month: int) -> MonthCloseInfo:
        income = self._actual_sum(year, month, TYP_INCOME)
        expenses = abs(self._actual_sum(year, month, TYP_EXPENSES))
        savings = self._actual_sum(year, month, TYP_SAVINGS)
        balance = income - expenses - savings

        info = MonthCloseInfo(
            year=year,
            month=month,
            income_actual=income,
            expense_actual=expenses,
            savings_actual=savings,
            balance=balance,
            already_closed=self.is_closed(year, month),
            surplus_target=None,
        )
        if balance > 0.005:
            info.surplus_target = self._suggest_surplus_target()
        elif balance < -0.005:
            # Nur Guthaben verwenden, das bis zum Ende des abzuschliessenden
            # Monats tatsächlich vorhanden war. Beim nachträglichen Abschluss
            # eines Vormonats darf kein Spar-Guthaben aus späteren Monaten als
            # Deckung angeboten werden.
            info.savings_with_funds = self._savings_with_funds(year, month)
            info.reduction_hints = self._reduction_hints(year, month)
        return info

    def _suggest_surplus_target(self) -> str | None:
        """Ersparnis-Ziel: offenes Sparziel mit grösstem Restbedarf, sonst
        erste Ersparnis-Kategorie."""
        try:
            row = self.conn.execute(
                "SELECT category FROM savings_goals "
                "WHERE COALESCE(status, 'active') = 'active' "
                "AND category IS NOT NULL AND category != '' "
                "ORDER BY (target_amount - current_amount) DESC LIMIT 1"
            ).fetchone()
            if row and row[0]:
                return str(row[0])
        except Exception as e:
            logger.debug("surplus target via goals: %s", e)
        row = self.conn.execute(
            "SELECT name FROM categories WHERE typ = ? ORDER BY sort_order, name LIMIT 1",
            (TYP_SAVINGS,),
        ).fetchone()
        return str(row[0]) if row else None

    def _savings_with_funds(
        self, year: int | None = None, month: int | None = None
    ) -> list[tuple[str, float]]:
        """Ersparnis-Kategorien mit positivem Saldo (Entnahme möglich).

        Wenn ``year/month`` gesetzt ist, wird nur der Saldo bis einschliesslich
        dieses Monats berücksichtigt. Das ist wichtig für Backlog-Abschlüsse:
        Wird z. B. Mai erst im Juli abgeschlossen, dürfen Juni/Juli-Ersparnisse
        nicht rückwirkend als Mai-Guthaben angeboten werden.
        """
        params: list[object] = [TYP_SAVINGS]
        date_clause = ""
        if year is not None and month is not None:
            next_y, next_m = (
                (int(year) + 1, 1) if int(month) == 12 else (int(year), int(month) + 1)
            )
            date_clause = " AND date < ?"
            params.append(f"{next_y:04d}-{next_m:02d}-01")
        rows = self.conn.execute(
            "SELECT category, COALESCE(SUM(amount), 0) AS saldo FROM tracking "  # nosec B608
            "WHERE typ = ?" + date_clause + " GROUP BY category HAVING saldo > 0.005 "
            "ORDER BY saldo DESC",
            tuple(params),
        ).fetchall()
        return [(str(r[0]), float(r[1])) for r in rows]

    def _reduction_hints(self, year: int, month: int) -> list[tuple[str, float, float]]:
        """Variable Kategorien mit Budget im Folgemonat – reine Information.

        Fixkosten (is_fix) und wiederkehrende Kategorien (is_recurring) sind
        ausgeschlossen: die kürzt man nicht "blind" am Monatsende.
        """
        ny, nm = (year + 1, 1) if month == 12 else (year, month + 1)
        rows = self.conn.execute(
            "SELECT b.category, b.amount FROM budget b "
            "JOIN categories c ON c.typ = b.typ AND c.name = b.category "
            "WHERE b.typ = ? AND b.year = ? AND b.month = ? AND b.amount > 0 "
            "AND COALESCE(c.is_fix, 0) = 0 AND COALESCE(c.is_recurring, 0) = 0 "
            "ORDER BY b.amount DESC LIMIT 5",
            (TYP_EXPENSES, ny, nm),
        ).fetchall()
        out: list[tuple[str, float, float]] = []
        for cat, budget in rows:
            avg_row = self.conn.execute(
                "SELECT COALESCE(AVG(monthsum), 0) FROM ("
                "  SELECT SUM(ABS(amount)) AS monthsum FROM tracking "
                "  WHERE typ = ? AND category = ? "
                "  GROUP BY strftime('%Y-%m', date) ORDER BY strftime('%Y-%m', date) DESC LIMIT 3"
                ")",
                (TYP_EXPENSES, str(cat)),
            ).fetchone()
            out.append((str(cat), float(budget), float(avg_row[0] or 0.0)))
        return out

    # ── Offene Monate für Cockpit-Vorschläge ─────────────────────
    def list_open_months_before(
        self,
        year: int,
        month: int,
        *,
        limit: int = 12,
    ) -> list[tuple[int, int]]:
        """Return unclosed months before ``year/month`` that have data.

        Der Monatsabschluss soll nicht nur den laufenden Monat sehen. Sobald
        ein Vormonat Budget- oder Tracking-Daten hat und noch nicht als
        abgeschlossen markiert wurde, wird er dem Cockpit vorgeschlagen.
        Monate ohne Daten werden bewusst ignoriert, damit ein neuer Nutzer
        nicht mit leeren historischen Monaten zugespamt wird.
        """
        year = int(year)
        month = int(month)
        limit = max(1, int(limit or 12))
        cutoff = f"{year:04d}-{month:02d}"
        rows = self.conn.execute(
            """
            SELECT ym FROM (
                SELECT substr(date, 1, 7) AS ym FROM tracking
                WHERE date IS NOT NULL AND length(date) >= 7
                UNION
                SELECT printf('%04d-%02d', year, month) AS ym FROM budget
                WHERE COALESCE(amount, 0) != 0
            )
            WHERE ym < ?
            ORDER BY ym ASC
            """,
            (cutoff,),
        ).fetchall()

        out: list[tuple[int, int]] = []
        seen: set[tuple[int, int]] = set()
        for row in rows:
            ym = str(row[0] or "")
            try:
                y_s, m_s = ym.split("-", 1)
                y, m = int(y_s), int(m_s)
            except Exception:
                continue
            if m < 1 or m > 12:
                continue
            key = (y, m)
            if key in seen or self.is_closed(y, m):
                continue
            seen.add(key)
            out.append(key)
            if len(out) >= limit:
                break
        return out

    def suggested_month_to_close(
        self, as_of: date | None = None
    ) -> tuple[int, int] | None:
        """Oldest open past month, or current month near month-end.

        Best Practice: Vormonate zuerst abschliessen. Dadurch bleiben
        Carryover, Budgetvorschläge und die Monatsbilanz chronologisch sauber.
        """
        today = as_of or date.today()
        overdue = self.list_open_months_before(today.year, today.month, limit=1)
        if overdue:
            return overdue[0]
        if today.day >= 25 and not self.is_closed(today.year, today.month):
            return today.year, today.month
        return None

    # ── Aktionen (nur nach Nutzer-Bestätigung aufrufen) ──────────
    def _last_day(self, year: int, month: int) -> date:
        return date(year, month, calendar.monthrange(year, month)[1])

    def book_surplus(
        self, year: int, month: int, amount: float, category: str, details: str
    ) -> None:
        """Überschuss als Ersparnis-Buchung am Monatsletzten erfassen."""
        if amount <= 0:
            raise ValueError("surplus amount must be > 0")
        from model.tracking_model import TrackingModel

        TrackingModel(self.conn).add(
            self._last_day(year, month),
            TYP_SAVINGS,
            str(category),
            float(amount),
            details,
        )

    def cover_deficit_from_savings(
        self, year: int, month: int, amount: float, category: str, details: str
    ) -> None:
        """Defizit durch Entnahme (negative Ersparnis-Buchung) decken."""
        if amount <= 0:
            raise ValueError("deficit amount must be > 0")
        from model.tracking_model import TrackingModel

        TrackingModel(self.conn).add(
            self._last_day(year, month),
            TYP_SAVINGS,
            str(category),
            -float(amount),
            details,
        )

    # ── Abschluss-Vermerk ────────────────────────────────────────
    def is_closed(self, year: int, month: int) -> bool:
        row = self.conn.execute(
            "SELECT value FROM system_flags WHERE key = ?",
            (f"{_FLAG_PREFIX}:{year:04d}-{month:02d}",),
        ).fetchone()
        return bool(row and str(row[0]) == "1")

    def mark_closed(self, year: int, month: int) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO system_flags(key, value) VALUES(?, ?)",
            (f"{_FLAG_PREFIX}:{year:04d}-{month:02d}", "1"),
        )
        self.conn.commit()
