from __future__ import annotations
import sqlite3
import json
from datetime import datetime
from typing import Optional, Dict, Any

class UndoRedoModel:
    """Einfaches Undo/Redo System basierend auf Snapshots"""
    
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.max_stack_size = 50  # Maximale Anzahl von Undo-Einträgen

    def record_operation(self, table_name: str, operation: str, 
                        old_data: Optional[Dict[str, Any]] = None,
                        new_data: Optional[Dict[str, Any]] = None) -> None:
        """Zeichnet eine Operation für Undo/Redo auf"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        
        self.conn.execute(
            """
            INSERT INTO undo_stack (timestamp, table_name, operation, old_data, new_data)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                timestamp,
                table_name,
                operation,
                json.dumps(old_data) if old_data else None,
                json.dumps(new_data) if new_data else None
            )
        )
        self.conn.commit()
        
        # Stack-Größe begrenzen
        self._trim_stack()

    def _trim_stack(self) -> None:
        """Begrenzt die Stack-Größe"""
        cur = self.conn.execute("SELECT COUNT(*) FROM undo_stack")
        count = cur.fetchone()[0]
        
        if count > self.max_stack_size:
            self.conn.execute(
                """
                DELETE FROM undo_stack
                WHERE id IN (
                    SELECT id FROM undo_stack
                    ORDER BY timestamp ASC
                    LIMIT ?
                )
                """,
                (count - self.max_stack_size,)
            )
            self.conn.commit()

    def get_last_operation(self) -> Optional[Dict[str, Any]]:
        """Gibt die letzte Operation zurück"""
        cur = self.conn.execute(
            """
            SELECT id, timestamp, table_name, operation, old_data, new_data
            FROM undo_stack
            ORDER BY timestamp DESC
            LIMIT 1
            """
        )
        row = cur.fetchone()
        if not row:
            return None
        
        return {
            'id': row[0],
            'timestamp': row[1],
            'table_name': row[2],
            'operation': row[3],
            'old_data': json.loads(row[4]) if row[4] else None,
            'new_data': json.loads(row[5]) if row[5] else None
        }

    def undo_last(self) -> bool:
        """Macht die letzte Operation rückgängig"""
        op = self.get_last_operation()
        if not op:
            return False
        
        table = op['table_name']
        operation = op['operation']
        old_data = op['old_data']
        
        try:
            if operation == 'INSERT' and old_data:
                # Bei INSERT: Eintrag löschen
                self.conn.execute(f"DELETE FROM {table} WHERE id = ?", (old_data.get('id'),))
            elif operation == 'UPDATE' and old_data:
                # Bei UPDATE: Alte Werte wiederherstellen
                set_clause = ', '.join([f"{k} = ?" for k in old_data.keys() if k != 'id'])
                values = [v for k, v in old_data.items() if k != 'id']
                values.append(old_data['id'])
                self.conn.execute(f"UPDATE {table} SET {set_clause} WHERE id = ?", values)
            elif operation == 'DELETE' and old_data:
                # Bei DELETE: Eintrag wiederherstellen
                columns = ', '.join(old_data.keys())
                placeholders = ', '.join(['?' for _ in old_data])
                values = list(old_data.values())
                self.conn.execute(f"INSERT INTO {table} ({columns}) VALUES ({placeholders})", values)
            
            # Operation aus Stack entfernen
            self.conn.execute("DELETE FROM undo_stack WHERE id = ?", (op['id'],))
            self.conn.commit()
            return True
        except Exception:
            self.conn.rollback()
            return False

    def clear_stack(self) -> None:
        """Löscht den gesamten Undo-Stack"""
        self.conn.execute("DELETE FROM undo_stack")
        self.conn.commit()

    def get_stack_size(self) -> int:
        """Gibt die Anzahl der Operationen im Stack zurück"""
        cur = self.conn.execute("SELECT COUNT(*) FROM undo_stack")
        return cur.fetchone()[0]
