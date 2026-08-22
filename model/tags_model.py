from __future__ import annotations

import logging
import re
import sqlite3
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Tag:
    """Ein Tag/Label.

    v2.2.31 (API-Vereinheitlichung): Bis v2.2.30 lieferte ``TagsModel``
    uneinheitlich mal ``Tag``-Objekte (``list_all``, ``get_tags_for_category``)
    und mal rohe ``dict``s (``get_all_tags``, ``list_tags``,
    ``get_tags_for_entry``). Aufrufer mussten wissen, welche Methode welchen
    Typ liefert – eine stille Stolperfalle, die beim Umbenennen einer Methode
    zu ``AttributeError``/``TypeError`` zur Laufzeit geführt hätte.

    Statt alle Aufrufer anzufassen, wird der Invariant hier *by construction*
    hergestellt: ``Tag`` unterstützt zusätzlich lesenden Mapping-Zugriff.
    Damit funktionieren ``tag.name`` UND ``tag["name"]`` gleichermaßen, und
    alle Model-Methoden können einheitlich ``Tag`` zurückgeben.
    """

    id: int
    name: str
    color: str
    action_text: str = ""

    _FIELDS = ("id", "name", "color", "action_text")

    # ── Read-only Mapping-Protokoll (Rückwärtskompatibilität) ────────

    def to_dict(self) -> dict:
        """Explizite dict-Kopie (z. B. für JSON-Export)."""
        return {
            "id": self.id,
            "name": self.name,
            "color": self.color,
            "action_text": self.action_text,
        }

    def __getitem__(self, key: str):
        if key not in self._FIELDS:
            raise KeyError(key)
        return getattr(self, key)

    def get(self, key: str, default=None):
        return getattr(self, key, default) if key in self._FIELDS else default

    def keys(self):
        return iter(self._FIELDS)

    def values(self):
        return (getattr(self, k) for k in self._FIELDS)

    def items(self):
        return ((k, getattr(self, k)) for k in self._FIELDS)

    def __contains__(self, key) -> bool:
        return key in self._FIELDS


class TagsModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _has_column(self, table: str, column: str) -> bool:
        # v2.2.25 (d1-Härtung): Tabellenname strikt als SQL-Identifier
        # validieren, bevor er das PRAGMA erreicht (Defense-in-Depth,
        # gleiches Muster wie migrations._cols / category_model._safe_table).
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table):
            return False
        try:
            rows = self.conn.execute(f"PRAGMA table_info({table})").fetchall()
            return column in {str(row[1]) for row in rows}
        except Exception:
            return False

    def create(self, name: str, color: str = "#3498db", action_text: str = "") -> int:
        """Erstellt einen neuen Tag.

        action_text ist optionaler freier Text, der beim Anhaken des Tags als
        Buchungs-Details vorgeschlagen wird. Unterstützte Platzhalter siehe
        render_action_text().
        """
        if self._has_column("tags", "action_text"):
            cur = self.conn.execute(
                "INSERT INTO tags (name, color, action_text) VALUES (?, ?, ?)",
                (name, color or "#3498db", action_text or ""),
            )
        else:
            cur = self.conn.execute(
                "INSERT INTO tags (name, color) VALUES (?, ?)",
                (name, color or "#3498db"),
            )
        self.conn.commit()
        return cur.lastrowid

    def list_all(self) -> list[Tag]:
        """Liste alle Tags"""
        action_col = (
            "action_text"
            if self._has_column("tags", "action_text")
            else "'' AS action_text"
        )
        cur = self.conn.execute(
            f"SELECT id, name, color, {action_col} FROM tags ORDER BY name"  # nosec B608
        )
        return [
            Tag(
                id=int(row[0]),
                name=str(row[1]),
                color=str(row[2] or "#3498db"),
                action_text=str(row[3] or ""),
            )
            for row in cur.fetchall()
        ]

    def list_tags(self, active_only: bool = False) -> list[Tag]:
        """Alias auf :meth:`list_all` für Views, die diesen Namen nutzen.

        Es gibt aktuell keine aktive/inaktive Tag-Spalte; active_only bleibt
        deshalb absichtlich ein No-op.

        v2.2.31: liefert wie alle anderen Lesemethoden ``Tag``-Objekte.
        Dank Mapping-Protokoll bleibt ``t["name"]`` weiterhin gültig.
        """
        return self.list_all()

    def get_all_tags(self) -> list[Tag]:
        """Alias auf :meth:`list_all` (historischer Name aus overview_tab).

        v2.2.31: liefert ``Tag``-Objekte statt roher Dicts – einheitlich mit
        ``list_all``/``get_tags_for_category``. Bestehende Aufrufer mit
        ``t["id"]`` funktionieren unverändert weiter.
        """
        return self.list_all()

    def get_tags_for_entry(self, entry_id: int) -> list[Tag]:
        """
        Gibt alle Tags für einen Tracking-Eintrag zurück.

        Wichtig: Bei älteren DBs kann die Tabelle entry_tags fehlen. Dann liefern wir
        einfach eine leere Liste, statt die Übersicht zu crashen.
        """
        try:
            action_col = (
                "t.action_text" if self._has_column("tags", "action_text") else "''"
            )
            cur = self.conn.execute(
                f"""
                SELECT t.id, t.name, t.color, COALESCE({action_col}, '')
                FROM tags t
                JOIN entry_tags et ON t.id = et.tag_id
                WHERE et.entry_id = ?
                ORDER BY t.name
                """,  # nosec B608
                (entry_id,),
            )
        except sqlite3.OperationalError:
            return []

        return [
            Tag(
                id=int(row[0]),
                name=str(row[1]),
                color=str(row[2] or "#3498db"),
                action_text=str(row[3] or "") if len(row) > 3 else "",
            )
            for row in cur.fetchall()
        ]

    # ── Entry-Tag-Verknüpfungen (Tracking ↔ Tags) ────────────

    def assign_to_entry(self, entry_id: int, tag_id: int) -> None:
        """Weist einen Tag einem Tracking-Eintrag zu."""
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                (entry_id, tag_id),
            )
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning("add_to_entry: entry_tags Tabelle nicht verfügbar: %s", e)

    def remove_from_entry(self, entry_id: int, tag_id: int) -> None:
        """Entfernt einen Tag von einem Tracking-Eintrag."""
        try:
            self.conn.execute(
                "DELETE FROM entry_tags WHERE entry_id = ? AND tag_id = ?",
                (entry_id, tag_id),
            )
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning(
                "remove_from_entry: entry_tags Tabelle nicht verfügbar: %s", e
            )

    def set_entry_tags(self, entry_id: int, tag_ids: list[int]) -> None:
        """Setzt die Tags eines Eintrags auf exakt die angegebene Liste.

        Entfernt alle bisherigen Tags und setzt nur die neuen.
        """
        try:
            fixed_ids: list[int] = []
            try:
                row = self.conn.execute(
                    "SELECT typ, category FROM tracking WHERE id=?",
                    (int(entry_id),),
                ).fetchone()
                if row:
                    fixed_ids = self.get_tag_ids_for_category_name(
                        str(row[0]),
                        str(row[1]),
                    )
            except Exception:
                fixed_ids = []

            final_ids = sorted(
                {int(tid) for tid in tag_ids} | {int(tid) for tid in fixed_ids}
            )
            self.conn.execute("DELETE FROM entry_tags WHERE entry_id = ?", (entry_id,))
            for tid in final_ids:
                self.conn.execute(
                    "INSERT OR IGNORE INTO entry_tags (entry_id, tag_id) VALUES (?, ?)",
                    (entry_id, tid),
                )
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning("set_entry_tags: entry_tags Tabelle nicht verfügbar: %s", e)

    def get_entry_ids_by_tag(self, tag_id: int) -> list[int]:
        """Gibt alle Tracking-Entry-IDs mit diesem Tag zurück."""
        try:
            cur = self.conn.execute(
                "SELECT entry_id FROM entry_tags WHERE tag_id = ?",
                (tag_id,),
            )
            return [row[0] for row in cur.fetchall()]
        except sqlite3.OperationalError:
            return []

    def update(
        self,
        tag_id: int,
        name: str | None = None,
        color: str | None = None,
        action_text: str | None = None,
    ) -> None:
        """Aktualisiert einen Tag"""
        if name is not None:
            self.conn.execute("UPDATE tags SET name = ? WHERE id = ?", (name, tag_id))
        if color is not None:
            self.conn.execute("UPDATE tags SET color = ? WHERE id = ?", (color, tag_id))
        if action_text is not None and self._has_column("tags", "action_text"):
            self.conn.execute(
                "UPDATE tags SET action_text = ? WHERE id = ?",
                (action_text, tag_id),
            )
        self.conn.commit()

    def delete(self, tag_id: int) -> None:
        """Löscht einen Tag"""
        self.conn.execute("DELETE FROM tags WHERE id = ?", (tag_id,))
        self.conn.commit()

    def assign_to_category(self, category_id: int, tag_id: int) -> None:
        """Weist einen Tag einer Kategorie zu"""
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO category_tags (category_id, tag_id) VALUES (?, ?)",
                (category_id, tag_id),
            )
            self.conn.commit()
        except sqlite3.IntegrityError:
            logger.debug(
                "assign_to_category: Tag bereits zugewiesen (category_id=%s, tag_id=%s)",
                category_id,
                tag_id,
            )

    def remove_from_category(self, category_id: int, tag_id: int) -> None:
        """Entfernt einen Tag von einer Kategorie"""
        self.conn.execute(
            "DELETE FROM category_tags WHERE category_id = ? AND tag_id = ?",
            (category_id, tag_id),
        )
        self.conn.commit()

    def get_tags_for_category(self, category_id: int) -> list[Tag]:
        """Gibt alle Tags einer Kategorie zurück"""
        action_col = (
            "t.action_text" if self._has_column("tags", "action_text") else "''"
        )
        cur = self.conn.execute(
            f"""
            SELECT t.id, t.name, t.color, COALESCE({action_col}, '')
            FROM tags t
            JOIN category_tags ct ON t.id = ct.tag_id
            WHERE ct.category_id = ?
            ORDER BY t.name
            """,  # nosec B608
            (category_id,),
        )
        return [
            Tag(
                id=int(row[0]),
                name=str(row[1]),
                color=str(row[2] or "#3498db"),
                action_text=str(row[3] or ""),
            )
            for row in cur.fetchall()
        ]

    def get_categories_by_tag(self, tag_id: int) -> list[int]:
        """Gibt alle Kategorie-IDs mit diesem Tag zurück"""
        cur = self.conn.execute(
            "SELECT category_id FROM category_tags WHERE tag_id = ?", (tag_id,)
        )
        return [row[0] for row in cur.fetchall()]

    # ── Kompatibilitäts-Aliases (für TagsManagerDialog) ──────────

    def create_tag(
        self, name: str, color: str | None = None, action_text: str | None = None
    ) -> int | None:
        """Erstellt Tag – gibt ID zurück oder None bei Fehler."""
        try:
            return self.create(name, color or "#3498db", action_text or "")
        except Exception:
            return None

    def update_tag(
        self, tag_id: int, new_name: str, action_text: str | None = None
    ) -> bool:
        """Benennt Tag um/ändert Aktionstext – gibt Erfolg zurück."""
        try:
            self.update(tag_id, name=new_name, action_text=action_text)
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

    def merge_tags(self, source_ids: list[int], target_id: int) -> bool:
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
                self.conn.execute("DELETE FROM entry_tags WHERE tag_id = ?", (src_id,))
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

    def set_category_tags(self, category_id: int, tag_ids: list[int]) -> None:
        """Setzt die fix an einer Kategorie haftenden Tags exakt."""
        try:
            self.conn.execute(
                "DELETE FROM category_tags WHERE category_id = ?",
                (int(category_id),),
            )
            for tag_id in tag_ids:
                self.conn.execute(
                    "INSERT OR IGNORE INTO category_tags (category_id, tag_id) VALUES (?, ?)",
                    (int(category_id), int(tag_id)),
                )
            self.conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning(
                "set_category_tags: category_tags Tabelle nicht verfügbar: %s",
                e,
            )

    def get_tag_ids_for_category_name(self, typ: str, category: str) -> list[int]:
        """Gibt fix zugewiesene Tag-IDs für typ+category zurück."""
        try:
            row = self.conn.execute(
                "SELECT id FROM categories WHERE typ=? AND name=?",
                (typ, category),
            ).fetchone()
            if not row:
                return []
            cur = self.conn.execute(
                "SELECT tag_id FROM category_tags WHERE category_id=? ORDER BY tag_id",
                (int(row[0]),),
            )
            return [int(r[0]) for r in cur.fetchall()]
        except Exception:
            return []

    def get_tags_by_ids(self, tag_ids: list[int] | tuple[int, ...]) -> list[Tag]:
        ids = [int(x) for x in tag_ids if x is not None]
        if not ids:
            return []
        placeholders = ",".join(["?"] * len(ids))
        action_col = (
            "action_text"
            if self._has_column("tags", "action_text")
            else "'' AS action_text"
        )
        cur = self.conn.execute(
            f"""
            SELECT id, name, color, {action_col}
            FROM tags
            WHERE id IN ({placeholders})
            ORDER BY name
            """,  # nosec B608
            tuple(ids),
        )
        return [
            Tag(
                id=int(row[0]),
                name=str(row[1]),
                color=str(row[2] or "#3498db"),
                action_text=str(row[3] or ""),
            )
            for row in cur.fetchall()
        ]

    @staticmethod
    def render_action_text(
        template: str,
        *,
        tag_name: str,
        category: str,
        booking_date=None,
    ) -> str:
        """Rendert den frei hinterlegbaren Aktionstext eines Tags.

        Unterstützte Platzhalter: {date}, {datum}, {tag}, {category},
        {kategorie}, {month}, {monat}. Bei ungültigen Templates wird der
        Rohtext sicher zurückgegeben.
        """
        text = (template or "").strip()
        if not text:
            return ""
        try:
            from datetime import date as _date

            d = booking_date if booking_date is not None else _date.today()
            iso = d.isoformat() if hasattr(d, "isoformat") else str(d)
            try:
                from utils.i18n import tr

                month = (
                    tr(f"month.{int(getattr(d, 'month', 0))}")
                    if getattr(d, "month", None)
                    else ""
                )
            except Exception:
                month = ""
            return text.format(
                date=iso,
                datum=iso,
                tag=tag_name,
                category=category or "",
                kategorie=category or "",
                month=month,
                monat=month,
            )
        except Exception:
            return text

    def render_action_texts(
        self,
        tag_ids: list[int] | tuple[int, ...],
        *,
        category: str,
        booking_date=None,
    ) -> str:
        """Rendert alle Aktionstexte der gewählten Tags, getrennt mit |."""
        parts: list[str] = []
        for tag in self.get_tags_by_ids(tag_ids):
            rendered = self.render_action_text(
                tag.action_text,
                tag_name=tag.name,
                category=category,
                booking_date=booking_date,
            )
            if rendered:
                parts.append(rendered)
        return " | ".join(parts)

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

    def usage_count(self, tag_id: int) -> int:
        """Anzahl der Buchungen, die diesen Tag verwenden."""
        try:
            cur = self.conn.execute(
                "SELECT COUNT(DISTINCT entry_id) FROM entry_tags WHERE tag_id = ?",
                (tag_id,),
            )
            row = cur.fetchone()
            return int(row[0]) if row else 0
        except Exception:
            return 0

    def name_exists(self, name: str) -> bool:
        """Prüft ob ein Tag-Name bereits existiert."""
        try:
            cur = self.conn.execute("SELECT COUNT(*) FROM tags WHERE name = ?", (name,))
            row = cur.fetchone()
            return (row[0] > 0) if row else False
        except Exception:
            return False
