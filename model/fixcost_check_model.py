"""
Fixkosten-Check Model
Prüft ob monatliche Fixkosten bereits gebucht wurden
"""

import sqlite3
from datetime import datetime, date
from typing import List, Dict, Tuple, Optional


class FixcostCheckModel:
    """
    Verwaltet die Überprüfung und Verfolgung von Fixkosten-Buchungen.
    """
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._ensure_tables()
    
    def _ensure_tables(self):
        """Stellt sicher, dass alle benötigten Tabellen existieren."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Fixkosten-Tracking Tabelle
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fixcost_tracking (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category_id INTEGER NOT NULL,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                booked INTEGER DEFAULT 0,
                booked_date TEXT,
                amount REAL DEFAULT 0,
                FOREIGN KEY (category_id) REFERENCES categories(id),
                UNIQUE(category_id, year, month)
            )
        ''')
        
        # Kategorie-Erweiterungen prüfen
        cursor.execute("PRAGMA table_info(categories)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'is_fixcost' not in columns:
            cursor.execute('ALTER TABLE categories ADD COLUMN is_fixcost INTEGER DEFAULT 0')
        
        if 'expected_monthly_bookings' not in columns:
            cursor.execute('ALTER TABLE categories ADD COLUMN expected_monthly_bookings INTEGER DEFAULT 1')
        
        conn.commit()
        conn.close()
    
    def get_fixcost_categories(self) -> List[Dict]:
        """
        Gibt alle Kategorien zurück, die als Fixkosten markiert sind.
        
        Returns:
            Liste von Dictionaries mit Kategorie-Informationen
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id, 
                name, 
                type, 
                is_fixcost,
                expected_monthly_bookings
            FROM categories 
            WHERE is_fixcost = 1
            ORDER BY name
        ''')
        
        categories = []
        for row in cursor.fetchall():
            categories.append({
                'id': row[0],
                'name': row[1],
                'type': row[2],
                'is_fixcost': bool(row[3]),
                'expected_bookings': row[4] or 1
            })
        
        conn.close()
        return categories
    
    def get_missing_fixcosts(self, year: int, month: int) -> List[Dict]:
        """
        Gibt alle Fixkosten zurück, die im angegebenen Monat noch nicht gebucht wurden.
        
        Args:
            year: Jahr (z.B. 2024)
            month: Monat (1-12)
        
        Returns:
            Liste von Dictionaries mit fehlenden Fixkosten
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Alle Fixkosten-Kategorien holen
        fixcost_categories = self.get_fixcost_categories()
        
        missing = []
        for cat in fixcost_categories:
            # Prüfen ob bereits gebucht
            cursor.execute('''
                SELECT booked, booked_date, amount
                FROM fixcost_tracking
                WHERE category_id = ? AND year = ? AND month = ?
            ''', (cat['id'], year, month))
            
            tracking = cursor.fetchone()
            
            # Wenn nicht gebucht oder Tracking-Eintrag fehlt
            if not tracking or not tracking[0]:
                # Letzten Betrag aus vorherigen Buchungen ermitteln
                cursor.execute('''
                    SELECT AVG(amount) as avg_amount
                    FROM transactions
                    WHERE category_id = ?
                    AND strftime('%Y', date) = ?
                    AND strftime('%m', date) < ?
                    LIMIT 12
                ''', (cat['id'], str(year), f'{month:02d}'))
                
                avg_amount = cursor.fetchone()
                estimated_amount = avg_amount[0] if avg_amount[0] else 0.0
                
                missing.append({
                    'category_id': cat['id'],
                    'category_name': cat['name'],
                    'category_type': cat['type'],
                    'expected_bookings': cat['expected_bookings'],
                    'estimated_amount': round(estimated_amount, 2),
                    'year': year,
                    'month': month
                })
        
        conn.close()
        return missing
    
    def mark_as_booked(self, category_id: int, year: int, month: int, 
                       booking_date: str, amount: float = 0.0):
        """
        Markiert eine Fixkost als gebucht.
        
        Args:
            category_id: ID der Kategorie
            year: Jahr
            month: Monat
            booking_date: Buchungsdatum (ISO Format)
            amount: Gebuchter Betrag
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO fixcost_tracking 
            (category_id, year, month, booked, booked_date, amount)
            VALUES (?, ?, ?, 1, ?, ?)
        ''', (category_id, year, month, booking_date, amount))
        
        conn.commit()
        conn.close()
    
    def mark_as_unbooked(self, category_id: int, year: int, month: int):
        """
        Markiert eine Fixkost als nicht gebucht.
        
        Args:
            category_id: ID der Kategorie
            year: Jahr
            month: Monat
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE fixcost_tracking
            SET booked = 0, booked_date = NULL, amount = 0
            WHERE category_id = ? AND year = ? AND month = ?
        ''', (category_id, year, month))
        
        conn.commit()
        conn.close()
    
    def set_category_as_fixcost(self, category_id: int, is_fixcost: bool = True,
                                expected_bookings: int = 1):
        """
        Markiert eine Kategorie als Fixkost oder entfernt die Markierung.
        
        Args:
            category_id: ID der Kategorie
            is_fixcost: True wenn Fixkost, False sonst
            expected_bookings: Erwartete Anzahl Buchungen pro Monat
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE categories
            SET is_fixcost = ?, expected_monthly_bookings = ?
            WHERE id = ?
        ''', (1 if is_fixcost else 0, expected_bookings, category_id))
        
        conn.commit()
        conn.close()
    
    def get_fixcost_status_for_month(self, year: int, month: int) -> Dict:
        """
        Gibt eine Übersicht über den Fixkosten-Status für einen Monat.
        
        Args:
            year: Jahr
            month: Monat
        
        Returns:
            Dictionary mit Statistiken
        """
        fixcosts = self.get_fixcost_categories()
        missing = self.get_missing_fixcosts(year, month)
        
        total_fixcosts = len(fixcosts)
        missing_count = len(missing)
        booked_count = total_fixcosts - missing_count
        
        return {
            'year': year,
            'month': month,
            'total_fixcosts': total_fixcosts,
            'booked_count': booked_count,
            'missing_count': missing_count,
            'completion_percentage': (booked_count / total_fixcosts * 100) if total_fixcosts > 0 else 100,
            'missing_fixcosts': missing
        }
    
    def auto_detect_fixcosts(self, min_months: int = 6) -> List[int]:
        """
        Erkennt automatisch potenzielle Fixkosten basierend auf regelmäßigen Buchungen.
        
        Args:
            min_months: Mindestanzahl aufeinanderfolgender Monate
        
        Returns:
            Liste von Kategorie-IDs die als Fixkosten vorgeschlagen werden
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Kategorien mit regelmäßigen monatlichen Buchungen finden
        cursor.execute('''
            SELECT 
                category_id,
                COUNT(DISTINCT strftime('%Y-%m', date)) as month_count,
                AVG(amount) as avg_amount,
                MIN(amount) as min_amount,
                MAX(amount) as max_amount
            FROM transactions
            WHERE date >= date('now', '-12 months')
            GROUP BY category_id
            HAVING month_count >= ?
            AND (max_amount - min_amount) / avg_amount < 0.3
        ''', (min_months,))
        
        potential_fixcosts = [row[0] for row in cursor.fetchall()]
        
        conn.close()
        return potential_fixcosts
    
    def get_booking_history(self, category_id: int, months: int = 12) -> List[Dict]:
        """
        Gibt die Buchungshistorie für eine Fixkost zurück.
        
        Args:
            category_id: ID der Kategorie
            months: Anzahl Monate zurück
        
        Returns:
            Liste von Buchungen
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                strftime('%Y', date) as year,
                strftime('%m', date) as month,
                SUM(amount) as total_amount,
                COUNT(*) as booking_count
            FROM transactions
            WHERE category_id = ?
            AND date >= date('now', ? || ' months')
            GROUP BY year, month
            ORDER BY year DESC, month DESC
        ''', (category_id, -months))
        
        history = []
        for row in cursor.fetchall():
            history.append({
                'year': int(row[0]),
                'month': int(row[1]),
                'total_amount': row[2],
                'booking_count': row[3]
            })
        
        conn.close()
        return history


if __name__ == '__main__':
    # Test der Funktionalität
    model = FixcostCheckModel('test_budgetmanager.db')
    
    # Fixkosten-Kategorien anzeigen
    print("Fixkosten-Kategorien:")
    for cat in model.get_fixcost_categories():
        print(f"  - {cat['name']} (ID: {cat['id']})")
    
    # Fehlende Buchungen für aktuellen Monat
    now = datetime.now()
    print(f"\nFehlende Fixkosten für {now.month}/{now.year}:")
    missing = model.get_missing_fixcosts(now.year, now.month)
    for item in missing:
        print(f"  - {item['category_name']}: ~{item['estimated_amount']:.2f} €")
    
    # Status-Übersicht
    status = model.get_fixcost_status_for_month(now.year, now.month)
    print(f"\nStatus: {status['booked_count']}/{status['total_fixcosts']} gebucht "
          f"({status['completion_percentage']:.1f}%)")
