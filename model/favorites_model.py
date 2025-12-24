from __future__ import annotations
import sqlite3
from typing import List, Tuple

class FavoritesModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def add(self, typ: str, category: str) -> None:
        """Fügt eine Kategorie zu Favoriten hinzu"""
        max_order = self._get_max_order(typ)
        try:
            self.conn.execute(
                "INSERT INTO favorites (typ, category, sort_order) VALUES (?, ?, ?)",
                (typ, category, max_order + 1)
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            pass  # bereits in Favoriten

    def remove(self, typ: str, category: str) -> None:
        """Entfernt eine Kategorie aus Favoriten"""
        self.conn.execute(
            "DELETE FROM favorites WHERE typ = ? AND category = ?",
            (typ, category)
        )
        self.conn.commit()
        self._reorder(typ)

    def is_favorite(self, typ: str, category: str) -> bool:
        """Prüft ob eine Kategorie ein Favorit ist"""
        cur = self.conn.execute(
            "SELECT COUNT(*) FROM favorites WHERE typ = ? AND category = ?",
            (typ, category)
        )
        return cur.fetchone()[0] > 0

    def list_favorites(self, typ: str) -> List[str]:
        """Liste alle Favoriten für einen Typ"""
        cur = self.conn.execute(
            "SELECT category FROM favorites WHERE typ = ? ORDER BY sort_order, category",
            (typ,)
        )
        return [row[0] for row in cur.fetchall()]

    def list_all(self) -> List[Tuple[str, str]]:
        """Liste alle Favoriten (typ, category)"""
        cur = self.conn.execute(
            "SELECT typ, category FROM favorites ORDER BY typ, sort_order, category"
        )
        return [(row[0], row[1]) for row in cur.fetchall()]

    def move_up(self, typ: str, category: str) -> None:
        """Bewegt einen Favoriten nach oben"""
        favs = self.list_favorites(typ)
        if category not in favs:
            return
        idx = favs.index(category)
        if idx == 0:
            return
        favs[idx], favs[idx - 1] = favs[idx - 1], favs[idx]
        self._save_order(typ, favs)

    def move_down(self, typ: str, category: str) -> None:
        """Bewegt einen Favoriten nach unten"""
        favs = self.list_favorites(typ)
        if category not in favs:
            return
        idx = favs.index(category)
        if idx >= len(favs) - 1:
            return
        favs[idx], favs[idx + 1] = favs[idx + 1], favs[idx]
        self._save_order(typ, favs)

    def _get_max_order(self, typ: str) -> int:
        """Gibt die höchste sort_order zurück"""
        cur = self.conn.execute(
            "SELECT MAX(sort_order) FROM favorites WHERE typ = ?",
            (typ,)
        )
        result = cur.fetchone()[0]
        return result if result is not None else 0

    def _reorder(self, typ: str) -> None:
        """Ordnet die Favoriten neu"""
        favs = self.list_favorites(typ)
        self._save_order(typ, favs)

    def _save_order(self, typ: str, categories: List[str]) -> None:
        """Speichert die Reihenfolge"""
        for i, cat in enumerate(categories):
            self.conn.execute(
                "UPDATE favorites SET sort_order = ? WHERE typ = ? AND category = ?",
                (i, typ, cat)
            )
        self.conn.commit()
