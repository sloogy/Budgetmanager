from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from typing import List, Optional

@dataclass
class SavingsGoal:
    id: int
    name: str
    target_amount: float
    current_amount: float
    deadline: Optional[str]
    category: Optional[str]
    notes: Optional[str]
    created_date: str

    @property
    def progress_percent(self) -> float:
        if self.target_amount <= 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)

    @property
    def remaining_amount(self) -> float:
        return max(0, self.target_amount - self.current_amount)

class SavingsGoalsModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, name: str, target_amount: float, current_amount: float = 0,
               deadline: Optional[str] = None, category: Optional[str] = None,
               notes: Optional[str] = None) -> int:
        """Erstellt ein neues Sparziel"""
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.execute(
            """
            INSERT INTO savings_goals 
            (name, target_amount, current_amount, deadline, category, notes, created_date)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (name, target_amount, current_amount, deadline, category, notes, created)
        )
        self.conn.commit()
        return cur.lastrowid

    def list_all(self) -> List[SavingsGoal]:
        """Liste alle Sparziele"""
        cur = self.conn.execute(
            """
            SELECT id, name, target_amount, current_amount, deadline, category, notes, created_date
            FROM savings_goals
            ORDER BY deadline IS NULL, deadline, name
            """
        )
        return [
            SavingsGoal(
                id=row[0],
                name=row[1],
                target_amount=float(row[2]),
                current_amount=float(row[3]),
                deadline=row[4],
                category=row[5],
                notes=row[6],
                created_date=row[7]
            )
            for row in cur.fetchall()
        ]

    def get(self, goal_id: int) -> Optional[SavingsGoal]:
        """Gibt ein Sparziel zurück"""
        cur = self.conn.execute(
            """
            SELECT id, name, target_amount, current_amount, deadline, category, notes, created_date
            FROM savings_goals
            WHERE id = ?
            """,
            (goal_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return SavingsGoal(
            id=row[0],
            name=row[1],
            target_amount=float(row[2]),
            current_amount=float(row[3]),
            deadline=row[4],
            category=row[5],
            notes=row[6],
            created_date=row[7]
        )

    def update(self, goal_id: int, name: Optional[str] = None, 
               target_amount: Optional[float] = None,
               current_amount: Optional[float] = None,
               deadline: Optional[str] = None,
               category: Optional[str] = None,
               notes: Optional[str] = None) -> None:
        """Aktualisiert ein Sparziel"""
        updates = []
        params = []
        
        if name is not None:
            updates.append("name = ?")
            params.append(name)
        if target_amount is not None:
            updates.append("target_amount = ?")
            params.append(target_amount)
        if current_amount is not None:
            updates.append("current_amount = ?")
            params.append(current_amount)
        if deadline is not None:
            updates.append("deadline = ?")
            params.append(deadline)
        if category is not None:
            updates.append("category = ?")
            params.append(category)
        if notes is not None:
            updates.append("notes = ?")
            params.append(notes)
        
        if updates:
            params.append(goal_id)
            query = f"UPDATE savings_goals SET {', '.join(updates)} WHERE id = ?"
            self.conn.execute(query, params)
            self.conn.commit()

    def add_progress(self, goal_id: int, amount: float) -> None:
        """Fügt Fortschritt zu einem Sparziel hinzu"""
        self.conn.execute(
            "UPDATE savings_goals SET current_amount = current_amount + ? WHERE id = ?",
            (amount, goal_id)
        )
        self.conn.commit()

    def delete(self, goal_id: int) -> None:
        """Löscht ein Sparziel"""
        self.conn.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
        self.conn.commit()
    
    def sync_with_tracking(self, goal_id: int) -> float:
        """
        Synchronisiert ein Sparziel mit allen Tracking-Buchungen der verknüpften Kategorie.
        Berechnet den aktuellen Stand neu basierend auf allen Ersparnisse-Buchungen.
        
        Returns: Neuer current_amount Wert
        """
        goal = self.get(goal_id)
        if not goal or not goal.category:
            return 0.0
        
        # Alle Ersparnisse-Buchungen für diese Kategorie summieren
        cur = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0) as total
            FROM tracking
            WHERE typ = 'Ersparnisse' AND category = ?
            """,
            (goal.category,)
        )
        total = float(cur.fetchone()[0])
        
        # Sparziel aktualisieren
        self.conn.execute(
            "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
            (total, goal_id)
        )
        self.conn.commit()
        
        return total
    
    def recalculate_all(self) -> None:
        """
        Berechnet alle Sparziele neu, die eine Kategorie verknüpft haben.
        Nützlich nach Datenimport oder zur Fehlerkorrektur.
        """
        goals = self.list_all()
        for goal in goals:
            if goal.category:
                self.sync_with_tracking(goal.id)
