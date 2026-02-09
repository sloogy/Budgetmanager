"""
Database Management Model - Erweitert mit Reset-Funktionalität
Version 2.3.0.1

Neue Features:
- Datenbank auf Standard zurücksetzen
- Optionale Backup-Erstellung vor Reset
- Standard-Kategorien vordefiniert
"""

import sqlite3
import os
import shutil
from datetime import datetime
from typing import Optional, Tuple, List


class DatabaseManagementModel:
    """Verwaltung von Datenbank-Operationen inkl. Reset."""
    
    # Standard-Kategorien die beim Reset erstellt werden
    DEFAULT_CATEGORIES = {
        "Einkommen": [
            "Lohn (Netto)",
            "Nebenverdienst",
            "Bonuszahlungen",
            "Sonstige Einnahmen"
        ],
        "Ausgaben": [
            # Wohnen
            "Miete/Hypothek",
            "Nebenkosten",
            "Hausrat/Reparaturen",
            "Strom & Gas",
            
            # Versicherungen
            "Krankenversicherung",
            "Haftpflicht",
            "Hausrat",
            "Auto/Motorrad",
            
            # Lebensunterhalt
            "Lebensmittel",
            "Drogerie/Apotheke",
            "Kleidung",
            
            # Transport
            "ÖV/Benzin",
            "Auto-Unterhalt",
            "Parkgebühren",
            
            # Kommunikation
            "Telefon/Internet",
            "Streaming-Dienste",
            
            # Freizeit
            "Restaurant/Café",
            "Hobbys",
            "Urlaub/Reisen",
            "Sport/Fitness",
            
            # Sonstiges
            "Geschenke",
            "Haustiere",
            "Sonstiges"
        ],
        "Ersparnisse": [
            "Notgroschen",
            "Altersvorsorge",
            "Sparziele",
            "Investitionen"
        ]
    }
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.backup_dir = os.path.join(os.path.dirname(db_path), "backups")
        
    def create_backup(self, prefix: str = "manual") -> Tuple[bool, str]:
        """
        Erstellt ein Backup der Datenbank.
        
        Args:
            prefix: Präfix für Backup-Dateiname
            
        Returns:
            (success, backup_path_or_error_message)
        """
        try:
            os.makedirs(self.backup_dir, exist_ok=True)
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_filename = f"{prefix}_backup_{timestamp}.db"
            backup_path = os.path.join(self.backup_dir, backup_filename)
            
            shutil.copy2(self.db_path, backup_path)
            
            return True, backup_path
        except Exception as e:
            return False, f"Fehler beim Backup: {str(e)}"
    
    def get_available_backups(self) -> List[dict]:
        """
        Gibt Liste verfügbarer Backups zurück.
        
        Returns:
            Liste mit Backup-Informationen
        """
        if not os.path.exists(self.backup_dir):
            return []
        
        backups = []
        for filename in os.listdir(self.backup_dir):
            if filename.endswith('.db'):
                filepath = os.path.join(self.backup_dir, filename)
                stat = os.stat(filepath)
                backups.append({
                    'filename': filename,
                    'path': filepath,
                    'size': stat.st_size,
                    'created': datetime.fromtimestamp(stat.st_mtime),
                    'size_mb': round(stat.st_size / (1024 * 1024), 2)
                })
        
        return sorted(backups, key=lambda x: x['created'], reverse=True)
    
    def restore_backup(self, backup_path: str) -> Tuple[bool, str]:
        """
        Stellt Datenbank aus Backup wieder her.
        
        Args:
            backup_path: Pfad zur Backup-Datei
            
        Returns:
            (success, message)
        """
        try:
            if not os.path.exists(backup_path):
                return False, "Backup-Datei nicht gefunden"
            
            # Aktuelles DB als Sicherheit kopieren
            temp_backup = self.db_path + ".before_restore"
            shutil.copy2(self.db_path, temp_backup)
            
            try:
                # Restore durchführen
                shutil.copy2(backup_path, self.db_path)
                return True, "Wiederherstellung erfolgreich"
            except Exception as e:
                # Bei Fehler: Original wiederherstellen
                shutil.copy2(temp_backup, self.db_path)
                return False, f"Fehler bei Wiederherstellung: {str(e)}"
            finally:
                # Temp-Backup löschen
                if os.path.exists(temp_backup):
                    os.remove(temp_backup)
                    
        except Exception as e:
            return False, f"Unerwarteter Fehler: {str(e)}"
    
    def reset_database(self, create_backup: bool = True, 
                       keep_user_data: bool = False) -> Tuple[bool, str]:
        """
        Setzt Datenbank auf Standard zurück.
        
        Args:
            create_backup: Backup vor Reset erstellen
            keep_user_data: Wenn True, behält Tracking-Daten (nur Budget/Kategorien zurücksetzen)
            
        Returns:
            (success, message)
        """
        try:
            # Backup erstellen
            if create_backup:
                success, backup_info = self.create_backup("before_reset")
                if not success:
                    return False, f"Backup fehlgeschlagen: {backup_info}"
            
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            if keep_user_data:
                # Nur Budget und Kategorien zurücksetzen
                cursor.execute("DELETE FROM budget")
                cursor.execute("DELETE FROM categories")
                message = "Budget und Kategorien zurückgesetzt (Tracking-Daten behalten)"
            else:
                # Kompletter Reset - alle Tabellen leeren
                tables = [
                    'budget', 'categories', 'tracking', 'savings_goals',
                    'tags', 'entry_tags', 'recurring_transactions',
                    'fixcost_tracking', 'favorites', 'undo_stack', 'redo_stack'
                ]
                
                for table in tables:
                    try:
                        cursor.execute(f"DELETE FROM {table}")
                    except sqlite3.OperationalError:
                        # Tabelle existiert nicht - ignorieren
                        pass
                
                message = "Datenbank komplett zurückgesetzt"
            
            # Standard-Kategorien erstellen
            self._create_default_categories(conn)
            
            conn.commit()
            conn.close()
            
            return True, message
            
        except Exception as e:
            return False, f"Fehler beim Reset: {str(e)}"
    
    def _create_default_categories(self, conn: sqlite3.Connection):
        """Erstellt Standard-Kategorien."""
        cursor = conn.cursor()
        
        # Prüfe ob categories Tabelle existiert
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='categories'
        """)
        if not cursor.fetchone():
            # Tabelle existiert nicht - erstellen
            cursor.execute("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    typ TEXT NOT NULL,
                    name TEXT NOT NULL,
                    parent_id INTEGER DEFAULT NULL,
                    is_fix INTEGER DEFAULT 0,
                    is_recurring INTEGER DEFAULT 0,
                    recurring_day INTEGER DEFAULT 1,
                    is_favorite INTEGER DEFAULT 0,
                    UNIQUE(typ, name),
                    FOREIGN KEY (parent_id) REFERENCES categories(id)
                )
            """)
        
        for typ, categories in self.DEFAULT_CATEGORIES.items():
            for cat_name in categories:
                try:
                    cursor.execute("""
                        INSERT INTO categories (typ, name) 
                        VALUES (?, ?)
                    """, (typ, cat_name))
                except sqlite3.IntegrityError:
                    # Kategorie existiert bereits
                    pass
    
    def cleanup_database(self) -> Tuple[bool, str, dict]:
        """
        Bereinigt Datenbank (löscht verwaiste Einträge, optimiert).
        
        Returns:
            (success, message, statistics)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {
                'deleted_orphaned_budgets': 0,
                'deleted_orphaned_tags': 0,
                'deleted_invalid_dates': 0,
                'deleted_reserved_categories': 0
            }
            
            # 1. Lösche Budget-Einträge für nicht existierende Kategorien
            cursor.execute("""
                DELETE FROM budget 
                WHERE NOT EXISTS (
                    SELECT 1 FROM categories 
                    WHERE categories.typ = budget.typ 
                    AND categories.name = budget.category
                )
            """)
            stats['deleted_orphaned_budgets'] = cursor.rowcount
            
            # 2. Lösche reservierte Kategorien
            reserved_patterns = [
                '%BUDGET-SALDO%', '%TOTAL%', '%SUMME%', '%📊%'
            ]
            for pattern in reserved_patterns:
                cursor.execute("DELETE FROM budget WHERE category LIKE ?", (pattern,))
                stats['deleted_reserved_categories'] += cursor.rowcount
            
            # 3. Lösche verwaiste Tags
            cursor.execute("""
                DELETE FROM entry_tags 
                WHERE entry_id NOT IN (SELECT id FROM tracking)
            """)
            stats['deleted_orphaned_tags'] = cursor.rowcount
            
            # 4. Lösche Tracking-Einträge mit ungültigen Daten
            cursor.execute("""
                DELETE FROM tracking 
                WHERE date IS NULL 
                OR date NOT GLOB '[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]'
            """)
            stats['deleted_invalid_dates'] = cursor.rowcount
            
            # 5. VACUUM für Datenbank-Optimierung
            cursor.execute("VACUUM")
            
            conn.commit()
            conn.close()
            
            total_deleted = sum(stats.values())
            message = f"Bereinigung abgeschlossen: {total_deleted} Einträge gelöscht"
            
            return True, message, stats
            
        except Exception as e:
            return False, f"Fehler bei Bereinigung: {str(e)}", {}
    
    def get_database_statistics(self) -> dict:
        """
        Gibt Statistiken über die Datenbank zurück.
        
        Returns:
            Dictionary mit Statistiken
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            stats = {}
            
            # Dateigröße
            stats['db_size_mb'] = round(os.path.getsize(self.db_path) / (1024 * 1024), 2)
            
            # Tabellen-Zählungen
            tables = {
                'categories': 'Kategorien',
                'budget': 'Budget-Einträge',
                'tracking': 'Buchungen',
                'savings_goals': 'Sparziele',
                'tags': 'Tags',
                'recurring_transactions': 'Wiederkehrende Transaktionen'
            }
            
            for table, label in tables.items():
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[label] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[label] = 0
            
            # Jahre mit Daten
            cursor.execute("SELECT DISTINCT year FROM budget ORDER BY year")
            stats['Jahre'] = ", ".join(str(y[0]) for y in cursor.fetchall())
            
            conn.close()
            return stats
            
        except Exception as e:
            return {'Fehler': str(e)}
    
    def export_to_sql(self, output_path: str) -> Tuple[bool, str]:
        """
        Exportiert Datenbank als SQL-Dump.
        
        Args:
            output_path: Ziel-Dateipfad
            
        Returns:
            (success, message)
        """
        try:
            conn = sqlite3.connect(self.db_path)
            
            with open(output_path, 'w', encoding='utf-8') as f:
                for line in conn.iterdump():
                    f.write(f'{line}\n')
            
            conn.close()
            
            return True, f"Export erfolgreich: {output_path}"
            
        except Exception as e:
            return False, f"Fehler beim Export: {str(e)}"


if __name__ == '__main__':
    # Test
    model = DatabaseManagementModel('test_budget.db')
    
    print("=== Database Statistics ===")
    for key, value in model.get_database_statistics().items():
        print(f"{key}: {value}")
    
    print("\n=== Available Backups ===")
    for backup in model.get_available_backups():
        print(f"{backup['filename']} - {backup['size_mb']} MB - {backup['created']}")
