from __future__ import annotations
import sqlite3
import shutil
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, List


class DatabaseManagementModel:
    """Model für Datenbank-Verwaltung: Reset, Backup, Statistiken"""
    
    def __init__(self, conn: sqlite3.Connection, db_path: str):
        self.conn = conn
        self.db_path = db_path
    
    def create_backup(self, backup_dir: Optional[str] = None, 
                      custom_name: Optional[str] = None) -> str:
        """
        Erstellt ein Backup der Datenbank
        
        Args:
            backup_dir: Zielverzeichnis (None = Standard)
            custom_name: Eigener Dateiname (None = Zeitstempel)
            
        Returns:
            Pfad zum erstellten Backup
        """
        if backup_dir is None:
            backup_dir = str(Path.home() / "BudgetManager_Backups")
        
        backup_path_obj = Path(backup_dir)
        backup_path_obj.mkdir(parents=True, exist_ok=True)
        
        if custom_name:
            backup_name = custom_name if custom_name.endswith('.db') else f"{custom_name}.db"
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"budgetmanager_backup_{timestamp}.db"
        
        backup_path = backup_path_obj / backup_name
        
        # Backup erstellen
        shutil.copy2(self.db_path, backup_path)
        
        return str(backup_path)
    
    def restore_from_backup(self, backup_path: str) -> bool:
        """
        Stellt die Datenbank aus einem Backup wieder her
        
        Args:
            backup_path: Pfad zum Backup
            
        Returns:
            True bei Erfolg
        """
        backup_file = Path(backup_path)
        if not backup_file.exists():
            raise FileNotFoundError(f"Backup nicht gefunden: {backup_path}")
        
        # Aktuelles DB schließen
        self.conn.close()
        
        # Sicherheitskopie der aktuellen DB
        current_backup = f"{self.db_path}.before_restore"
        shutil.copy2(self.db_path, current_backup)
        
        try:
            # Backup kopieren
            shutil.copy2(backup_path, self.db_path)
            
            # Neue Verbindung öffnen
            from model.database import open_db
            self.conn = open_db(self.db_path)
            
            return True
        except Exception as e:
            # Bei Fehler: Alte DB wiederherstellen
            shutil.copy2(current_backup, self.db_path)
            from model.database import open_db
            self.conn = open_db(self.db_path)
            raise e
        finally:
            # Temp-Backup löschen
            Path(current_backup).unlink(missing_ok=True)
    
    def reset_to_defaults(self, keep_categories: bool = True, 
                         keep_budgets: bool = False,
                         create_backup: bool = True) -> str:
        """
        Setzt die Datenbank auf Standardwerte zurück
        
        Args:
            keep_categories: Kategorien beibehalten
            keep_budgets: Budgets beibehalten
            create_backup: Backup vor Reset erstellen
            
        Returns:
            Pfad zum erstellten Backup (oder leerer String)
        """
        backup_path = ""
        
        # Backup erstellen
        if create_backup:
            backup_path = self.create_backup(custom_name="pre_reset")
        
        # Alle Transaktionen löschen
        self.conn.execute("DELETE FROM tracking")
        
        # Optional: Budgets löschen
        if not keep_budgets:
            self.conn.execute("DELETE FROM budget")
        
        # Optional: Kategorien löschen
        if not keep_categories:
            self.conn.execute("DELETE FROM categories")
        
        # Weitere Tabellen zurücksetzen
        self.conn.execute("DELETE FROM tags")
        self.conn.execute("DELETE FROM category_tags")
        self.conn.execute("DELETE FROM budget_warnings")
        self.conn.execute("DELETE FROM favorites")
        self.conn.execute("DELETE FROM savings_goals")
        self.conn.execute("DELETE FROM undo_stack")
        
        # Wiederkehrende Transaktionen zurücksetzen
        try:
            self.conn.execute("DELETE FROM recurring_transactions")
        except sqlite3.OperationalError:
            pass  # Tabelle existiert noch nicht
        
        self.conn.commit()
        
        # Standard-Kategorien anlegen wenn Kategorien gelöscht wurden
        if not keep_categories:
            self._create_default_categories()
        
        return backup_path
    
    def _create_default_categories(self):
        """Erstellt Standard-Kategorien"""
        default_categories = [
            ("Einnahmen", "Gehalt"),
            ("Einnahmen", "Bonus"),
            ("Einnahmen", "Sonstiges"),
            ("Ausgaben", "Miete"),
            ("Ausgaben", "Lebensmittel"),
            ("Ausgaben", "Transport"),
            ("Ausgaben", "Versicherungen"),
            ("Ausgaben", "Freizeit"),
            ("Ausgaben", "Sonstiges"),
        ]
        
        for typ, name in default_categories:
            try:
                self.conn.execute(
                    "INSERT OR IGNORE INTO categories (typ, name) VALUES (?, ?)",
                    (typ, name)
                )
            except sqlite3.IntegrityError:
                pass
        
        self.conn.commit()
    
    def get_database_statistics(self) -> Dict:
        """
        Gibt Statistiken über die Datenbank zurück
        
        Returns:
            Dictionary mit verschiedenen Statistiken
        """
        stats = {}
        
        # Datenbankgröße
        db_file = Path(self.db_path)
        stats['file_size_mb'] = db_file.stat().st_size / (1024 * 1024) if db_file.exists() else 0
        
        # Anzahl Einträge pro Tabelle
        tables = [
            'categories', 'budget', 'tracking', 'tags', 'category_tags',
            'budget_warnings', 'favorites', 'savings_goals', 'undo_stack',
            'theme_profiles'
        ]
        
        for table in tables:
            try:
                cur = self.conn.execute(f"SELECT COUNT(*) FROM {table}")
                stats[f'{table}_count'] = cur.fetchone()[0]
            except sqlite3.OperationalError:
                stats[f'{table}_count'] = 0
        
        # Wiederkehrende Transaktionen
        try:
            cur = self.conn.execute("SELECT COUNT(*) FROM recurring_transactions")
            stats['recurring_transactions_count'] = cur.fetchone()[0]
        except sqlite3.OperationalError:
            stats['recurring_transactions_count'] = 0
        
        # Zeitraum der Transaktionen
        cur = self.conn.execute(
            "SELECT MIN(date), MAX(date) FROM tracking WHERE date IS NOT NULL"
        )
        row = cur.fetchone()
        stats['first_transaction'] = row[0] if row[0] else None
        stats['last_transaction'] = row[1] if row[1] else None
        
        # Summen
        cur = self.conn.execute(
            "SELECT typ, SUM(amount) FROM tracking GROUP BY typ"
        )
        for typ, total in cur.fetchall():
            stats[f'total_{typ.lower()}'] = float(total)
        
        # Anzahl Jahre/Monate mit Daten
        cur = self.conn.execute(
            """
            SELECT COUNT(DISTINCT strftime('%Y', date)), 
                   COUNT(DISTINCT strftime('%Y-%m', date))
            FROM tracking WHERE date IS NOT NULL
            """
        )
        row = cur.fetchone()
        stats['years_with_data'] = row[0] if row else 0
        stats['months_with_data'] = row[1] if row else 0
        
        return stats
    
    def vacuum_database(self):
        """
        Optimiert die Datenbank (VACUUM)
        Gibt Speicherplatz frei und defragmentiert
        """
        self.conn.execute("VACUUM")
        self.conn.commit()
    
    def list_backups(self, backup_dir: Optional[str] = None) -> List[Dict]:
        """
        Listet alle verfügbaren Backups auf
        
        Returns:
            Liste von Dicts mit Backup-Informationen
        """
        if backup_dir is None:
            backup_dir = str(Path.home() / "BudgetManager_Backups")
        
        backup_path = Path(backup_dir)
        if not backup_path.exists():
            return []
        
        backups = []
        for backup_file in backup_path.glob("*.db"):
            stat = backup_file.stat()
            backups.append({
                'name': backup_file.name,
                'path': str(backup_file),
                'size_mb': stat.st_size / (1024 * 1024),
                'created': datetime.fromtimestamp(stat.st_ctime),
                'modified': datetime.fromtimestamp(stat.st_mtime)
            })
        
        # Sortiere nach Änderungsdatum (neueste zuerst)
        backups.sort(key=lambda x: x['modified'], reverse=True)
        
        return backups
    
    def delete_backup(self, backup_path: str) -> bool:
        """Löscht ein Backup"""
        backup_file = Path(backup_path)
        if backup_file.exists():
            backup_file.unlink()
            return True
        return False
    
    def export_data_json(self, output_path: str, include_tracking: bool = True,
                        include_budgets: bool = True, include_categories: bool = True) -> None:
        """
        Exportiert Daten als JSON
        
        Args:
            output_path: Zieldatei
            include_tracking: Transaktionen exportieren
            include_budgets: Budgets exportieren
            include_categories: Kategorien exportieren
        """
        import json
        
        data = {
            'export_date': datetime.now().isoformat(),
            'version': '0.17.0'
        }
        
        if include_categories:
            cur = self.conn.execute("SELECT id, typ, name, is_fix, is_recurring, recurring_day FROM categories")
            data['categories'] = [
                {
                    'id': row[0],
                    'typ': row[1],
                    'name': row[2],
                    'is_fix': bool(row[3]),
                    'is_recurring': bool(row[4]),
                    'recurring_day': row[5]
                }
                for row in cur.fetchall()
            ]
        
        if include_budgets:
            cur = self.conn.execute("SELECT year, month, typ, category, amount FROM budget")
            data['budgets'] = [
                {
                    'year': row[0],
                    'month': row[1],
                    'typ': row[2],
                    'category': row[3],
                    'amount': float(row[4])
                }
                for row in cur.fetchall()
            ]
        
        if include_tracking:
            cur = self.conn.execute("SELECT date, typ, category, amount, details FROM tracking")
            data['tracking'] = [
                {
                    'date': row[0],
                    'typ': row[1],
                    'category': row[2],
                    'amount': float(row[3]),
                    'details': row[4]
                }
                for row in cur.fetchall()
            ]
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
