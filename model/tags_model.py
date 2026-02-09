from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from typing import List

@dataclass
class Tag:
    id: int
    name: str
    color: str

class TagsModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def create(self, name: str, color: str = '#3498db') -> int:
        """Erstellt einen neuen Tag"""
        cur = self.conn.execute(
            "INSERT INTO tags (name, color) VALUES (?, ?)",
            (name, color)
        )
        self.conn.commit()
        return cur.lastrowid

    def list_all(self) -> List[Tag]:
        """Liste alle Tags"""
        cur = self.conn.execute("SELECT id, name, color FROM tags ORDER BY name")
        return [Tag(id=row[0], name=row[1], color=row[2]) for row in cur.fetchall()]
    
    def get_all_tags(self) -> list[dict]:
        """
        Gibt alle Tags als Dictionary-Liste zurück.
        Für Kompatibilität mit overview_tab.
        """
        tags = self.list_all()
        return [
            {
                "id": tag.id,
                "name": tag.name,
                "color": tag.color
            }
            for tag in tags
        ]
    def get_tags_for_entry(self, entry_id: int) -> list[dict]:
        """
        Gibt alle Tags für einen Tracking-Eintrag zurück.

        Wichtig: Bei älteren DBs kann die Tabelle entry_tags fehlen. Dann liefern wir
        einfach eine leere Liste, statt die Übersicht zu crashen.
        """
        try:
            cur = self.conn.execute(
                """
                SELECT t.id, t.name, t.color
                FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ORDER BY t.name
                """,
                (entry_id,)
            )
        except sqlite3.OperationalError:
            return []

        return [
            {
                "id": row[0],
                "name": row[1],
                "color": row[2],
            }
            for row in cur.fetchall()
        ]

    def update(self, tag_id: int, name: str | None = None, color: str | None = None) -> None:
        """Aktualisiert einen Tag"""
        if name is not None:
            self.conn.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
        if color is not None:
            self.conn.execute("UPDATE tags SET color = ? WHERE id = ?", (color, tag_id))
        self.conn.commit()

    def delete(self, tag_id: int) -> None:
        """Löscht einen Tag"""
        self.conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self.conn.commit()

    def assign_to_category(self, category_id: int, tag_id: int) -> None:
        """Weist einen Tag einer Kategorie zu"""
        try:
            self.conn.execute(
                "INSERT INTO category_tags (category_id, tag_id) VALUES (?, ?)",
                (category_id, tag_id)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # bereits zugewiesen

    def remove_from_category(self, category_id: int, tag_id: int) -> None:
        """Entfernt einen Tag von einer Kategorie"""
        self.conn.execute(
            "DELETE FROM category_tags WHERE category_id = ? AND tag_id = ?",
            (category_id, tag_id)
        )
        self.conn.commit()

    def get_tags_for_category(self, category_id: int) -> List[Tag]:
        """Gibt alle Tags einer Kategorie zurück"""
        cur = self.conn.execute(
            """
            SELECT t.id, t.name, t.color 
            FROM tags t
            JOIN category_tags ct ON t.id = ct.tag_id
            WHERE ct.category_id = ?
            ORDER BY t.name
            """,
            (category_id,)
        )
        return [Tag(id=row[0], name=row[1], color=row[2]) for row in cur.fetchall()]

    def get_categories_by_tag(self, tag_id: int) -> List[int]:
        """Gibt alle Kategorie-IDs mit diesem Tag zurück"""
        cur = self.conn.execute(
            "SELECT category_id FROM category_tags WHERE tag_id = ?",
            (tag_id,)
        )
        return [row[0] for row in cur.fetchall()]

    # ── Kompatibilitäts-Aliases (für TagsManagerDialog) ──────────

    def create_tag(self, name: str, color: str | None = None) -> int | None:
        """Erstellt Tag – gibt ID zurück oder None bei Fehler."""
        try:
            return self.create(name, color or '#3498db')
        except Exception:
            return None

    def update_tag(self, tag_id: int, new_name: str) -> bool:
        """Benennt Tag um – gibt Erfolg zurück."""
        try:
            self.update(tag_id, name=new_name)
            return True
        except Exception:
            return False

    def update_tag_color(self, tag_id: int, color: str) -> bool:
        """Aktualisiert Tag-Farbe – gibt Erfolg zurück."""
        try:
            self.update(tag_id, color=color)
            return True
        except Exception:
            return False

    def delete_tag(self, tag_id: int) -> bool:
        """Löscht Tag – gibt Erfolg zurück."""
        try:
            self.delete(tag_id)
            return True
        except Exception:
            return False

    def merge_tags(self, source_ids: List[int], target_id: int) -> bool:
        """Führt Quell-Tags in ein Ziel-Tag zusammen.

        Alle entry_tags- und category_tags-Verknüpfungen werden auf
        target_id umgehängt. Duplikate werden ignoriert, Quell-Tags gelöscht.
        """
        try:
            for src_id in source_ids:
                if src_id == target_id:
                    continue
                # entry_tags umhängen (Duplikate ignorieren)
                self.conn.execute(
                    """
                    UPDATE OR IGNORE entry_tags SET tag_id = ?
                    WHERE tag_id = ?
                    """,
                    (target_id, src_id),
                )
                self.conn.execute(
                    "DELETE FROM entry_tags WHERE tag_id = ?", (src_id,)
                )
                # category_tags umhängen
                self.conn.execute(
                    """
                    UPDATE OR IGNORE category_tags SET tag_id = ?
                    WHERE tag_id = ?
                    """,
                    (target_id, src_id),
                )
                self.conn.execute(
                    "DELETE FROM category_tags WHERE tag_id = ?", (src_id,)
                )
                # Quell-Tag löschen
                self.conn.execute("DELETE FROM tags WHERE id = ?", (src_id,))
            self.conn.commit()
            return True
        except Exception:
            return False

    def get_tag_stats(self) -> list[tuple]:
        """Statistiken: (tag_name, anzahl_buchungen, gesamtbetrag).

        Basiert auf entry_tags ↔ tracking.
        """
        try:
            cur = self.conn.execute(
                """
                SELECT t.name,
                       COUNT(DISTINCT et.entry_id),
                       COALESCE(SUM(tr.amount), 0)
                FROM tags t
                LEFT JOIN entry_tags et ON t.id = et.tag_id
                LEFT JOIN tracking tr   ON et.entry_id = tr.id
                GROUP BY t.id
                ORDER BY COUNT(DISTINCT et.entry_id) DESC
                """
            )
            return [(row[0], row[1], row[2]) for row in cur.fetchall()]
        except Exception:
            return []
