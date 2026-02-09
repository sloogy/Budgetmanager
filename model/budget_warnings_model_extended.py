from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Tuple, Optional
from datetime import date, timedelta
from collections import defaultdict

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

    def create(self, year: int, month: int, typ: str, category: str, 
               threshold_percent: int = 90) -> int:
        """Erstellt eine Budget-Warnung"""
        try:
            cur = self.conn.execute(
                """
                INSERT INTO budget_warnings 
                (year, month, typ, category, threshold_percent, enabled)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (year, month, typ, category, threshold_percent)
            )
            self.conn.commit()
            return cur.lastrowid
        except sqlite3.IntegrityError:
            return 0  # bereits vorhanden

    def update(self, warning_id: int, threshold_percent: int | None = None,
               enabled: bool | None = None) -> None:
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

    def get_warnings(self, year: int, month: int, typ: str | None = None) -> List[BudgetWarning]:
        """Gibt alle Warnungen für Jahr/Monat zurück"""
        if typ:
            cur = self.conn.execute(
                """
                SELECT id, year, month, typ, category, threshold_percent, enabled
                FROM budget_warnings
                WHERE year = ? AND month = ? AND typ = ? AND enabled = 1
                """,
                (year, month, typ)
            )
        else:
            cur = self.conn.execute(
                """
                SELECT id, year, month, typ, category, threshold_percent, enabled
                FROM budget_warnings
                WHERE year = ? AND month = ? AND enabled = 1
                """,
                (year, month)
            )
        
        return [
            BudgetWarning(
                id=row[0],
                year=row[1],
                month=row[2],
                typ=row[3],
                category=row[4],
                threshold_percent=row[5],
                enabled=bool(row[6])
            )
            for row in cur.fetchall()
        ]

    def check_warnings_extended(self, year: int, month: int, lookback_months: int = 3) -> List[BudgetExceedance]:
        """
        Prüft alle Warnungen und gibt überschrittene zurück mit erweiterten Infos
        
        Args:
            year: Jahr
            month: Monat
            lookback_months: Wie viele Monate zurückschauen für Überschreitungshistorie
            
        Returns:
            Liste von BudgetExceedance-Objekten mit Vorschlägen
        """
        warnings = self.get_warnings(year, month)
        exceeded = []
        
        for warn in warnings:
            # Budget abrufen
            cur = self.conn.execute(
                """
                SELECT amount FROM budget
                WHERE year = ? AND month = ? AND typ = ? AND category = ?
                """,
                (year, month, warn.typ, warn.category)
            )
            budget_row = cur.fetchone()
            if not budget_row or budget_row[0] <= 0:
                continue
            budget = float(budget_row[0])
            
            # Ausgaben abrufen (nur für den Monat)
            start_date = f"{year:04d}-{month:02d}-01"
            if month == 12:
                end_date = f"{year+1:04d}-01-01"
            else:
                end_date = f"{year:04d}-{month+1:02d}-01"
            
            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start_date, end_date, warn.typ, warn.category)
            )
            spent = float(cur.fetchone()[0])
            
            # Prüfen ob Schwellenwert überschritten
            if budget > 0:
                percent_used = (spent / budget) * 100
                if percent_used >= warn.threshold_percent:
                    # Überschreitungshistorie und Vorschlag berechnen
                    exceed_count = self._get_exceed_count(
                        warn.typ, warn.category, year, month, lookback_months
                    )
                    suggestion = self._calculate_budget_suggestion(
                        warn.typ, warn.category, year, month, budget, spent, lookback_months
                    )
                    
                    exceeded.append(BudgetExceedance(
                        typ=warn.typ,
                        category=warn.category,
                        year=year,
                        month=month,
                        budget=budget,
                        spent=spent,
                        threshold_percent=warn.threshold_percent,
                        percent_used=percent_used,
                        suggestion=suggestion,
                        exceed_count=exceed_count
                    ))
        
        return exceeded

    def _get_exceed_count(self, typ: str, category: str, year: int, month: int, 
                          lookback_months: int) -> int:
        """
        Zählt wie oft das Budget in den letzten N Monaten überschritten wurde
        """
        count = 0
        current_date = date(year, month, 1)
        
        for i in range(lookback_months):
            check_date = self._subtract_months(current_date, i)
            check_year = check_date.year
            check_month = check_date.month
            
            # Budget holen
            cur = self.conn.execute(
                "SELECT amount FROM budget WHERE year = ? AND month = ? AND typ = ? AND category = ?",
                (check_year, check_month, typ, category)
            )
            budget_row = cur.fetchone()
            if not budget_row or budget_row[0] <= 0:
                continue
            budget = float(budget_row[0])
            
            # Ausgaben holen
            start = f"{check_year:04d}-{check_month:02d}-01"
            if check_month == 12:
                end = f"{check_year+1:04d}-01-01"
            else:
                end = f"{check_year:04d}-{check_month+1:02d}-01"
            
            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start, end, typ, category)
            )
            spent = float(cur.fetchone()[0])
            
            if spent >= budget:
                count += 1
        
        return count

    def _calculate_budget_suggestion(self, typ: str, category: str, year: int, month: int,
                                     current_budget: float, current_spent: float,
                                     lookback_months: int) -> float:
        """
        Berechnet einen Budgetvorschlag basierend auf historischen Ausgaben
        
        Strategie:
        - Durchschnitt der letzten N Monate
        - Gewichtung: Neuere Monate stärker gewichten
        - Sicherheitspuffer von 10%
        """
        spending_history = []
        current_date = date(year, month, 1)
        
        # Sammle Ausgaben der letzten Monate
        for i in range(lookback_months):
            check_date = self._subtract_months(current_date, i)
            check_year = check_date.year
            check_month = check_date.month
            
            start = f"{check_year:04d}-{check_month:02d}-01"
            if check_month == 12:
                end = f"{check_year+1:04d}-01-01"
            else:
                end = f"{check_year:04d}-{check_month+1:02d}-01"
            
            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start, end, typ, category)
            )
            spent = float(cur.fetchone()[0])
            
            if spent > 0:
                # Gewichtung: Neuere Monate = höheres Gewicht
                weight = (lookback_months - i) / lookback_months
                spending_history.append((spent, weight))
        
        if not spending_history:
            # Kein Verlauf, verwende aktuell + 20%
            return round(current_spent * 1.2, 2)
        
        # Gewichteter Durchschnitt
        weighted_sum = sum(spent * weight for spent, weight in spending_history)
        total_weight = sum(weight for _, weight in spending_history)
        avg_spending = weighted_sum / total_weight if total_weight > 0 else current_spent
        
        # 10% Sicherheitspuffer
        suggested_budget = avg_spending * 1.1
        
        # Auf 10er-Stellen runden für praktischere Werte
        return round(suggested_budget / 10) * 10

    def _subtract_months(self, start_date: date, months: int) -> date:
        """Subtrahiert N Monate von einem Datum"""
        month = start_date.month - months
        year = start_date.year
        
        while month < 1:
            month += 12
            year -= 1
        
        return date(year, month, 1)

    def apply_budget_suggestion(self, typ: str, category: str, year: int, month: int, 
                                new_budget: float) -> None:
        """Wendet den Budget-Vorschlag an"""
        self.conn.execute(
            """
            INSERT OR REPLACE INTO budget (year, month, typ, category, amount)
            VALUES (?, ?, ?, ?, ?)
            """,
            (year, month, typ, category, new_budget)
        )
        self.conn.commit()

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
        
        for i in range(months):
            check_date = self._subtract_months(today, i)
            check_year = check_date.year
            check_month = check_date.month
            
            # Budget holen
            cur = self.conn.execute(
                "SELECT amount FROM budget WHERE year = ? AND month = ? AND typ = ? AND category = ?",
                (check_year, check_month, typ, category)
            )
            budget_row = cur.fetchone()
            if not budget_row or budget_row[0] <= 0:
                continue
            budget = float(budget_row[0])
            
            # Ausgaben holen
            start = f"{check_year:04d}-{check_month:02d}-01"
            if check_month == 12:
                end = f"{check_year+1:04d}-01-01"
            else:
                end = f"{check_year:04d}-{check_month+1:02d}-01"
            
            cur = self.conn.execute(
                """
                SELECT COALESCE(SUM(amount), 0) FROM tracking
                WHERE date >= ? AND date < ? AND typ = ? AND category = ?
                """,
                (start, end, typ, category)
            )
            spent = float(cur.fetchone()[0])
            
            if spent > budget:
                times_exceeded += 1
                overspend_percent = ((spent - budget) / budget) * 100
                overspend_percents.append(overspend_percent)
        
        suggestion = self._calculate_budget_suggestion(
            typ, category, today.year, today.month, 0, 0, months
        )
        
        return {
            'months_checked': months,
            'times_exceeded': times_exceeded,
            'avg_overspend_percent': sum(overspend_percents) / len(overspend_percents) if overspend_percents else 0,
            'max_overspend_percent': max(overspend_percents) if overspend_percents else 0,
            'suggestion': suggestion
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
                enabled=bool(row[6])
            )
            for row in cur.fetchall()
        ]
