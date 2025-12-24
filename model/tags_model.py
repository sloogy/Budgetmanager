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
