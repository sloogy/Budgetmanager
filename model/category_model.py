from __future__ import annotations
import sqlite3
from dataclasses import dataclass

from model.undo_redo_model import UndoRedoModel

@dataclass(frozen=True)
class Category:
    id: int
    typ: str
    name: str
    parent_id: int | None
    is_fix: bool
    is_recurring: bool
    recurring_day: int
    funded_by_category_id: int | None
    sort_order: int

class CategoryModel:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        # Undo/Redo (global)
        self.undo = UndoRedoModel(conn)

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
        cols = self._cols("categories")
        cur=self.conn.cursor()
        for typ, items in defaults.items():
            for name, is_fix, is_rec in items:
                # v6+: parent_id/funded_by/sort_order existieren, bleiben aber NULL/0
                if "parent_id" in cols and "sort_order" in cols and "funded_by_category_id" in cols:
                    cur.execute(
                        "INSERT OR IGNORE INTO categories(typ,name,parent_id,is_fix,is_recurring,recurring_day,funded_by_category_id,sort_order) "
                        "VALUES(?,?,?,?,?,?,?,?)",
                        (typ, name, None, int(is_fix), int(is_rec), 1, None, 0),
                    )
                else:
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
            cur=self.conn.execute("SELECT * FROM categories WHERE typ=? ORDER BY sort_order, name COLLATE NOCASE",(typ,))
        else:
            cur=self.conn.execute("SELECT * FROM categories ORDER BY typ, sort_order, name COLLATE NOCASE")
        out=[]
        for r in cur.fetchall():
            out.append(
                Category(
                    int(r["id"]),
                    r["typ"],
                    r["name"],
                    int(r["parent_id"]) if "parent_id" in r.keys() and r["parent_id"] is not None else None,
                    bool(r["is_fix"]),
                    bool(r["is_recurring"]),
                    int(r["recurring_day"] or 1),
                    int(r["funded_by_category_id"]) if "funded_by_category_id" in r.keys() and r["funded_by_category_id"] is not None else None,
                    int(r["sort_order"]) if "sort_order" in r.keys() and r["sort_order"] is not None else 0,
                )
            )
        return out

    # ---------------------------------------------------------------------
    # Kompatibilitätsschicht (für Views aus dem 0.18.x-Branch)
    # ---------------------------------------------------------------------
    def get_all_categories(self) -> list[dict]:
        """Gibt alle Kategorien als Dict-Liste zurück.

        Einige Views/Dialogs (z.B. Übersicht / Fixkosten-Check) erwarten ein
        Dict-Format mit Keys wie 'id'/'name'/'type'. Intern arbeitet der
        Budgetmanager weiterhin mit 'typ' (Einkommen/Ausgaben/Ersparnisse).
        """

        cols = self._cols("categories")
        select = [
            "id",
            "typ",
            "name",
            "parent_id" if "parent_id" in cols else "NULL as parent_id",
            "is_fix" if "is_fix" in cols else "0 as is_fix",
            "is_recurring" if "is_recurring" in cols else "0 as is_recurring",
            "recurring_day" if "recurring_day" in cols else "1 as recurring_day",
            "funded_by_category_id" if "funded_by_category_id" in cols else "NULL as funded_by_category_id",
            "sort_order" if "sort_order" in cols else "0 as sort_order",
        ]
        # optional (einige Dialoge nutzen diesen Wert)
        if "expected_monthly_bookings" in cols:
            select.append("expected_monthly_bookings")
        else:
            select.append("1 as expected_monthly_bookings")

        cur = self.conn.execute(
            f"SELECT {', '.join(select)} FROM categories ORDER BY typ, sort_order, name COLLATE NOCASE"
        )

        def _map_type(typ: str) -> str:
            t = (typ or "").strip().lower()
            if t in ("einkommen", "einnahmen", "income"):
                return "income"
            if t in ("ausgaben", "expense", "expenses"):
                return "expense"
            if t in ("ersparnisse", "sparen", "savings"):
                return "savings"
            # Fallback: wie Ausgaben behandeln
            return "expense"

        out: list[dict] = []
        for r in cur.fetchall():
            out.append(
                {
                    "id": int(r["id"]),
                    "name": r["name"],
                    "typ": r["typ"],
                    "type": _map_type(r["typ"]),
                    "parent_id": int(r["parent_id"]) if r["parent_id"] is not None else None,
                    # Legacy-Key für Fixkosten-Dialoge
                    "is_fixcost": bool(r["is_fix"]),
                    "is_fix": bool(r["is_fix"]),
                    "is_recurring": bool(r["is_recurring"]),
                    "recurring_day": int(r["recurring_day"] or 1),
                    "funded_by_category_id": int(r["funded_by_category_id"]) if r["funded_by_category_id"] is not None else None,
                    "sort_order": int(r["sort_order"] or 0),
                    "expected_monthly_bookings": int(r["expected_monthly_bookings"] or 1),
                }
            )
        return out

    def list_tree(self) -> dict[str, list[Category]]:
        """Liefert alle Kategorien gruppiert nach typ (Einnahmen/Ausgaben/Ersparnisse)."""
        data: dict[str, list[Category]] = {"Einkommen": [], "Ausgaben": [], "Ersparnisse": []}
        for c in self.list(None):
            data.setdefault(c.typ, []).append(c)
        return data

    def build_tree(self, items: list[Category]) -> list[dict]:
        """Baut aus flacher Liste eine Baumstruktur.

        Returns: Liste von Nodes {cat: Category, children: [...]}
        """
        by_id: dict[int, dict] = {}
        roots: list[dict] = []
        for c in items:
            by_id[c.id] = {"cat": c, "children": []}
        for c in items:
            node = by_id[c.id]
            if c.parent_id and c.parent_id in by_id:
                by_id[c.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    def _cols(self, table: str) -> set[str]:
        try:
            cur = self.conn.execute(f"PRAGMA table_info({table});")
            return {row[1] for row in cur.fetchall()}
        except Exception:
            return set()

    def list_names(self, typ: str) -> list[str]:
        cur=self.conn.execute("SELECT name FROM categories WHERE typ=? ORDER BY name COLLATE NOCASE",(typ,))
        return [r["name"] for r in cur.fetchall()]

    def list_names_tree(self, typ: str) -> list[tuple[str, str]]:
        """Hierarchische Namensliste für Dropdowns.

        Anzeige: Einrückung bleibt, aber ab Unterkategorie wird zusätzlich der direkte Parent angezeigt:
        z.B. "  Krankenkasse › Selbstbehalt".

        Returns: [(anzeige_text, echter_name), ...]
        """
        items = self.list(typ)
        nodes = self.build_tree(items)

        out: list[tuple[str, str]] = []

        def walk(children: list[dict], depth: int, parent_name: str | None) -> None:
            for n in children:
                c: Category = n["cat"]
                prefix = "  " * depth
                label = c.name if depth == 0 or not parent_name else f"{parent_name} › {c.name}"
                out.append((f"{prefix}{label}", c.name))
                walk(n["children"], depth + 1, c.name)

        walk(nodes, 0, None)
        return out

    def list_fix_names(self, typ: str) -> list[str]:
        cur=self.conn.execute("SELECT name FROM categories WHERE typ=? AND is_fix=1 ORDER BY name COLLATE NOCASE",(typ,))
        return [r["name"] for r in cur.fetchall()]

    def list_fix_names_tree(self, typ: str) -> list[tuple[str, str]]:
        items = [c for c in self.list(typ) if c.is_fix]
        nodes = self.build_tree(items)
        out: list[tuple[str, str]] = []

        def walk(children: list[dict], depth: int, parent_name: str | None) -> None:
            for n in children:
                c: Category = n["cat"]
                prefix = "  " * depth
                label = c.name if depth == 0 or not parent_name else f"{parent_name} › {c.name}"
                out.append((f"{prefix}{label}", c.name))
                walk(n["children"], depth + 1, c.name)

        walk(nodes, 0, None)
        return out

    def display_with_parent(self, typ: str, name: str) -> str:
        """Gibt "Parent › Child" zurück, aber nur wenn die Kategorie einen Parent hat."""
        parent = self.get_parent_name(typ, name)
        return f"{parent} › {name}" if parent else name

    def get_parent_name(self, typ: str, name: str) -> str | None:
        """Gibt den direkten Parent-Namen zurück (oder None wenn Root)."""
        cols = self._cols("categories")
        if "parent_id" not in cols:
            return None
        row = self.conn.execute(
            "SELECT parent_id FROM categories WHERE typ=? AND name=?",
            (typ, name),
        ).fetchone()
        if not row or row["parent_id"] is None:
            return None
        prow = self.conn.execute("SELECT name FROM categories WHERE id=?", (int(row["parent_id"]),)).fetchone()
        return str(prow["name"]) if prow else None

    def get_flags(self, typ: str, name: str) -> tuple[bool, bool, int]:
        """returns (is_fix, is_recurring, recurring_day). if missing -> (False, False, 1)"""
        cur = self.conn.execute(
            "SELECT is_fix, is_recurring, recurring_day FROM categories WHERE typ=? AND name=?",
            (typ, name),
        ).fetchone()
        if not cur:
            return (False, False, 1)
        return (bool(cur["is_fix"]), bool(cur["is_recurring"]), int(cur["recurring_day"] or 1))

    def upsert(
        self,
        typ: str,
        name: str,
        is_fix: bool,
        is_recurring: bool,
        recurring_day: int = 1,
        *,
        parent_id: int | None = None,
        funded_by_category_id: int | None = None,
        sort_order: int = 0,
    ) -> None:
        day = int(recurring_day) if recurring_day else 1
        if day < 1:
            day = 1
        if day > 31:
            day = 31
        cols = self._cols("categories")
        if "parent_id" in cols and "funded_by_category_id" in cols and "sort_order" in cols:
            self.conn.execute(
                "INSERT INTO categories(typ,name,parent_id,is_fix,is_recurring,recurring_day,funded_by_category_id,sort_order) "
                "VALUES(?,?,?,?,?,?,?,?) "
                "ON CONFLICT(typ,name) DO UPDATE SET "
                "  parent_id=excluded.parent_id, "
                "  is_fix=excluded.is_fix, "
                "  is_recurring=excluded.is_recurring, "
                "  recurring_day=excluded.recurring_day, "
                "  funded_by_category_id=excluded.funded_by_category_id, "
                "  sort_order=excluded.sort_order",
                (typ, name, parent_id, int(is_fix), int(is_recurring), day, funded_by_category_id, int(sort_order)),
            )
        else:
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
        *,
        parent_id: int | None = None,
        funded_by_category_id: int | None = None,
        sort_order: int = 0,
    ) -> int:
        """Legt eine neue Kategorie an und liefert die ID zurück."""
        day = int(recurring_day) if recurring_day else 1
        day = max(1, min(31, day))
        cols = self._cols("categories")
        if "parent_id" in cols and "funded_by_category_id" in cols and "sort_order" in cols:
            cur = self.conn.execute(
                "INSERT INTO categories(typ,name,parent_id,is_fix,is_recurring,recurring_day,funded_by_category_id,sort_order) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (typ, name, parent_id, int(is_fix), int(is_recurring), day, funded_by_category_id, int(sort_order)),
            )
        else:
            cur = self.conn.execute(
                "INSERT INTO categories(typ,name,is_fix,is_recurring,recurring_day) VALUES(?,?,?,?,?)",
                (typ, name, int(is_fix), int(is_recurring), day),
            )
        self.conn.commit()
        new_id = int(cur.lastrowid)
        row = self.conn.execute("SELECT * FROM categories WHERE id=?", (new_id,)).fetchone()
        self.undo.record_operation("categories", "INSERT", None, dict(row) if row else None)
        return new_id

    def update_flags(self, cat_id: int, *, is_fix: bool | None = None, is_recurring: bool | None = None, recurring_day: int | None = None) -> None:
        """Aktualisiert Flags (und optional den Tag) per ID + Undo/Redo."""
        old = self.conn.execute("SELECT * FROM categories WHERE id=?", (int(cat_id),)).fetchone()
        old_d = dict(old) if old else None

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

        new = self.conn.execute("SELECT * FROM categories WHERE id=?", (int(cat_id),)).fetchone()
        new_d = dict(new) if new else None
        if old_d != new_d:
            self.undo.record_operation("categories", "UPDATE", old_d, new_d)

    def rename_and_cascade(self, cat_id: int, *, typ: str, old_name: str, new_name: str) -> None:
        """Benennt eine Kategorie um und aktualisiert Budget/Tracking (Kategorie-Textspalte).

        Wichtig: Budget/Tracking referenzieren Kategorie per Name (Legacy). Deshalb wird der Cascade als
        eigener Undo/Redo-Operationstyp gespeichert.
        """
        old_name = (old_name or "").strip()
        new_name = (new_name or "").strip()
        if not old_name or not new_name or old_name == new_name:
            return

        # ausführen
        self.conn.execute("UPDATE categories SET name=? WHERE id=?", (new_name, int(cat_id)))
        self.conn.execute(
            "UPDATE budget SET category=? WHERE typ=? AND category=?",
            (new_name, typ, old_name),
        )
        self.conn.execute(
            "UPDATE tracking SET category=? WHERE typ=? AND category=?",
            (new_name, typ, old_name),
        )
        self.conn.commit()

        self.undo.record_operation(
            "categories",
            "RENAME_CASCADE",
            {"cat_id": int(cat_id), "typ": typ, "old_name": old_name},
            {"cat_id": int(cat_id), "typ": typ, "new_name": new_name},
        )

    def delete(self, typ: str, name: str) -> None:
        old = self.conn.execute("SELECT * FROM categories WHERE typ=? AND name=?", (typ, name)).fetchone()
        old_d = dict(old) if old else None
        self.conn.execute("DELETE FROM categories WHERE typ=? AND name=?", (typ, name))
        self.conn.commit()
        if old_d:
            self.undo.record_operation("categories", "DELETE", old_d, None)

    def delete_by_ids(self, ids: list[int]) -> None:
        if not ids:
            return
        q = ",".join(["?"] * len(ids))
        rows = self.conn.execute(f"SELECT * FROM categories WHERE id IN ({q})", [int(i) for i in ids]).fetchall()
        old_rows = [dict(r) for r in rows]

<<<<<<< HEAD
        # Undo/Redo: Delete von mehreren Kategorien als eine Gruppe
        group = self.undo.new_group_id()
=======
<<<<<<< Updated upstream
        group = self.undo.new_group()
=======
        # Undo/Redo: Delete von mehreren Kategorien als eine Gruppe
        group = self.undo.new_group_id()
>>>>>>> Stashed changes
>>>>>>> origin/main
        self.conn.execute(f"DELETE FROM categories WHERE id IN ({q})", [int(i) for i in ids])
        self.conn.commit()

        for r in old_rows:
            self.undo.record_operation("categories", "DELETE", r, None, group_id=group)

    def update_parent(self, cat_id: int, new_parent_id: int | None) -> None:
        cols = self._cols("categories")
        if "parent_id" not in cols:
            return
        old = self.conn.execute("SELECT * FROM categories WHERE id=?", (int(cat_id),)).fetchone()
        old_d = dict(old) if old else None

        self.conn.execute("UPDATE categories SET parent_id=? WHERE id=?", (new_parent_id, int(cat_id)))
        self.conn.commit()

        new = self.conn.execute("SELECT * FROM categories WHERE id=?", (int(cat_id),)).fetchone()
        new_d = dict(new) if new else None
        if old_d != new_d:
            self.undo.record_operation("categories", "UPDATE", old_d, new_d)

    def reset_defaults_flag(self) -> None:
        """
        Setzt das Flag zurück, damit ensure_defaults() beim nächsten Start wieder läuft.
        Nützlich für Entwicklung oder wenn Standard-Kategorien wiederhergestellt werden sollen.
        """
        self.conn.execute("DELETE FROM system_flags WHERE key='defaults_loaded'")
        self.conn.commit()
