from __future__ import annotations
import sqlite3
from datetime import date, datetime
from dataclasses import dataclass
from typing import Optional


@dataclass
class RecurringTransaction:
    """Wiederkehrende Transaktion mit Soll-Buchungsdatum"""
    id: Optional[int]
    typ: str  # 'Einnahmen' oder 'Ausgaben'
    category: str
    amount: float
    details: str
    day_of_month: int  # Tag im Monat (1-31)
    is_active: bool
    start_date: date
    end_date: Optional[date]
    created_date: datetime
    last_booking_date: Optional[date]


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
        end_date: Optional[date] = None,
        is_active: bool = True
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
                None
            )
        )
        self.conn.commit()
        return cur.lastrowid
    
    def get_all_recurring_transactions(self, active_only: bool = False) -> list[RecurringTransaction]:
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
    
    def get_pending_bookings(self, target_month: date) -> list[tuple[RecurringTransaction, date]]:
        """
        Gibt Liste von Transaktionen zurück, die für den Zielmonat gebucht werden müssen
        
        Returns:
            Liste von (RecurringTransaction, Soll-Buchungsdatum) Tupeln
        """
        transactions = self.get_all_recurring_transactions(active_only=True)
        pending = []
        
        for trans in transactions:
            # Prüfe ob bereits gebucht wurde in diesem Monat
            if self._is_already_booked(trans, target_month):
                continue
            
            # Berechne Soll-Buchungsdatum
            booking_date = self._calculate_booking_date(trans, target_month)
            
            # Prüfe ob Datum in gültigem Zeitraum liegt
            if not self._is_valid_booking_date(trans, booking_date):
                continue
            
            # Prüfe ob Datum erreicht oder überschritten
            if booking_date <= date.today():
                pending.append((trans, booking_date))
        
        return pending
    
    def _is_already_booked(self, trans: RecurringTransaction, target_month: date) -> bool:
        """Prüft ob die Transaktion bereits im Zielmonat gebucht wurde"""
        # Prüfe in tracking-Tabelle
        year = target_month.year
        month = target_month.month
        
        rows = self.conn.execute(
            """
            SELECT COUNT(*) FROM tracking 
            WHERE typ = ? 
              AND category = ? 
              AND strftime('%Y', date) = ? 
              AND strftime('%m', date) = ?
              AND details LIKE ?
            """,
            (
                trans.typ,
                trans.category,
                str(year),
                f"{month:02d}",
                f"%Wiederkehrend (ID: {trans.id})%"
            )
        ).fetchone()
        
        return rows[0] > 0 if rows else False
    
    def _calculate_booking_date(self, trans: RecurringTransaction, target_month: date) -> date:
        """Berechnet das Soll-Buchungsdatum für eine Transaktion"""
        year = target_month.year
        month = target_month.month
        
        # Versuche den gewünschten Tag zu verwenden
        try:
            return date(year, month, trans.day_of_month)
        except ValueError:
            # Falls Tag nicht existiert (z.B. 31. Februar), nimm letzten Tag des Monats
            if month == 12:
                next_month = date(year + 1, 1, 1)
            else:
                next_month = date(year, month + 1, 1)
            from datetime import timedelta
            last_day = next_month - timedelta(days=1)
            return last_day
    
    def _is_valid_booking_date(self, trans: RecurringTransaction, booking_date: date) -> bool:
        """Prüft ob das Buchungsdatum im gültigen Zeitraum liegt"""
        if booking_date < trans.start_date:
            return False
        
        if trans.end_date and booking_date > trans.end_date:
            return False
        
        return True
    
    def update_last_booking_date(self, transaction_id: int, booking_date: date) -> None:
        """Aktualisiert das letzte Buchungsdatum"""
        self.conn.execute(
            "UPDATE recurring_transactions SET last_booking_date = ? WHERE id = ?",
            (booking_date.isoformat(), transaction_id)
        )
        self.conn.commit()
    
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
        end_date: Optional[date] = None
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
                transaction_id
            )
        )
        self.conn.commit()
    
    def delete_recurring_transaction(self, transaction_id: int) -> None:
        """Löscht eine wiederkehrende Transaktion"""
        self.conn.execute(
            "DELETE FROM recurring_transactions WHERE id = ?",
            (transaction_id,)
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
            (transaction_id,)
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
            last_booking_date=date.fromisoformat(row["last_booking_date"]) if row["last_booking_date"] else None
        )
