from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import List, Dict, Tuple

@dataclass
class BudgetWarning:
    id: int
    year: int
    month: int
    typ: str
    category: str
    threshold_percent: int
    enabled: bool

class BudgetWarningsModel:
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

    def check_warnings(self, year: int, month: int) -> List[Tuple[str, str, float, float, int]]:
        """
        Prüft alle Warnungen und gibt überschrittene zurück
        Returns: List[(typ, category, budget, spent, threshold_percent)]
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
                    exceeded.append((warn.typ, warn.category, budget, spent, warn.threshold_percent))
        
        return exceeded

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
