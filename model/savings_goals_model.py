"""Sparziele-Datenmodell.

Ein Sparziel ist ein Flussbestand:

* Zielbetrag / Einzahlungsziel
* kumuliert eingezahlt (Korrekturen verändern diesen Wert)
* kumuliert bezogen / verwendet
* aktueller Bestand = Einzahlungen - Bezüge
* noch einzuzahlen = Zielbetrag - Einzahlungen
* Teilfreigaben reservieren einen Teil des Bestands zur Verwendung, ohne das
  Sparziel zu beenden.
"""

from __future__ import annotations

import logging
import math
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from model.crypto import suspend_after_commit_autosave
from model.typ_constants import TYP_SAVINGS
from model.undo_redo_model import UndoRedoModel

logger = logging.getLogger(__name__)

STATUS_SAVING = "sparend"
STATUS_RELEASED = "freigegeben"  # Legacy-Status; neue UI nutzt Teilfreigaben.
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

ACTION_DEPOSIT = "deposit"
ACTION_WITHDRAWAL = "withdrawal"
ACTION_CORRECTION = "correction"
VALID_SAVINGS_ACTIONS = {ACTION_DEPOSIT, ACTION_WITHDRAWAL, ACTION_CORRECTION}

_EPSILON_AMOUNT = 0.005


class SavingsGoalBoundsError(ValueError):
    """Fachlicher Fehler: Sparziel-Fluss würde seine Grenzen verlassen."""

    def __init__(self, message_key: str, **params: object):
        super().__init__(message_key)
        self.message_key = message_key
        self.params = params


def _finite_or_error(goal_name: str, **values: float) -> None:
    for value in values.values():
        if not math.isfinite(float(value)):
            raise SavingsGoalBoundsError(
                "savings.bounds.not_finite",
                goal_name=goal_name,
                current_amount=0.0,
                target_amount=0.0,
                attempted_amount=0.0,
                resulting_amount=0.0,
                max_allowed=0.0,
            )


def validate_savings_goal_bounds(
    *,
    goal_name: str,
    target_amount: float,
    current_amount: float,
    resulting_amount: float,
    delta_amount: float = 0.0,
) -> None:
    """Kompatible Standprüfung: ``0 <= neuer Stand <= Zielbetrag``.

    Diese API bleibt für ältere Aufrufer und Tests erhalten. Neue Buchungspfade
    verwenden :func:`validate_savings_goal_flow_bounds`, weil ein Bezug den
    Einzahlungsfortschritt nicht wieder zurücksetzt.
    """

    target = float(target_amount or 0.0)
    current = float(current_amount or 0.0)
    result = float(resulting_amount or 0.0)
    delta = float(delta_amount or 0.0)
    _finite_or_error(
        goal_name,
        target=target,
        current=current,
        result=result,
        delta=delta,
    )

    if result < -_EPSILON_AMOUNT:
        raise SavingsGoalBoundsError(
            "savings.bounds.withdraw_too_much",
            goal_name=goal_name,
            current_amount=current,
            target_amount=target,
            attempted_amount=abs(delta),
            resulting_amount=result,
            max_allowed=max(0.0, current),
        )
    if result - target > _EPSILON_AMOUNT:
        raise SavingsGoalBoundsError(
            "savings.bounds.deposit_too_much",
            goal_name=goal_name,
            current_amount=current,
            target_amount=target,
            attempted_amount=abs(delta),
            resulting_amount=result,
            max_allowed=max(0.0, target - current),
        )


def validate_savings_goal_flow_bounds(
    *,
    goal_name: str,
    target_amount: float,
    current_stock: float,
    contributed_amount: float,
    stock_delta: float,
    contribution_delta: float,
) -> None:
    """Validiert Bestand und Einzahlungsziel getrennt.

    Bezüge verändern nur den Bestand. Einzahlungen und Korrekturen verändern
    sowohl Bestand als auch den kumulierten Einzahlungsfortschritt.
    """

    target = float(target_amount or 0.0)
    stock = float(current_stock or 0.0)
    contributed = float(contributed_amount or 0.0)
    stock_result = stock + float(stock_delta or 0.0)
    contribution_result = contributed + float(contribution_delta or 0.0)
    _finite_or_error(
        goal_name,
        target=target,
        stock=stock,
        contributed=contributed,
        stock_result=stock_result,
        contribution_result=contribution_result,
    )

    if stock_result < -_EPSILON_AMOUNT:
        raise SavingsGoalBoundsError(
            "savings.bounds.withdraw_too_much",
            goal_name=goal_name,
            current_amount=stock,
            target_amount=target,
            attempted_amount=abs(float(stock_delta)),
            resulting_amount=stock_result,
            max_allowed=max(0.0, stock),
        )
    if contribution_result < -_EPSILON_AMOUNT:
        raise SavingsGoalBoundsError(
            "savings.bounds.correction_too_much",
            goal_name=goal_name,
            current_amount=contributed,
            target_amount=target,
            attempted_amount=abs(float(contribution_delta)),
            resulting_amount=contribution_result,
            max_allowed=max(0.0, contributed),
        )
    if contribution_result - target > _EPSILON_AMOUNT:
        raise SavingsGoalBoundsError(
            "savings.bounds.deposit_too_much",
            goal_name=goal_name,
            current_amount=contributed,
            target_amount=target,
            attempted_amount=abs(float(contribution_delta)),
            resulting_amount=contribution_result,
            max_allowed=max(0.0, target - contributed),
        )


@dataclass
class SavingsGoal:
    id: int
    name: str
    target_amount: float
    current_amount: float
    deadline: str | None
    category: str | None
    notes: str | None
    created_date: str
    status: str = STATUS_SAVING
    released_amount: float = 0.0
    released_date: str | None = None
    contributed_amount: float = 0.0
    withdrawn_amount: float = 0.0
    # Ob dieses Ziel an FPM gespiegelt wird. Vorgabe aus: Ein Sparziel traegt
    # Name, Betrag und Frist - das verlaesst den BudgetManager erst, wenn der
    # Nutzer es sagt.
    bridge_share: bool = False

    @property
    def effective_contributed_amount(self) -> float:
        """Kompatibler Einzahlungsstand für alte direkt erzeugte Objekte."""
        if (
            abs(self.contributed_amount) < _EPSILON_AMOUNT
            and abs(self.withdrawn_amount) < _EPSILON_AMOUNT
            and abs(self.current_amount) >= _EPSILON_AMOUNT
        ):
            return float(self.current_amount)
        return float(self.contributed_amount)

    @property
    def progress_percent(self) -> float:
        if self.target_amount <= 0:
            return 0.0
        return max(
            0.0,
            min(
                100.0, (self.effective_contributed_amount / self.target_amount) * 100.0
            ),
        )

    @property
    def remaining_amount(self) -> float:
        """Noch einzuzahlen (historischer Property-Name)."""
        return max(0.0, self.target_amount - self.effective_contributed_amount)

    @property
    def remaining_contribution(self) -> float:
        return self.remaining_amount

    @property
    def current_stock(self) -> float:
        return max(0.0, self.current_amount)

    @property
    def used_amount(self) -> float:
        return max(0.0, self.withdrawn_amount)

    @property
    def released_available(self) -> float:
        return max(0.0, self.released_amount - self.withdrawn_amount)

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
    _BASE_SELECT = (
        "id, name, target_amount, current_amount, deadline, category, notes, "
        "created_date, status, released_amount, released_date"
    )

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.undo = UndoRedoModel(conn)
        self._goal_columns = {
            str(row[1]) for row in self.conn.execute("PRAGMA table_info(savings_goals)")
        }
        self._tracking_columns = {
            str(row[1]) for row in self.conn.execute("PRAGMA table_info(tracking)")
        }

    @property
    def _has_flow_columns(self) -> bool:
        return {"contributed_amount", "withdrawn_amount"}.issubset(self._goal_columns)

    @property
    def _has_action_column(self) -> bool:
        return "savings_action" in self._tracking_columns

    @property
    def _has_bridge_column(self) -> bool:
        return "bridge_share" in self._goal_columns

    def _select_sql(self) -> str:
        # Alle Varianten sind vollständig statische SQL-Literale. Das hält die
        # Abfrage auditierbar und verhindert, dass Spaltennamen aus externen
        # Eingaben in SQL gelangen können.
        # Der Ausdruck bleibt bewusst *im* return: Das Release-Audit erkennt
        # eine Methode nur dann als literal, wenn jeder Rueckgabeausdruck aus
        # Literalen, Ternaeren und Verkettung besteht. Ueber eine Zwischen-
        # variable gefuehrt, gilt jede Abfrage darauf als dynamisches SQL.
        #
        # Zum zweiten Teil: Vor v19 gab es die Spalte nicht; "1" statt "0" als
        # Ersatz, damit eine aeltere Datenbank sich wie frueher verhaelt und
        # alles spiegelt, statt die Bruecke wortlos leerzuraeumen.
        return (
            "id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date, "
            "contributed_amount, withdrawn_amount"
            if self._has_flow_columns
            else "id, name, target_amount, current_amount, deadline, category, notes, "
            "created_date, status, released_amount, released_date, "
            "current_amount AS contributed_amount, 0 AS withdrawn_amount"
        ) + (", bridge_share" if self._has_bridge_column else ", 1 AS bridge_share")

    def _snapshot(self, goal_id: int):
        return self.conn.execute(
            f"SELECT {self._select_sql()} FROM savings_goals WHERE id=?",  # nosec B608
            (goal_id,),
        ).fetchone()

    def _row_to_goal(self, row) -> SavingsGoal:
        return SavingsGoal(
            id=int(row[0]),
            name=str(row[1]),
            target_amount=float(row[2] or 0.0),
            current_amount=float(row[3] or 0.0),
            deadline=row[4],
            category=row[5],
            notes=row[6],
            created_date=str(row[7]),
            status=str(row[8] or STATUS_SAVING),
            released_amount=float(row[9] or 0.0),
            released_date=row[10],
            contributed_amount=float(row[11] or 0.0),
            withdrawn_amount=float(row[12] or 0.0),
            bridge_share=bool(row[13]),
        )

    def create(
        self,
        name: str,
        target_amount: float,
        current_amount: float = 0,
        deadline: str | None = None,
        category: str | None = None,
        notes: str | None = None,
    ) -> int:
        validate_savings_goal_flow_bounds(
            goal_name=name,
            target_amount=target_amount,
            current_stock=0.0,
            contributed_amount=0.0,
            stock_delta=current_amount,
            contribution_delta=current_amount,
        )
        created = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        if self._has_flow_columns:
            cur = self.conn.execute(
                """
                INSERT INTO savings_goals
                (name, target_amount, current_amount, deadline, category, notes,
                 created_date, status, released_amount, released_date,
                 contributed_amount, withdrawn_amount)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, 0)
                """,
                (
                    name,
                    float(target_amount),
                    float(current_amount),
                    deadline,
                    category,
                    notes,
                    created,
                    STATUS_SAVING,
                    float(current_amount),
                ),
            )
        else:
            cur = self.conn.execute(
                """
                INSERT INTO savings_goals
                (name, target_amount, current_amount, deadline, category, notes,
                 created_date, status, released_amount, released_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, NULL)
                """,
                (
                    name,
                    float(target_amount),
                    float(current_amount),
                    deadline,
                    category,
                    notes,
                    created,
                    STATUS_SAVING,
                ),
            )
        self.conn.commit()
        goal_id = int(cur.lastrowid)
        try:
            row = self._snapshot(goal_id)
            if row:
                self.undo.record_operation("savings_goals", "INSERT", None, dict(row))
        except Exception as exc:
            logger.debug("savings_goals create undo: %s", exc)
        return goal_id

    def list_all(self) -> list[SavingsGoal]:
        cur = self.conn.execute(
            f"""
            SELECT {self._select_sql()}
            FROM savings_goals
            ORDER BY
                CASE status
                    WHEN 'sparend' THEN 0
                    WHEN 'freigegeben' THEN 1
                    WHEN 'abgeschlossen' THEN 2
                    ELSE 3
                END,
                deadline IS NULL, deadline, name
            """  # nosec B608
        )
        return [self._row_to_goal(row) for row in cur.fetchall()]

    def get(self, goal_id: int) -> SavingsGoal | None:
        row = self._snapshot(goal_id)
        return self._row_to_goal(row) if row else None

    def get_by_category(self, category: str) -> SavingsGoal | None:
        row = self.conn.execute(
            f"""
            SELECT {self._select_sql()}
            FROM savings_goals
            WHERE category=? AND status IN (?, ?)
            ORDER BY id LIMIT 1
            """,  # nosec B608
            (category, STATUS_SAVING, STATUS_RELEASED),
        ).fetchone()
        return self._row_to_goal(row) if row else None

    def update(
        self,
        goal_id: int,
        name: str | None = None,
        target_amount: float | None = None,
        current_amount: float | None = None,
        deadline: str | None = None,
        category: str | None = None,
        notes: str | None = None,
    ) -> None:
        old_goal = self.get(goal_id)
        old_row = self._snapshot(goal_id)
        if not old_goal:
            return

        next_name = name if name is not None else old_goal.name
        next_target = (
            float(target_amount)
            if target_amount is not None
            else old_goal.target_amount
        )
        # Das historisch ``current_amount`` genannte Edit-Feld ist ab v18 der
        # kumulierte Einzahlungsstand. Der Bestand wird daraus abzüglich Bezüge
        # rekonstruiert, damit eine Verwendung nicht plötzlich verschwindet.
        next_contributed = (
            float(current_amount)
            if current_amount is not None
            else old_goal.contributed_amount
        )
        next_stock = next_contributed - old_goal.withdrawn_amount
        validate_savings_goal_flow_bounds(
            goal_name=str(next_name),
            target_amount=next_target,
            current_stock=old_goal.current_amount,
            contributed_amount=old_goal.contributed_amount,
            stock_delta=next_stock - old_goal.current_amount,
            contribution_delta=next_contributed - old_goal.contributed_amount,
        )

        updates: list[str] = []
        params: list[object] = []
        for column, value in (
            ("name", name),
            ("target_amount", target_amount),
            ("deadline", deadline),
            ("category", category),
            ("notes", notes),
        ):
            if value is not None:
                updates.append(f"{column}=?")
                params.append(value)
        if current_amount is not None:
            updates.append("current_amount=?")
            params.append(next_stock)
            if self._has_flow_columns:
                updates.append("contributed_amount=?")
                params.append(next_contributed)

        if not updates:
            return
        params.append(goal_id)
        self.conn.execute(
            f"UPDATE savings_goals SET {', '.join(updates)} WHERE id=?",  # nosec B608
            params,
        )
        self.conn.commit()
        try:
            new_row = self._snapshot(goal_id)
            if old_row and new_row:
                self.undo.record_operation(
                    "savings_goals", "UPDATE", dict(old_row), dict(new_row)
                )
        except Exception as exc:
            logger.debug("savings_goals update undo: %s", exc)

    def add_progress(self, goal_id: int, amount: float) -> None:
        """Manuelle Einzahlung bzw. Korrektur, niemals ein Bezug.

        Positive Werte erhöhen die Einzahlungen. Negative Werte korrigieren eine
        Fehlbuchung und werden deshalb nicht als Verwendung ausgewiesen.
        """
        goal = self.get(goal_id)
        if not goal:
            return
        delta = float(amount)
        validate_savings_goal_flow_bounds(
            goal_name=goal.name,
            target_amount=goal.target_amount,
            current_stock=goal.current_amount,
            contributed_amount=goal.contributed_amount,
            stock_delta=delta,
            contribution_delta=delta,
        )
        if self._has_flow_columns:
            self.conn.execute(
                """
                UPDATE savings_goals
                SET current_amount=current_amount+?,
                    contributed_amount=contributed_amount+?
                WHERE id=?
                """,
                (delta, delta, goal_id),
            )
        else:
            self.conn.execute(
                "UPDATE savings_goals SET current_amount=current_amount+? WHERE id=?",
                (delta, goal_id),
            )
        self.conn.commit()

    def set_bridge_share(self, goal_id: int, geteilt: bool) -> None:
        """Gibt ein Sparziel fuer die FPM-Bruecke frei oder nimmt es zurueck.

        Das Zuruecknehmen wirkt erst beim naechsten Schreiben der Brueckendatei
        - die ist eine Momentaufnahme und wird vollstaendig ersetzt. Wer es
        sofort will, benutzt "Jetzt senden" im Freigabe-Dialog.
        """
        if not self._has_bridge_column:
            return
        self.conn.execute(
            "UPDATE savings_goals SET bridge_share=? WHERE id=?",
            (int(geteilt), goal_id),
        )
        self.conn.commit()

    def delete(self, goal_id: int) -> None:
        old_row = self._snapshot(goal_id)
        self.conn.execute("DELETE FROM savings_goals WHERE id=?", (goal_id,))
        self.conn.commit()
        try:
            if old_row:
                self.undo.record_operation(
                    "savings_goals", "DELETE", dict(old_row), None
                )
        except Exception as exc:
            logger.debug("savings_goals delete undo: %s", exc)

    def release_partial(self, goal_id: int, amount: float) -> SavingsGoal | None:
        """Gibt einen Teilbetrag frei, ohne das Ziel zu beenden."""
        goal = self.get(goal_id)
        if not goal or goal.is_completed:
            return goal
        value = float(amount)
        _finite_or_error(goal.name, amount=value)
        if value <= _EPSILON_AMOUNT:
            raise SavingsGoalBoundsError(
                "savings.bounds.release_positive",
                goal_name=goal.name,
                current_amount=goal.current_stock,
                target_amount=goal.target_amount,
                attempted_amount=value,
                resulting_amount=goal.released_available,
                max_allowed=max(0.0, goal.current_stock - goal.released_available),
            )
        max_additional = max(0.0, goal.current_stock - goal.released_available)
        if value - max_additional > _EPSILON_AMOUNT:
            raise SavingsGoalBoundsError(
                "savings.bounds.release_too_much",
                goal_name=goal.name,
                current_amount=goal.current_stock,
                target_amount=goal.target_amount,
                attempted_amount=value,
                resulting_amount=goal.released_available + value,
                max_allowed=max_additional,
            )
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        # Bereits erfolgte Bezüge gelten als verbrauchte Freigabe. Bei der
        # ersten späteren Teilfreigabe wird deshalb mindestens auf den bisher
        # verwendeten Betrag aufgesetzt, damit der neue Teilbetrag tatsächlich
        # als verfügbar erscheint.
        baseline = max(goal.released_amount, goal.withdrawn_amount)
        self.conn.execute(
            """
            UPDATE savings_goals
            SET released_amount=?, released_date=?
            WHERE id=?
            """,
            (baseline + value, now, goal_id),
        )
        self.conn.commit()
        return self.get(goal_id)

    def release(self, goal_id: int) -> SavingsGoal | None:
        """Legacy-Vollfreigabe für alte Aufrufer.

        Die neue Oberfläche verwendet :meth:`release_partial`, wodurch das Ziel
        im Status ``sparend`` bleibt.
        """
        goal = self.get(goal_id)
        if not goal:
            return None
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.conn.execute(
            """
            UPDATE savings_goals
            SET status=?, released_amount=current_amount, released_date=?
            WHERE id=?
            """,
            (STATUS_RELEASED, now, goal_id),
        )
        self.conn.commit()
        return self.get(goal_id)

    def complete(self, goal_id: int) -> SavingsGoal | None:
        if not self.get(goal_id):
            return None
        self.conn.execute(
            "UPDATE savings_goals SET status=? WHERE id=?",
            (STATUS_COMPLETED, goal_id),
        )
        self.conn.commit()
        return self.get(goal_id)

    def reopen(self, goal_id: int) -> SavingsGoal | None:
        if not self.get(goal_id):
            return None
        # Freigabehistorie bleibt erhalten; nur der Lebenszyklus wird geöffnet.
        self.conn.execute(
            "UPDATE savings_goals SET status=? WHERE id=?",
            (STATUS_SAVING, goal_id),
        )
        self.conn.commit()
        return self.get(goal_id)

    def get_spent_amount(self, goal_id: int) -> float:
        goal = self.get(goal_id)
        if not goal:
            return 0.0
        if self._has_flow_columns:
            return goal.withdrawn_amount
        if not goal.category:
            return 0.0
        action_filter = (
            "AND COALESCE(NULLIF(savings_action,''), 'withdrawal')='withdrawal'"
            if self._has_action_column
            else ""
        )
        row = self.conn.execute(
            f"""
            SELECT COALESCE(SUM(ABS(amount)),0)
            FROM tracking
            WHERE typ=? AND category=? AND amount<0 {action_filter}
            """,  # nosec B608
            (TYP_SAVINGS, goal.category),
        ).fetchone()
        return float(row[0] or 0.0) if row else 0.0

    def get_added_since_release(self, goal_id: int) -> float:
        goal = self.get(goal_id)
        if not goal or not goal.category or not goal.released_date:
            return 0.0
        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount),0)
            FROM tracking
            WHERE typ=? AND category=? AND amount>0 AND date>=?
            """,
            (TYP_SAVINGS, goal.category, goal.released_date[:10]),
        ).fetchone()
        return float(row[0] or 0.0) if row else 0.0

    def _tracking_totals(self, category: str) -> tuple[float, float, float]:
        if self._has_action_column:
            action = (
                "COALESCE(NULLIF(savings_action,''), "
                "CASE WHEN amount<0 THEN 'withdrawal' ELSE 'deposit' END)"
            )
            row = self.conn.execute(
                f"""
                SELECT
                    COALESCE(SUM(amount),0) AS stock,
                    COALESCE(SUM(CASE WHEN {action}='withdrawal' THEN 0 ELSE amount END),0)
                        AS contributed,
                    COALESCE(SUM(CASE WHEN {action}='withdrawal' THEN ABS(amount) ELSE 0 END),0)
                        AS withdrawn
                FROM tracking WHERE typ=? AND category=?
                """,  # nosec B608
                (TYP_SAVINGS, category),
            ).fetchone()
            return tuple(float(value or 0.0) for value in row[:3])  # type: ignore[return-value]

        row = self.conn.execute(
            """
            SELECT COALESCE(SUM(amount),0),
                   COALESCE(SUM(CASE WHEN amount>0 THEN amount ELSE 0 END),0),
                   COALESCE(SUM(CASE WHEN amount<0 THEN ABS(amount) ELSE 0 END),0)
            FROM tracking WHERE typ=? AND category=?
            """,
            (TYP_SAVINGS, category),
        ).fetchone()
        return tuple(float(value or 0.0) for value in row[:3])  # type: ignore[return-value]

    def sync_with_tracking(self, goal_id: int) -> float:
        goal = self.get(goal_id)
        if not goal or not goal.category:
            return 0.0
        if goal.is_completed:
            return goal.current_amount
        stock, contributed, withdrawn = self._tracking_totals(goal.category)
        validate_savings_goal_flow_bounds(
            goal_name=goal.name,
            target_amount=goal.target_amount,
            current_stock=0.0,
            contributed_amount=0.0,
            stock_delta=stock,
            contribution_delta=contributed,
        )
        if self._has_flow_columns:
            self.conn.execute(
                """
                UPDATE savings_goals
                SET current_amount=?, contributed_amount=?, withdrawn_amount=?
                WHERE id=?
                """,
                (stock, contributed, withdrawn, goal_id),
            )
        else:
            self.conn.execute(
                "UPDATE savings_goals SET current_amount=? WHERE id=?",
                (stock, goal_id),
            )
        self.conn.commit()
        return stock

    def recalculate_all(self) -> None:
        with suspend_after_commit_autosave(self.conn):
            for goal in self.list_all():
                if goal.category and not goal.is_completed:
                    self.sync_with_tracking(goal.id)

    def has_active_goal_for_category(self, category: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM savings_goals
            WHERE category=? AND status IN (?, ?) LIMIT 1
            """,
            (category, STATUS_SAVING, STATUS_RELEASED),
        ).fetchone()
        return row is not None

    def has_released_goal_for_category(self, category: str) -> bool:
        row = self.conn.execute(
            """
            SELECT 1 FROM savings_goals
            WHERE category=? AND (status=? OR COALESCE(released_amount,0)>0) LIMIT 1
            """,
            (category, STATUS_RELEASED),
        ).fetchone()
        return row is not None
