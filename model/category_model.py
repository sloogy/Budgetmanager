from __future__ import annotations
import sqlite3
from dataclasses import dataclass

@dataclass(frozen=True)
class Category:
    id: int
    typ: str
    name: str
    is_fix: bool
    is_recurring: bool
    recurring_day: int

class CategoryModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def ensure_defaults(self) -> None:
        # Prüfe ob Defaults bereits geladen wurden
        flag = self.conn.execute(
            "SELECT value FROM system_flags WHERE key='defaults_loaded'"
        ).fetchone()
        
        if flag:
            return  # Defaults wurden bereits geladen, nichts tun
        
        defaults = {
            "Einkommen": [("Lohn (Netto)", 0, 1), ("Nebenerweb", 0, 0), ("Alimente (Netto)", 0, 0)],
            "Ausgaben": [
                ("Miete", 1, 1), ("Strom", 1, 1), ("Telefonie Internet TV", 1, 1), ("Natel", 1, 1),
                ("Streaming & Computer Abos", 0, 1), ("SERAFE", 1, 1), ("Steuern", 1, 1),
                ("Krankenkasse", 1, 1), ("Rechtschutzz", 1, 1), ("Hausrat", 1, 1), ("Haftpflicht", 1, 1),
                ("KFZ Rückzahlung", 1, 1), ("Tirza Jugendlohn.", 1, 1),
                ("Freizeit", 0, 0), ("ÖV / Sprit", 0, 0), ("Nahrungsmittel", 0, 0),
            ],
            "Ersparnisse": [("Ferien", 0, 0), ("Rücklagen", 0, 0), ("Sonderanschaffungen", 0, 0), ("3. Säule", 0, 1)],
        }
        cur=self.conn.cursor()
        for typ, items in defaults.items():
            for name, is_fix, is_rec in items:
                cur.execute(
                    "INSERT OR IGNORE INTO categories(typ,name,is_fix,is_recurring,recurring_day) VALUES(?,?,?,?,?)",
                    (typ, name, int(is_fix), int(is_rec), 1),
                )
        
        # Markiere als geladen
        cur.execute(
            "INSERT OR REPLACE INTO system_flags(key, value) VALUES('defaults_loaded', 'true')"
        )
        self.conn.commit()

    def list(self, typ: str | None = None) -> list[Category]:
        if typ:
            cur=self.conn.execute("SELECT * FROM categories WHERE typ=? ORDER BY name COLLATE NOCASE",(typ,))
        else:
            cur=self.conn.execute("SELECT * FROM categories ORDER BY typ, name COLLATE NOCASE")
        out=[]
        for r in cur.fetchall():
            out.append(
                Category(
                    int(r["id"]),
                    r["typ"],
                    r["name"],
                    bool(r["is_fix"]),
                    bool(r["is_recurring"]),
                    int(r["recurring_day"] or 1),
                )
            )
        return out

    def list_names(self, typ: str) -> list[str]:
        cur=self.conn.execute("SELECT name FROM categories WHERE typ=? ORDER BY name COLLATE NOCASE",(typ,))
        return [r["name"] for r in cur.fetchall()]

    def list_fix_names(self, typ: str) -> list[str]:
        cur=self.conn.execute("SELECT name FROM categories WHERE typ=? AND is_fix=1 ORDER BY name COLLATE NOCASE",(typ,))
        return [r["name"] for r in cur.fetchall()]

    def get_flags(self, typ: str, name: str) -> tuple[bool, bool, int]:
        """returns (is_fix, is_recurring, recurring_day). if missing -> (False, False, 1)"""
        cur = self.conn.execute(
            "SELECT is_fix, is_recurring, recurring_day FROM categories WHERE typ=? AND name=?",
            (typ, name),
        ).fetchone()
        if not cur:
            return (False, False, 1)
        return (bool(cur["is_fix"]), bool(cur["is_recurring"]), int(cur["recurring_day"] or 1))

    def upsert(self, typ: str, name: str, is_fix: bool, is_recurring: bool, recurring_day: int = 1) -> None:
        day = int(recurring_day) if recurring_day else 1
        if day < 1:
            day = 1
        if day > 31:
            day = 31
        self.conn.execute(
            "INSERT INTO categories(typ,name,is_fix,is_recurring,recurring_day) VALUES(?,?,?,?,?) "
            "ON CONFLICT(typ,name) DO UPDATE SET "
            "  is_fix=excluded.is_fix, "
            "  is_recurring=excluded.is_recurring, "
            "  recurring_day=excluded.recurring_day",
            (typ, name, int(is_fix), int(is_recurring), day),
        )
        self.conn.commit()

    def create(
        self,
        typ: str,
        name: str,
        is_fix: bool = False,
        is_recurring: bool = False,
        recurring_day: int = 1,
    ) -> int:
        """Legt eine neue Kategorie an und liefert die ID zurück."""
        day = int(recurring_day) if recurring_day else 1
        day = max(1, min(31, day))
        cur = self.conn.execute(
            "INSERT INTO categories(typ,name,is_fix,is_recurring,recurring_day) VALUES(?,?,?,?,?)",
            (typ, name, int(is_fix), int(is_recurring), day),
        )
        self.conn.commit()
        return int(cur.lastrowid)

    def update_flags(self, cat_id: int, *, is_fix: bool | None = None, is_recurring: bool | None = None, recurring_day: int | None = None) -> None:
        """Aktualisiert Flags (und optional den Tag) per ID."""
        fields: list[str] = []
        params: list[object] = []
        if is_fix is not None:
            fields.append("is_fix=?")
            params.append(int(is_fix))
        if is_recurring is not None:
            fields.append("is_recurring=?")
            params.append(int(is_recurring))
        if recurring_day is not None:
            day = max(1, min(31, int(recurring_day)))
            fields.append("recurring_day=?")
            params.append(day)
        if not fields:
            return
        params.append(int(cat_id))
        self.conn.execute(f"UPDATE categories SET {', '.join(fields)} WHERE id=?", params)
        self.conn.commit()

    def rename_and_cascade(self, cat_id: int, *, typ: str, old_name: str, new_name: str) -> None:
        """Benennt eine Kategorie um und aktualisiert Budget/Tracking (Kategorie-Textspalte)."""
        self.conn.execute("UPDATE categories SET name=? WHERE id=?", (new_name, int(cat_id)))
        # Cascade: budget/tracking referenzieren Kategorie per Name
        self.conn.execute(
            "UPDATE budget SET category=? WHERE typ=? AND category=?",
            (new_name, typ, old_name),
        )
        self.conn.execute(
            "UPDATE tracking SET category=? WHERE typ=? AND category=?",
            (new_name, typ, old_name),
        )
        self.conn.commit()

    def delete(self, typ: str, name: str) -> None:
        self.conn.execute("DELETE FROM categories WHERE typ=? AND name=?",(typ,name))
        self.conn.commit()

    def reset_defaults_flag(self) -> None:
        """
        Setzt das Flag zurück, damit ensure_defaults() beim nächsten Start wieder läuft.
        Nützlich für Entwicklung oder wenn Standard-Kategorien wiederhergestellt werden sollen.
        """
        self.conn.execute("DELETE FROM system_flags WHERE key='defaults_loaded'")
        self.conn.commit()
