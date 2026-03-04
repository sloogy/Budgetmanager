from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import sqlite3
from dataclasses import dataclass
from datetime import datetime, date
from typing import List, Optional

from model.undo_redo_model import UndoRedoModel
from model.database import db_transaction


"""Sparziele-Datenmodell.

Verwaltet Sparziele mit Lebenszyklusstatus (sparend, freigegeben, abgeschlossen),
Buchungsintegration und Fortschrittsberechnung.
"""

# ── Konstanten für Sparziel-Status ──
STATUS_SAVING = "sparend"
STATUS_RELEASED = "freigegeben"
STATUS_COMPLETED = "abgeschlossen"

STATUS_LABELS = {
    STATUS_SAVING: "Sparend",
    STATUS_RELEASED: "Freigegeben",
    STATUS_COMPLETED: "Abgeschlossen",
}

STATUS_ICONS = {
    STATUS_SAVING: "💰",
    STATUS_RELEASED: "🔓",
    STATUS_COMPLETED: "✅",
}


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
    # Lifecycle-Felder (v10)
    status: str = STATUS_SAVING
    released_amount: float = 0.0
    released_date: Optional[str] = None

    @property
    def progress_percent(self) -> float:
        if self.target_amount <= 0:
            return 0
        return min(100, (self.current_amount / self.target_amount) * 100)

    @property
    def remaining_amount(self) -> float:
        return max(0, self.target_amount - self.current_amount)

    @property
    def is_saving(self) -> bool:
        return self.status == STATUS_SAVING

    @property
    def is_released(self) -> bool:
        return self.status == STATUS_RELEASED

    @property
    def is_completed(self) -> bool:
        return self.status == STATUS_COMPLETED

    @property
    def status_label(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def status_icon(self) -> str:
        return STATUS_ICONS.get(self.status, "")


class SavingsGoalsModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.undo = UndoRedoModel(conn)

    # ──────────────────────────────────────────────
    # CRUD
    # ──────────────────────────────────────────────
    def create(self, name: str, target_amount: float, current_amount: float = 0,
               deadline: Optional[str] = None, category: Optional[str] = None,
               notes: Optional[str] = None) -> int:
        """Erstellt ein neues Sparziel (Status: sparend)"""
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cur = self.conn.execute(
            """
            INSERT INTO savings_goals 
            (name, target_amount, current_amount, deadline, category, notes, created_date,
             status, released_amount, released_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
            """,
            (name, target_amount, current_amount, deadline, category, notes, created,
             STATUS_SAVING)
        )
        self.conn.commit()
        goal_id = cur.lastrowid
        # Undo-Tracking
        try:
            row = self.conn.execute(
                "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
                "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
                (goal_id,)
            ).fetchone()
            if row:
                self.undo.record_operation("savings_goals", "INSERT", None, dict(row))
        except Exception as e:
            logger.debug("savings_goals create undo: %s", e)
        return goal_id

    def _row_to_goal(self, row) -> SavingsGoal:
        """Konvertiert eine DB-Zeile in ein SavingsGoal-Objekt."""
        return SavingsGoal(
            id=row[0],
            name=row[1],
            target_amount=float(row[2]),
            current_amount=float(row[3]),
            deadline=row[4],
            category=row[5],
            notes=row[6],
            created_date=row[7],
            status=row[8] or STATUS_SAVING,
            released_amount=float(row[9] or 0),
            released_date=row[10],
        )

    def list_all(self) -> List[SavingsGoal]:
        """Liste alle Sparziele"""
        cur = self.conn.execute(
            """
            SELECT id, name, target_amount, current_amount, deadline, category, notes, 
                   created_date, status, released_amount, released_date
            FROM savings_goals
            ORDER BY 
                CASE status 
                    WHEN 'sparend' THEN 0 
                    WHEN 'freigegeben' THEN 1 
                    WHEN 'abgeschlossen' THEN 2 
                END,
                deadline IS NULL, deadline, name
            """
        )
        return [self._row_to_goal(row) for row in cur.fetchall()]

    def get(self, goal_id: int) -> Optional[SavingsGoal]:
        """Gibt ein Sparziel zurück"""
        cur = self.conn.execute(
            """
            SELECT id, name, target_amount, current_amount, deadline, category, notes, 
                   created_date, status, released_amount, released_date
            FROM savings_goals
            WHERE id = ?
            """,
            (goal_id,)
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_goal(row)

    def get_by_category(self, category: str) -> Optional[SavingsGoal]:
        """Gibt das aktive Sparziel für eine Kategorie zurück (sparend oder freigegeben)."""
        cur = self.conn.execute(
            """
            SELECT id, name, target_amount, current_amount, deadline, category, notes,
                   created_date, status, released_amount, released_date
            FROM savings_goals
            WHERE category = ? AND status IN (?, ?)
            LIMIT 1
            """,
            (category, STATUS_SAVING, STATUS_RELEASED)
        )
        row = cur.fetchone()
        if not row:
            return None
        return self._row_to_goal(row)

    def update(self, goal_id: int, name: Optional[str] = None, 
               target_amount: Optional[float] = None,
               current_amount: Optional[float] = None,
               deadline: Optional[str] = None,
               category: Optional[str] = None,
               notes: Optional[str] = None) -> None:
        """Aktualisiert ein Sparziel"""
        # Alte Werte für Undo
        old_row = self.conn.execute(
            "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
            (goal_id,)
        ).fetchone()

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
            # Undo-Tracking
            try:
                new_row = self.conn.execute(
                    "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
                    "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
                    (goal_id,)
                ).fetchone()
                if old_row and new_row:
                    self.undo.record_operation("savings_goals", "UPDATE", dict(old_row), dict(new_row))
            except Exception as e:
                logger.debug("savings_goals update undo: %s", e)

    def add_progress(self, goal_id: int, amount: float) -> None:
        """Fügt Fortschritt zu einem Sparziel hinzu"""
        self.conn.execute(
            "UPDATE savings_goals SET current_amount = current_amount + ? WHERE id = ?",
            (amount, goal_id)
        )
        self.conn.commit()

    def delete(self, goal_id: int) -> None:
        """Löscht ein Sparziel"""
        old_row = self.conn.execute(
            "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
            (goal_id,)
        ).fetchone()
        self.conn.execute("DELETE FROM savings_goals WHERE id = ?", (goal_id,))
        self.conn.commit()
        # Undo-Tracking
        try:
            if old_row:
                self.undo.record_operation("savings_goals", "DELETE", dict(old_row), None)
        except Exception as e:
            logger.debug("savings_goals delete undo: %s", e)

    # ──────────────────────────────────────────────
    # Lifecycle: Freigabe / Abschluss
    # ──────────────────────────────────────────────
    def release(self, goal_id: int) -> Optional[SavingsGoal]:
        """Gibt ein Sparziel frei: Status -> freigegeben."""
        goal = self.get(goal_id)
        if not goal:
            return None
        if goal.status != STATUS_SAVING:
            logger.warning("Sparziel %d ist nicht im Status 'sparend', kann nicht freigeben", goal_id)
            return goal

        old_row = self.conn.execute(
            "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
            (goal_id,)
        ).fetchone()

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            """
            UPDATE savings_goals 
            SET status = ?, released_amount = current_amount, released_date = ?
            WHERE id = ?
            """,
            (STATUS_RELEASED, now, goal_id)
        )
        self.conn.commit()
        # Undo-Tracking
        try:
            new_row = self.conn.execute(
                "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
                "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
                (goal_id,)
            ).fetchone()
            if old_row and new_row:
                self.undo.record_operation("savings_goals", "UPDATE", dict(old_row), dict(new_row))
        except Exception as e:
            logger.debug("savings_goals release undo: %s", e)
        return self.get(goal_id)

    def complete(self, goal_id: int) -> Optional[SavingsGoal]:
        """Schliesst ein Sparziel ab: Status -> abgeschlossen."""
        goal = self.get(goal_id)
        if not goal:
            return None

        old_row = self.conn.execute(
            "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
            (goal_id,)
        ).fetchone()

        self.conn.execute(
            "UPDATE savings_goals SET status = ? WHERE id = ?",
            (STATUS_COMPLETED, goal_id)
        )
        self.conn.commit()
        # Undo-Tracking
        try:
            new_row = self.conn.execute(
                "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
                "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
                (goal_id,)
            ).fetchone()
            if old_row and new_row:
                self.undo.record_operation("savings_goals", "UPDATE", dict(old_row), dict(new_row))
        except Exception as e:
            logger.debug("savings_goals complete undo: %s", e)
        return self.get(goal_id)

    def reopen(self, goal_id: int) -> Optional[SavingsGoal]:
        """Oeffnet ein abgeschlossenes/freigegebenes Sparziel wieder zum Sparen."""
        old_row = self.conn.execute(
            "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
            (goal_id,)
        ).fetchone()

        self.conn.execute(
            """
            UPDATE savings_goals 
            SET status = ?, released_amount = 0, released_date = NULL
            WHERE id = ?
            """,
            (STATUS_SAVING, goal_id)
        )
        self.conn.commit()
        # Undo-Tracking
        try:
            new_row = self.conn.execute(
                "SELECT id, name, target_amount, current_amount, deadline, category, notes, "
                "created_date, status, released_amount, released_date FROM savings_goals WHERE id=?",
                (goal_id,)
            ).fetchone()
            if old_row and new_row:
                self.undo.record_operation("savings_goals", "UPDATE", dict(old_row), dict(new_row))
        except Exception as e:
            logger.debug("savings_goals reopen undo: %s", e)
        return self.get(goal_id)

    # ──────────────────────────────────────────────
    # Verbrauchsberechnung (freigegebene Ziele)
    # ──────────────────────────────────────────────
    def get_spent_amount(self, goal_id: int) -> float:
        """Berechnet den Verbrauch seit Freigabe.

        Summiert alle NEGATIVEN Ersparnisse-Buchungen auf die Kategorie
        nach dem Freigabedatum.

        Returns:
            Positiver Betrag = so viel wurde bereits ausgegeben.
        """
        goal = self.get(goal_id)
        if not goal or not goal.category or not goal.released_date:
            return 0.0

        cur = self.conn.execute(
            """
            SELECT COALESCE(SUM(ABS(amount)), 0) 
            FROM tracking 
            WHERE typ = 'Ersparnisse' 
              AND category = ? 
              AND amount < 0 
              AND date >= ?
            """,
            (goal.category, goal.released_date[:10])
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    def get_added_since_release(self, goal_id: int) -> float:
        """Berechnet Nachsparen seit Freigabe (positive Buchungen)."""
        goal = self.get(goal_id)
        if not goal or not goal.category or not goal.released_date:
            return 0.0

        cur = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount), 0)
            FROM tracking
            WHERE typ = 'Ersparnisse'
              AND category = ?
              AND amount > 0
              AND date >= ?
            """,
            (goal.category, goal.released_date[:10])
        )
        row = cur.fetchone()
        return float(row[0]) if row and row[0] is not None else 0.0

    # ──────────────────────────────────────────────
    # Sync mit Tracking
    # ──────────────────────────────────────────────
    def sync_with_tracking(self, goal_id: int) -> float:
        """Synchronisiert ein Sparziel mit allen Tracking-Buchungen.
        
        Nur aktive Ziele (sparend/freigegeben) werden synchronisiert.
        Abgeschlossene Ziele haben ihren Stand eingefroren.
        """
        goal = self.get(goal_id)
        if not goal or not goal.category:
            return 0.0
        if goal.is_completed:
            # Abgeschlossene Ziele nicht neu synchronisieren
            return goal.current_amount

        cur = self.conn.execute(
            """SELECT COALESCE(SUM(amount), 0) FROM tracking
               WHERE typ = 'Ersparnisse' AND category = ?
               AND id IN (
                   SELECT et.entry_id FROM tracking t2
                   LEFT JOIN savings_goals sg ON sg.category = t2.category
                   WHERE t2.category = ?
               )
            """,
            (goal.category, goal.category)
        )
        # Vereinfachte korrekte Version: nur positive Buchungen (Einzahlungen) summieren,
        # nicht Buchungen anderer Ziele derselben Kategorie doppelt zählen.
        # Wir summieren ALLE Tracking-Buchungen der Kategorie (positiv = einzahlen, negativ = entnehmen).
        cur = self.conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM tracking WHERE typ = 'Ersparnisse' AND category = ?",
            (goal.category,)
        )
        row = cur.fetchone()
        total = float(row[0]) if row and row[0] is not None else 0.0
        
        self.conn.execute(
            "UPDATE savings_goals SET current_amount = ? WHERE id = ?",
            (total, goal_id)
        )
        self.conn.commit()
        return total
    
    def recalculate_all(self) -> None:
        """Berechnet alle Sparziele neu."""
        goals = self.list_all()
        for goal in goals:
            if goal.category:
                self.sync_with_tracking(goal.id)

    # ──────────────────────────────────────────────
    # Hilfsmethoden fuer Tracking-Integration
    # ──────────────────────────────────────────────
    def has_active_goal_for_category(self, category: str) -> bool:
        """Prueft ob ein aktives (sparend) Sparziel fuer die Kategorie existiert."""
        cur = self.conn.execute(
            "SELECT 1 FROM savings_goals WHERE category = ? AND status = ? LIMIT 1",
            (category, STATUS_SAVING)
        )
        return cur.fetchone() is not None

    def has_released_goal_for_category(self, category: str) -> bool:
        """Prueft ob ein freigegebenes Sparziel fuer die Kategorie existiert."""
        cur = self.conn.execute(
            "SELECT 1 FROM savings_goals WHERE category = ? AND status = ? LIMIT 1",
            (category, STATUS_RELEASED)
        )
        return cur.fetchone() is not None
