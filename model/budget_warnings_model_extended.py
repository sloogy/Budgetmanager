from __future__ import annotations
import logging

logger = logging.getLogger(__name__)
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Optional
from datetime import date

from model.budget_suggestion_engine import BudgetSuggestionEngine
from model.date_ranges import month_bounds
from model.typ_constants import (
    TYP_INCOME,
    TYP_EXPENSES,
    TYP_SAVINGS,
    normalize_typ,
    is_income,
    rest_sign,
    ALL_TYPEN,
)


@dataclass
class BudgetWarning:
    id: int
    year: int
    month: int
    typ: str
    category: str
    threshold_percent: int
    enabled: bool


@dataclass
class BudgetExceedance:
    """Informationen über eine Budget-Überschreitung"""

    typ: str
    category: str
    year: int
    month: int
    budget: float
    spent: float
    threshold_percent: int
    percent_used: float
    suggestion: Optional[float] = None  # Vorgeschlagenes Budget
    exceed_count: int = 0  # Wie oft überschritten in letzten Monaten


class BudgetWarningsModelExtended:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self._engine = BudgetSuggestionEngine(conn)

    def create(
        self,
        year: int,
        month: int,
        typ: str,
        category: str,
        threshold_percent: int = 90,
    ) -> int:
        """Erstellt eine Budget-Warnung"""
        try:
            cur = self.conn.execute(
                """
                INSERT INTO budget_warnings 
                (year, month, typ, category, threshold_percent, enabled)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (year, month, typ, category, threshold_percent),
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return 0  # bereits vorhanden

    def update(
        self,
        warning_id: int,
        threshold_percent: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        """Aktualisiert eine Warnung"""
        updates = []
        params = []

        if threshold_percent is not None:
            updates.append("threshold_percent = ?")
            params.append(threshold_percent)
        if enabled is not None:
            updates.append("enabled = ?")
            params.append(1 if enabled else 0)

        if updates:
            params.append(warning_id)
            query = f"UPDATE budget_warnings SET {', '.join(updates)} WHERE id = ?"
            self.conn.execute(query, params)
            self.conn.commit()

    def delete(self, warning_id: int) -> None:
        """Löscht eine Warnung"""
        self.conn.execute("DELETE FROM budget_warnings WHERE id = ?", (warning_id,))
        self.conn.commit()

    def get_warnings(
        self, year: int, month: int, typ: str | None = None
    ) -> List[BudgetWarning]:
        """Gibt alle Warnungen für Jahr/Monat zurück"""
        if typ:
            cur = self.conn.execute(
                """
                SELECT id, year, month, typ, category, threshold_percent, enabled
                FROM budget_warnings
                WHERE year = ? AND month = ? AND typ = ? AND enabled = 1
                """,
                (year, month, typ),
            )
        else:
            cur = self.conn.execute(
                """
                SELECT id, year, month, typ, category, threshold_percent, enabled
                FROM budget_warnings
                WHERE year = ? AND month = ? AND enabled = 1
                """,
                (year, month),
            )

        return [
            BudgetWarning(
                id=row[0],
                year=row[1],
                month=row[2],
                typ=row[3],
                category=row[4],
                threshold_percent=row[5],
                enabled=bool(row[6]),
            )
            for row in cur.fetchall()
        ]

    def check_warnings_extended(
        self, year: int, month: int, lookback_months: int = 6
    ) -> List[BudgetExceedance]:
        """
        Prüft alle Warnungen und gibt überschrittene zurück mit erweiterten Infos

        Args:
            year: Jahr
            month: Monat
            lookback_months: Wie viele Monate zurückschauen für Überschreitungshistorie

        Returns:
            Liste von BudgetExceedance-Objekten mit Vorschlägen
        """
        # WICHTIG: ``warn_budget_overrun`` steuert nur passive/automatische
        # Start- oder Banner-Hinweise. Die manuell geöffnete Funktion
        # "Budgetwarnungen/Budgetvorschläge" darf dadurch NICHT leer bleiben.
        # Nach einem Restore können Settings-Defaults sonst die komplette
        # Warn-/Vorschlagslogik scheinbar deaktivieren, obwohl Budget und
        # Trackingdaten vorhanden sind.

        # Explizit gespeicherte Warnungen holen
        warnings = self.get_warnings(year, month)

        # Auto-Generierung: Wenn keine expliziten Warnungen vorhanden, temporäre aus Budget erzeugen.
        # Gesteuert über Setting "auto_generate_budget_warnings" (default: True).
        self._auto_generated = False  # Für UI-Kennzeichnung (Dialog zeigt Hinweis)
        if not warnings:
            try:
                from settings import Settings

                auto_gen = bool(Settings().get("auto_generate_budget_warnings", True))
            except Exception:
                auto_gen = True
            if auto_gen:
                # KILLCRITIC v2.2.5 Nachaudit:
                # Nicht nur den Zielmonat scannen. Wenn der Nutzer im Juli
                # Vorschläge öffnet, Juli aber noch kein Budget hat, müssen
                # Kategorien aus der letzten bekannten Budgetbasis trotzdem als
                # temporäre Warn-/Vorschlagskandidaten auftauchen. Sonst bleibt
                # das Cockpit-Warnpanel leer, obwohl die Engine intern z. B.
                # Jan-Jun als dauerhaft über Budget erkennt.
                candidate_keys = self._budget_candidate_keys_before_or_at(
                    year, month, lookback_months
                )
                warnings = [
                    BudgetWarning(
                        id=0,
                        year=year,
                        month=month,
                        typ=t,
                        category=c,
                        threshold_percent=100,
                        enabled=True,
                    )
                    for t, c in sorted(candidate_keys)
                ]
                self._auto_generated = bool(warnings)
        exceeded = []

        # Einheitliche Engine-Parameter (eine Quelle der Wahrheit)
        # Wichtig: require_same_sign_ratio darf NICHT 1.0 sein, sonst blockiert
        # ein einzelner Ausreisser-Monat den Vorschlag.
        try:
            from settings import Settings

            sign_ratio = float(
                Settings().get("budget_suggestion_sign_ratio", 0.7) or 0.7
            )
        except Exception:
            sign_ratio = 0.7

        for warn in warnings:
            # Budget abrufen: Zielmonat bevorzugen, sonst letzte positive
            # Budgetbasis <= Zielmonat. Das hält Warnungen konsistent mit der
            # Vorschlagsengine und verhindert leere Warnpanels bei leerem
            # aktuellem Monat.
            budget = self._effective_budget_amount(
                year, month, warn.typ, warn.category, lookback_months
            )
            if budget <= 0:
                continue

            # Ausgaben abrufen (nur für den Monat)
            start_date, end_date = month_bounds(year, month)

            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start_date, end_date, warn.typ, warn.category),
            )
            spent = float(cur.fetchone()[0])
            # Ausgaben/Ersparnisse: abs() für Konsistenz mit Engine
            if not is_income(warn.typ):
                spent = abs(spent)

            # Prozentverwendung
            percent_used = (spent / budget) * 100 if budget > 0 else 0.0

            # EINHEITLICHE LOGIK (eine Quelle der Wahrheit):
            # - Vorschlag kann sowohl bei dauerhaftem Überschreiten als auch Unterschreiten entstehen.
            # - Ein Eintrag wird angezeigt, wenn:
            #   a) percent_used >= threshold_percent (klassischer Warner) ODER
            #   b) ein valider Vorschlag existiert.
            suggestion = None
            try:
                res = self._engine.compute_category_suggestion(
                    typ=warn.typ,
                    category=warn.category,
                    year=year,
                    month=month,
                    months_back=lookback_months,
                    alpha=0.8,
                    min_abs_change=20.0,
                    min_pct_change=0.05,
                    round_to=10.0,
                    require_same_sign_ratio=sign_ratio,
                )
                suggestion = res.suggested_budget if res else None
            except Exception:
                suggestion = None

            if percent_used >= float(warn.threshold_percent) or suggestion is not None:
                exceed_count = self._get_exceed_count(
                    warn.typ, warn.category, year, month, lookback_months
                )

                exceeded.append(
                    BudgetExceedance(
                        typ=warn.typ,
                        category=warn.category,
                        year=year,
                        month=month,
                        budget=budget,
                        spent=spent,
                        threshold_percent=warn.threshold_percent,
                        percent_used=percent_used,
                        suggestion=suggestion,
                        exceed_count=exceed_count,
                    )
                )

        return exceeded

    def _budget_candidate_keys_before_or_at(
        self, year: int, month: int, lookback_months: int
    ) -> set[tuple[str, str]]:
        """Budget-Kandidaten aus Zielmonat oder letzter bekannter Planbasis.

        Für Warnungen/Vorschläge muss ein leerer Zielmonat nicht bedeuten, dass
        keine Kategorien geprüft werden. Wir betrachten die letzten N*3 Monate,
        analog zur Forecast-Engine, und sammeln Kategorien mit positivem Budget.
        """
        keys: set[tuple[str, str]] = set()
        base = date(int(year), max(1, min(12, int(month or 1))), 1)
        max_scan = max(1, int(lookback_months or 3)) * 3
        for i in range(max_scan):
            d = self._subtract_months(base, i)
            rows = self.conn.execute(
                """
                SELECT DISTINCT typ, category
                FROM budget
                WHERE year = ? AND month = ? AND COALESCE(amount, 0) > 0
                """,
                (d.year, d.month),
            ).fetchall()
            for row in rows:
                keys.add((str(row[0]), str(row[1])))
        return keys

    def _effective_budget_amount(
        self, year: int, month: int, typ: str, category: str, lookback_months: int
    ) -> float:
        """Budget im Zielmonat, sonst letzte positive Budgetbasis <= Zielmonat."""
        base = date(int(year), max(1, min(12, int(month or 1))), 1)
        max_scan = max(1, int(lookback_months or 3)) * 3
        for i in range(max_scan):
            d = self._subtract_months(base, i)
            row = self.conn.execute(
                """
                SELECT amount FROM budget
                WHERE year = ? AND month = ? AND typ = ? AND category = ?
                """,
                (d.year, d.month, typ, category),
            ).fetchone()
            try:
                amount = float(row[0] if row else 0.0)
            except Exception:
                amount = 0.0
            if amount > 0:
                return amount
        return 0.0

    def _get_exceed_count(
        self, typ: str, category: str, year: int, month: int, lookback_months: int
    ) -> int:
        """Zählt Überschreitungen in den letzten N echten Budgetmonaten.

        Ein leerer Zielmonat darf die Historie nicht verkürzen. Beispiel:
        Im Juli ist noch kein Budget gesetzt, aber April-Juni waren über Budget.
        Dann müssen bei ``lookback_months=3`` auch genau April, Mai und Juni
        gezählt werden – nicht Juli leer + Juni + Mai.
        """
        count = 0
        checked_budget_months = 0
        current_date = date(year, month, 1)
        max_scan = max(1, int(lookback_months or 3)) * 3

        for i in range(max_scan):
            if checked_budget_months >= int(lookback_months or 3):
                break
            check_date = self._subtract_months(current_date, i)
            check_year = check_date.year
            check_month = check_date.month

            cur = self.conn.execute(
                "SELECT amount FROM budget WHERE year = ? AND month = ? AND typ = ? AND category = ?",
                (check_year, check_month, typ, category),
            )
            budget_row = cur.fetchone()
            try:
                budget = float(budget_row[0] if budget_row else 0.0)
            except Exception:
                budget = 0.0
            if budget <= 0:
                continue

            checked_budget_months += 1
            start, end = month_bounds(check_year, check_month)

            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start, end, typ, category),
            )
            spent = float(cur.fetchone()[0])
            if not is_income(typ):
                spent = abs(spent)

            if spent >= budget:
                count += 1

        return count

    # _calculate_budget_suggestion wurde ersetzt durch BudgetSuggestionEngine

    def _subtract_months(self, start_date: date, months: int) -> date:
        """Subtrahiert N Monate von einem Datum"""
        month = start_date.month - months
        year = start_date.year

        while month < 1:
            month += 12
            year -= 1

        return date(year, month, 1)

    def apply_budget_suggestion(
        self,
        typ: str,
        category: str,
        year: int,
        month: int,
        new_budget: float,
        remaining_months: bool = False,
    ) -> int:
        """Wendet den Budget-Vorschlag an.

        Args:
            remaining_months: Wenn True, wird das Budget für alle restlichen Monate
                            des Jahres (ab month) angewendet. Sonst nur für month.

        Returns:
            Anzahl der angepassten Monate
        """
        if remaining_months:
            count = 0
            for m in range(month, 13):
                self.conn.execute(
                    """
                    INSERT OR REPLACE INTO budget (year, month, typ, category, amount)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (year, m, typ, category, new_budget),
                )
                count += 1
            self.conn.commit()
            return count
        else:
            self.conn.execute(
                """
                INSERT OR REPLACE INTO budget (year, month, typ, category, amount)
                VALUES (?, ?, ?, ?, ?)
                """,
                (year, month, typ, category, new_budget),
            )
            self.conn.commit()
            return 1

    def mark_suggestion_accepted(
        self, typ: str, category: str, year: int, month: int
    ) -> None:
        """Markiert einen Vorschlag als angenommen für diesen Monat.

        Verhindert dass dieselbe Kategorie im selben Monat erneut vorgeschlagen wird.
        Nächsten Monat erscheint sie wieder (falls die Engine einen neuen Vorschlag generiert).
        """
        try:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO suggestion_accepted (typ, category, year, month)
                VALUES (?, ?, ?, ?)
                """,
                (typ, category, year, month),
            )
            self.conn.commit()
        except Exception as e:
            logger.warning("mark_suggestion_accepted fehlgeschlagen: %s", e)

    def get_accepted_for_month(self, year: int, month: int) -> set[tuple[str, str]]:
        """Gibt alle (typ, category)-Paare zurück, die in diesem Monat bereits angenommen wurden."""
        try:
            rows = self.conn.execute(
                """
                SELECT sa.typ, sa.category
                FROM suggestion_accepted sa
                WHERE sa.year=? AND sa.month=?
                  AND EXISTS (
                      SELECT 1 FROM budget b
                      WHERE b.year = sa.year
                        AND b.typ = sa.typ
                        AND b.category = sa.category
                        AND COALESCE(b.amount, 0) > 0
                  )
                """,
                (year, month),
            ).fetchall()
            return {(r[0], r[1]) for r in rows}
        except Exception as e:
            logger.warning("get_accepted_for_month fehlgeschlagen: %s", e)
            return set()

    def get_exceed_statistics(self, typ: str, category: str, months: int = 6) -> Dict:
        """
        Gibt Statistiken über Budget-Überschreitungen zurück

        Returns:
            {
                'months_checked': int,
                'times_exceeded': int,
                'avg_overspend_percent': float,
                'max_overspend_percent': float,
                'suggestion': float
            }
        """
        today = date.today()
        times_exceeded = 0
        overspend_percents = []

        # Einheitlicher Sign-Ratio-Parameter (wie überall)
        try:
            from settings import Settings

            sign_ratio = float(
                Settings().get("budget_suggestion_sign_ratio", 0.7) or 0.7
            )
        except Exception:
            sign_ratio = 0.7

        for i in range(months):
            check_date = self._subtract_months(today, i)
            check_year = check_date.year
            check_month = check_date.month

            # Budget holen
            cur = self.conn.execute(
                "SELECT amount FROM budget WHERE year = ? AND month = ? AND typ = ? AND category = ?",
                (check_year, check_month, typ, category),
            )
            budget_row = cur.fetchone()
            if not budget_row or budget_row[0] <= 0:
                continue
            budget = float(budget_row[0])

            # Ausgaben holen
            start, end = month_bounds(check_year, check_month)

            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start, end, typ, category),
            )
            spent = float(cur.fetchone()[0])
            if not is_income(typ):
                spent = abs(spent)

            if spent > budget:
                times_exceeded += 1
                overspend_percent = ((spent - budget) / budget) * 100
                overspend_percents.append(overspend_percent)

        # Einheitlicher Vorschlag (kann auch bei dauerhaftem Unterschreiten kommen)
        res = None
        try:
            res = self._engine.compute_category_suggestion(
                typ=typ,
                category=category,
                year=today.year,
                month=today.month,
                months_back=months,
                alpha=0.8,
                min_abs_change=20.0,
                min_pct_change=0.05,
                round_to=10.0,
                require_same_sign_ratio=sign_ratio,
            )
        except Exception:
            res = None

        suggestion = res.suggested_budget if res else 0.0

        return {
            "months_checked": months,
            "times_exceeded": times_exceeded,
            "avg_overspend_percent": (
                sum(overspend_percents) / len(overspend_percents)
                if overspend_percents
                else 0
            ),
            "max_overspend_percent": (
                max(overspend_percents) if overspend_percents else 0
            ),
            "suggestion": suggestion,
        }

    def list_all(self) -> List[BudgetWarning]:
        """Liste alle Warnungen"""
        cur = self.conn.execute(
            """
            SELECT id, year, month, typ, category, threshold_percent, enabled
            FROM budget_warnings
            ORDER BY year DESC, month DESC, typ, category
            """
        )
        return [
            BudgetWarning(
                id=row[0],
                year=row[1],
                month=row[2],
                typ=row[3],
                category=row[4],
                threshold_percent=row[5],
                enabled=bool(row[6]),
            )
            for row in cur.fetchall()
        ]
