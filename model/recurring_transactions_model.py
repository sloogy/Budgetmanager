from __future__ import annotations

# Hinweis: Dieses Modell ist Legacy/Kompatibilitäts-Schicht.
# Der aktive App-Workflow für monatliche Fix-/Wiederholungsbuchungen läuft
# über Kategorien (`categories.is_fix`, `categories.is_recurring`,
# `categories.recurring_day`) und markiert Auto-Buchungen sprachunabhängig
# über die `tracking.source`-Spalte.
#
# Die frühere Per-Eintrag-Terminvorschau (`get_pending_bookings`,
# `_is_already_booked`, `update_last_booking_date`) wurde in v2.1.0 entfernt:
# Sie war produktiv nicht angebunden und ihre Dubletten-Erkennung hing am
# deutschsprachigen Marker `"Wiederkehrend (ID: …)"`, was der Live-Pfad
# bewusst nicht mehr nutzt. Es verbleiben die Tabellen-CRUD (für Backward-
# Compat der `recurring_transactions`-Tabelle) und die reinen Datums-Helfer.
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime


@dataclass
class RecurringTransaction:
    """Wiederkehrende Transaktion mit Soll-Buchungsdatum"""

    id: int | None
    typ: str  # 'Einkommen' oder 'Ausgaben'
    category: str
    amount: float
    details: str
    day_of_month: int  # Tag im Monat (1-31)
    is_active: bool
    start_date: date
    end_date: date | None
    created_date: datetime
    last_booking_date: date | None


class RecurringTransactionsModel:
    """Model für wiederkehrende Transaktionen"""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create_recurring_transaction(
        self,
        typ: str,
        category: str,
        amount: float,
        details: str,
        day_of_month: int,
        start_date: date,
        end_date: date | None = None,
        is_active: bool = True,
    ) -> int:
        """Erstellt eine neue wiederkehrende Transaktion"""
        cur = self.conn.execute(
            """
            INSERT INTO recurring_transactions 
            (typ, category, amount, details, day_of_month, is_active, 
             start_date, end_date, created_date, last_booking_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                typ,
                category,
                amount,
                details,
                day_of_month,
                1 if is_active else 0,
                start_date.isoformat(),
                end_date.isoformat() if end_date else None,
                datetime.now().isoformat(),
                None,
            ),
        )
        self.conn.commit()
        return cur.lastrowid

    def get_all_recurring_transactions(
        self, active_only: bool = False
    ) -> list[RecurringTransaction]:
        """Gibt alle wiederkehrenden Transaktionen zurück"""
        query = """
            SELECT id, typ, category, amount, details, day_of_month, 
                   is_active, start_date, end_date, created_date, last_booking_date
            FROM recurring_transactions
        """
        if active_only:
            query += " WHERE is_active = 1"
        query += " ORDER BY day_of_month, typ, category"

        rows = self.conn.execute(query).fetchall()
        return [self._row_to_transaction(row) for row in rows]

    def _calculate_booking_date(
        self, trans: RecurringTransaction, target_month: date
    ) -> date:
        """Berechnet das Soll-Buchungsdatum für eine Transaktion"""
        year = target_month.year
        month = target_month.month

        # Versuche den gewünschten Tag zu verwenden
        try:
            return date(year, month, trans.day_of_month)
        except ValueError:
            # Falls Tag nicht existiert (z.B. 31. Februar), nimm letzten Tag des Monats
            next_month = (
                date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
            )
            from datetime import timedelta

            last_day = next_month - timedelta(days=1)
            return last_day

    def _is_valid_booking_date(
        self, trans: RecurringTransaction, booking_date: date
    ) -> bool:
        """Prüft ob das Buchungsdatum im gültigen Zeitraum liegt"""
        if booking_date < trans.start_date:
            return False

        return not (trans.end_date and booking_date > trans.end_date)

    def update_recurring_transaction(
        self,
        transaction_id: int,
        typ: str,
        category: str,
        amount: float,
        details: str,
        day_of_month: int,
        is_active: bool,
        start_date: date,
        end_date: date | None = None,
    ) -> None:
        """Aktualisiert eine wiederkehrende Transaktion"""
        self.conn.execute(
            """
            UPDATE recurring_transactions 
            SET typ = ?, category = ?, amount = ?, details = ?, 
                day_of_month = ?, is_active = ?, start_date = ?, end_date = ?
            WHERE id = ?
            """,
            (
                typ,
                category,
                amount,
                details,
                day_of_month,
                1 if is_active else 0,
                start_date.isoformat(),
                end_date.isoformat() if end_date else None,
                transaction_id,
            ),
        )
        self.conn.commit()

    def delete_recurring_transaction(self, transaction_id: int) -> None:
        """Löscht eine wiederkehrende Transaktion"""
        self.conn.execute(
            "DELETE FROM recurring_transactions WHERE id = ?", (transaction_id,)
        )
        self.conn.commit()

    def toggle_active(self, transaction_id: int) -> None:
        """Aktiviert/Deaktiviert eine wiederkehrende Transaktion"""
        self.conn.execute(
            """
            UPDATE recurring_transactions 
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE id = ?
            """,
            (transaction_id,),
        )
        self.conn.commit()

    def _row_to_transaction(self, row: sqlite3.Row) -> RecurringTransaction:
        """Konvertiert eine Datenbank-Zeile in ein RecurringTransaction-Objekt"""
        return RecurringTransaction(
            id=row["id"],
            typ=row["typ"],
            category=row["category"],
            amount=float(row["amount"]),
            details=row["details"],
            day_of_month=int(row["day_of_month"]),
            is_active=bool(row["is_active"]),
            start_date=date.fromisoformat(row["start_date"]),
            end_date=date.fromisoformat(row["end_date"]) if row["end_date"] else None,
            created_date=datetime.fromisoformat(row["created_date"]),
            last_booking_date=(
                date.fromisoformat(row["last_booking_date"])
                if row["last_booking_date"]
                else None
            ),
        )
