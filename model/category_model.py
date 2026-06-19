from __future__ import annotations
import logging

logger = logging.getLogger(__name__)
import sqlite3
from dataclasses import dataclass
from typing import List

from model.undo_redo_model import UndoRedoModel

"""Kategorie-Datenmodell.

Verwaltet Kategorien mit hierarchischer Eltern-Kind-Struktur,
Typen (Ausgaben/Einkommen/Ersparnisse), Fixkosten- und Wiederkehrend-Flags.
"""


class CategoryError(ValueError):
    """Benutzer-sichtbarer Kategorie-Fehler mit i18n-Key.

    Bleibt eine ``ValueError``-Subklasse, damit bestehende
    ``except ValueError``/``except Exception`` Pfade unverändert greifen.
    ``str()`` rendert den Text zur Anzeigezeit lokalisiert (de/en/fr),
    inklusive optionaler ``str.format``-Argumente. Dadurch erscheinen die
    Meldungen in Dialogen übersetzt, auch wenn ein Aufrufer den Fehler nur
    generisch als ``{error}``/``{value_0}`` einbettet, statt den rohen
    i18n-Key auszugeben.
    """

    def __init__(self, key: str, **fmt):
        self.key = key
        self.fmt = fmt
        super().__init__(key)

    def __str__(self) -> str:
        try:
            from utils.i18n import tr, trf

            return trf(self.key, **self.fmt) if self.fmt else tr(self.key)
        except Exception:
            return self.key


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
    _ALLOWED_SCHEMA_TABLES = frozenset(
        {
            "budget",
            "budget_warnings",
            "categories",
            "category_tags",
            "entry_tags",
            "favorites",
            "recurring_transactions",
            "savings_goals",
            "suggestion_accepted",
            "system_flags",
            "tracking",
        }
    )
    _CATEGORY_TEXT_REFERENCE_TABLES = frozenset(
        {
            "budget",
            "favorites",
            "budget_warnings",
            "recurring_transactions",
            "suggestion_accepted",
        }
    )

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

        # Zentrale Quelle: data/default_categories.json (siehe model/default_categories.py).
        # Die frühere hardcodierte Liste (inkl. persönlicher Einträge und Tippfehler
        # wie "Nebenerweb"/"Rechtschutzz") wurde in v1.0.30 entfernt — Erststart und
        # Reset verwenden jetzt dieselbe Quelle UND dieselbe Insert-Routine
        # (inkl. Unterkategorien via parent_id, v1.0.34).
        from model.default_categories import insert_default_categories

        try:
            from settings import Settings

            preferred_day = int(Settings().get("recurring_preferred_day", 25) or 0)
        except Exception:
            preferred_day = 25
        insert_default_categories(self.conn, recurring_day_override=preferred_day)

        # Markiere als geladen
        self.conn.execute(
            "INSERT OR REPLACE INTO system_flags(key, value) VALUES('defaults_loaded', 'true')"
        )
        self.conn.commit()

    def list(self, typ: str | None = None) -> List[Category]:
        if typ:
            cur = self.conn.execute(
                "SELECT * FROM categories WHERE typ=? ORDER BY sort_order, name COLLATE NOCASE",
                (typ,),
            )
        else:
            cur = self.conn.execute(
                "SELECT * FROM categories ORDER BY typ, sort_order, name COLLATE NOCASE"
            )
        out = []
        for r in cur.fetchall():
            out.append(
                Category(
                    int(r["id"]),
                    r["typ"],
                    r["name"],
                    (
                        int(r["parent_id"])
                        if "parent_id" in r.keys() and r["parent_id"] is not None
                        else None
                    ),
                    bool(r["is_fix"]),
                    bool(r["is_recurring"]),
                    int(r["recurring_day"] or 1),
                    (
                        int(r["funded_by_category_id"])
                        if "funded_by_category_id" in r.keys()
                        and r["funded_by_category_id"] is not None
                        else None
                    ),
                    (
                        int(r["sort_order"])
                        if "sort_order" in r.keys() and r["sort_order"] is not None
                        else 0
                    ),
                )
            )
        return out

    # ---------------------------------------------------------------------
    # Kompatibilitätsschicht (für Views aus dem 0.18.x-Branch)
    # ---------------------------------------------------------------------
    def get_all_categories(self) -> List[dict]:
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
            (
                "funded_by_category_id"
                if "funded_by_category_id" in cols
                else "NULL as funded_by_category_id"
            ),
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

        out: List[dict] = []
        for r in cur.fetchall():
            out.append(
                {
                    "id": int(r["id"]),
                    "name": r["name"],
                    "typ": r["typ"],
                    "type": _map_type(r["typ"]),
                    "parent_id": (
                        int(r["parent_id"]) if r["parent_id"] is not None else None
                    ),
                    # Legacy-Key für Fixkosten-Dialoge
                    "is_fixcost": bool(r["is_fix"]),
                    "is_fix": bool(r["is_fix"]),
                    "is_recurring": bool(r["is_recurring"]),
                    "recurring_day": int(r["recurring_day"] or 1),
                    "funded_by_category_id": (
                        int(r["funded_by_category_id"])
                        if r["funded_by_category_id"] is not None
                        else None
                    ),
                    "sort_order": int(r["sort_order"] or 0),
                    "expected_monthly_bookings": int(
                        r["expected_monthly_bookings"] or 1
                    ),
                }
            )
        return out

    def list_tree(self) -> dict[str, List[Category]]:
        """Liefert alle Kategorien gruppiert nach typ (Einnahmen/Ausgaben/Ersparnisse)."""
        data: dict[str, List[Category]] = {
            "Einkommen": [],
            "Ausgaben": [],
            "Ersparnisse": [],
        }
        for c in self.list(None):
            data.setdefault(c.typ, []).append(c)
        return data

    def build_tree(self, items: List[Category]) -> List[dict]:
        """Baut aus flacher Liste eine Baumstruktur.

        Returns: Liste von Nodes {cat: Category, children: [...]}
        """
        by_id: dict[int, dict] = {}
        roots: List[dict] = []
        for c in items:
            by_id[c.id] = {"cat": c, "children": []}
        for c in items:
            node = by_id[c.id]
            if c.parent_id and c.parent_id in by_id:
                by_id[c.parent_id]["children"].append(node)
            else:
                roots.append(node)
        return roots

    @classmethod
    def _safe_table(cls, table: str) -> str:
        """Gibt einen geprüften internen Tabellennamen zurück.

        SQLite erlaubt für ``PRAGMA table_info`` und DDL-artige Stellen keine
        Platzhalter für Tabellen-/Spaltennamen. Deshalb dürfen dynamische
        Tabellennamen hier nur aus einer festen internen Whitelist kommen.
        Nutzerwerte laufen weiterhin ausschließlich über ``?``-Parameter.
        """
        if table not in cls._ALLOWED_SCHEMA_TABLES:
            raise ValueError(f"Nicht erlaubte Tabelle: {table}")
        return table

    def _cols(self, table: str) -> set[str]:
        try:
            safe_table = self._safe_table(table)
            cur = self.conn.execute(f"PRAGMA table_info({safe_table});")
            return {row[1] for row in cur.fetchall()}
        except Exception as e:
            logger.debug("_cols(%s) fehlgeschlagen: %s", table, e)
            return set()

    def list_names(self, typ: str) -> List[str]:
        cur = self.conn.execute(
            "SELECT name FROM categories WHERE typ=? ORDER BY name COLLATE NOCASE",
            (typ,),
        )
        return [r["name"] for r in cur.fetchall()]

    def list_names_tree(self, typ: str) -> List[tuple[str, str]]:
        """Hierarchische Namensliste für Dropdowns.

        Anzeige: Einrückung bleibt, aber ab Unterkategorie wird zusätzlich der direkte Parent angezeigt:
        z.B. "  Krankenkasse › Selbstbehalt".

        Returns: [(anzeige_text, echter_name), ...]
        """
        items = self.list(typ)
        nodes = self.build_tree(items)

        out: List[tuple[str, str]] = []

        def walk(children: List[dict], depth: int, parent_name: str | None) -> None:
            for n in children:
                c: Category = n["cat"]
                prefix = "  " * depth
                label = (
                    c.name
                    if depth == 0 or not parent_name
                    else f"{parent_name} › {c.name}"
                )
                out.append((f"{prefix}{label}", c.name))
                walk(n["children"], depth + 1, c.name)

        walk(nodes, 0, None)
        return out

    def list_for_tracking_dropdown(self, typ: str) -> List[tuple[str, str]]:
        """Kategorien-Reihenfolge für Buchungsdialoge.

        Flache Fallback-Liste ohne Kopfzeilen. Die eigentliche Tracker-UI nutzt
        ``list_for_tracking_dropdown_grouped``. Damit Fallback und UI fachlich
        gleich bleiben, wird die gruppierte Liste hier nur auf echte Einträge
        reduziert.
        """
        grouped = self.list_for_tracking_dropdown_grouped(typ)
        return [
            (label, str(value))
            for kind, label, value in grouped
            if kind == "item" and value
        ]

    def list_for_tracking_dropdown_grouped(
        self, typ: str
    ) -> List[tuple[str, str, object]]:
        """Gruppierte Reihenfolge für den Tracker-Picker.

        Liefert eine flache Liste aus Kopfzeilen und Einträgen:
            ("header", <Gruppentitel>, None)
            ("item",   <Anzeigelabel inkl. Baum-Pfad>, <echter Kategoriename>)

        Best-Practice für den Tracker:
        1. Favoriten stehen immer ganz oben.
        2. Normale, manuelle Buchungskategorien werden nach echter manueller
           Nutzung sortiert. Automatische Fix-/Wiederkehrend-Buchungen zählen
           dabei nicht.
        3. Fix-/Wiederkehrend-Kategorien bleiben sichtbar, aber in eigenen
           unteren Gruppen, damit Alltagsbuchungen nicht von Monatsautomatiken
           verdrängt werden.

        Kategorien erscheinen genau einmal. Unterkategorien behalten ihren
        Eltern-Pfad (z.B. "Wohnen › Miete").
        """
        items = self.list(typ)
        if not items:
            return []
        by_name = {c.name: c for c in items}

        # Baum-Pfade + Baum-Reihenfolge
        path_by_name: dict[str, str] = {}
        nodes = self.build_tree(items)
        tree_pos: dict[str, int] = {}

        def walk(children: List[dict], parent_path: str | None = None) -> None:
            for n in children:
                c: Category = n["cat"]
                path = c.name if not parent_path else f"{parent_path} › {c.name}"
                path_by_name[c.name] = path
                tree_pos[c.name] = len(tree_pos)
                walk(n.get("children", []) or [], path)

        walk(nodes)

        try:
            fav_rows = self.conn.execute(
                "SELECT category FROM favorites WHERE typ=? ORDER BY sort_order, category COLLATE NOCASE",
                (typ,),
            ).fetchall()
            fav_order = [str(r[0]) for r in fav_rows if str(r[0]) in by_name]
        except Exception as e:
            logger.debug("Favoriten für gruppierten Picker: %s", e)
            fav_order = []
        fav_set = set(fav_order)

        try:
            from model.tracking_model import TrackingModel

            usage = TrackingModel(self.conn).category_usage_counts(
                typ, manual_only=True
            )
        except Exception as e:
            logger.debug("Nutzungsranking für gruppierten Picker: %s", e)
            usage = {}

        def order_by_usage(names: List[str]) -> List[str]:
            return sorted(
                names,
                key=lambda n: (
                    -int(usage.get(n, 0)),
                    tree_pos.get(n, 1 << 30),
                    path_by_name.get(n, n).casefold(),
                ),
            )

        def order_by_tree(names: List[str]) -> List[str]:
            return sorted(
                names,
                key=lambda n: (
                    tree_pos.get(n, 1 << 30),
                    path_by_name.get(n, n).casefold(),
                ),
            )

        frequent_manual: List[str] = []
        normal_other: List[str] = []
        fix_variable: List[str] = []
        recurring_variable: List[str] = []
        real_fixcosts: List[str] = []

        for c in items:
            if c.name in fav_set:
                continue
            is_fix = bool(c.is_fix)
            is_rec = bool(c.is_recurring)
            if is_fix and is_rec:
                real_fixcosts.append(c.name)
            elif is_fix:
                fix_variable.append(c.name)
            elif is_rec:
                recurring_variable.append(c.name)
            else:
                if int(usage.get(c.name, 0)) > 0:
                    frequent_manual.append(c.name)
                else:
                    normal_other.append(c.name)

        out: List[tuple[str, str, object]] = []

        def _tr(title_key: str, default_title: str) -> str:
            try:
                from utils.i18n import tr

                title = tr(title_key)
                if title and title != title_key:
                    return title
            except Exception as e:
                logger.debug(
                    "Picker-Gruppentitel nicht übersetzt (%s): %s", title_key, e
                )
            return default_title

        def add_group(
            title_key: str,
            default_title: str,
            names: List[str],
            *,
            favorite: bool = False,
        ) -> None:
            if not names:
                return
            out.append(("header", _tr(title_key, default_title), None))
            for n in names:
                label = path_by_name.get(n, n)
                if favorite:
                    label = f"★ {label}"
                out.append(("item", label, n))

        add_group("picker.group_favorites", "★ Favoriten", fav_order, favorite=True)
        add_group(
            "picker.group_frequent_manual",
            "Häufig manuell gebucht",
            order_by_usage(frequent_manual),
        )
        add_group(
            "picker.group_normal", "Normale Buchungen", order_by_tree(normal_other)
        )
        add_group(
            "picker.group_variable_fix", "Fix / variabel", order_by_usage(fix_variable)
        )
        add_group(
            "picker.group_variable_recurring",
            "Wiederkehrend / variabel",
            order_by_usage(recurring_variable),
        )
        add_group(
            "picker.group_real_fixcosts",
            "Echte Fixkosten",
            order_by_usage(real_fixcosts),
        )
        return out

    def list_fix_names(self, typ: str) -> List[str]:
        cur = self.conn.execute(
            "SELECT name FROM categories WHERE typ=? AND is_fix=1 ORDER BY name COLLATE NOCASE",
            (typ,),
        )
        return [r["name"] for r in cur.fetchall()]

    def list_fix_names_tree(self, typ: str) -> List[tuple[str, str]]:
        items = [c for c in self.list(typ) if c.is_fix]
        nodes = self.build_tree(items)
        out: List[tuple[str, str]] = []

        def walk(children: List[dict], depth: int, parent_name: str | None) -> None:
            for n in children:
                c: Category = n["cat"]
                prefix = "  " * depth
                label = (
                    c.name
                    if depth == 0 or not parent_name
                    else f"{parent_name} › {c.name}"
                )
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
        prow = self.conn.execute(
            "SELECT name FROM categories WHERE id=?", (int(row["parent_id"]),)
        ).fetchone()
        return str(prow["name"]) if prow else None

    def exists(self, typ: str, name: str) -> bool:
        """True, wenn eine Kategorie mit Typ + Name existiert.

        Wird bewusst case-insensitive geprüft, weil Benutzer im Suchfeld einer
        editierbaren ComboBox tippen können. Gespeichert wird anschließend aber
        der echte Datenbankname aus ``resolve_name``.
        """
        name = (name or "").strip()
        if not typ or not name:
            return False
        row = self.conn.execute(
            "SELECT 1 FROM categories WHERE typ=? AND lower(name)=lower(?) LIMIT 1",
            (typ, name),
        ).fetchone()
        return row is not None

    def resolve_name(self, typ: str, name: str) -> str | None:
        """Liefert den exakten DB-Kategorienamen zu einer Benutzereingabe.

        Bei exact/case-insensitive Treffern wird der gespeicherte Name
        zurückgegeben. Ohne Treffer gibt die Methode ``None`` zurück.
        """
        name = (name or "").strip()
        if not typ or not name:
            return None
        row = self.conn.execute(
            "SELECT name FROM categories WHERE typ=? AND lower(name)=lower(?) LIMIT 1",
            (typ, name),
        ).fetchone()
        return str(row["name"]) if row else None

    def get_flags(self, typ: str, name: str) -> tuple[bool, bool, int]:
        """returns (is_fix, is_recurring, recurring_day). if missing -> (False, False, 1)"""
        cur = self.conn.execute(
            "SELECT is_fix, is_recurring, recurring_day FROM categories WHERE typ=? AND name=?",
            (typ, name),
        ).fetchone()
        if not cur:
            return (False, False, 1)
        return (
            bool(cur["is_fix"]),
            bool(cur["is_recurring"]),
            int(cur["recurring_day"] or 1),
        )

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
        if (
            "parent_id" in cols
            and "funded_by_category_id" in cols
            and "sort_order" in cols
        ):
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
                (
                    typ,
                    name,
                    parent_id,
                    int(is_fix),
                    int(is_recurring),
                    day,
                    funded_by_category_id,
                    int(sort_order),
                ),
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
        if (
            "parent_id" in cols
            and "funded_by_category_id" in cols
            and "sort_order" in cols
        ):
            cur = self.conn.execute(
                "INSERT INTO categories(typ,name,parent_id,is_fix,is_recurring,recurring_day,funded_by_category_id,sort_order) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    typ,
                    name,
                    parent_id,
                    int(is_fix),
                    int(is_recurring),
                    day,
                    funded_by_category_id,
                    int(sort_order),
                ),
            )
        else:
            cur = self.conn.execute(
                "INSERT INTO categories(typ,name,is_fix,is_recurring,recurring_day) VALUES(?,?,?,?,?)",
                (typ, name, int(is_fix), int(is_recurring), day),
            )
        self.conn.commit()
        new_id = int(cur.lastrowid)
        row = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (new_id,)
        ).fetchone()
        self.undo.record_operation(
            "categories", "INSERT", None, dict(row) if row else None
        )
        return new_id

    def update_flags(
        self,
        cat_id: int,
        *,
        is_fix: bool | None = None,
        is_recurring: bool | None = None,
        recurring_day: int | None = None,
    ) -> None:
        """Aktualisiert Flags (und optional den Tag) per ID + Undo/Redo."""
        old = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (int(cat_id),)
        ).fetchone()
        old_d = dict(old) if old else None

        fields: List[str] = []
        params: List[object] = []
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
        self.conn.execute(
            f"UPDATE categories SET {', '.join(fields)} WHERE id=?", params
        )
        self.conn.commit()

        new = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (int(cat_id),)
        ).fetchone()
        new_d = dict(new) if new else None
        if old_d != new_d:
            self.undo.record_operation("categories", "UPDATE", old_d, new_d)

    def _table_exists(self, table: str) -> bool:
        try:
            safe_table = self._safe_table(table)
            row = self.conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (safe_table,),
            ).fetchone()
            return row is not None
        except Exception as e:
            logger.debug("_table_exists(%s) fehlgeschlagen: %s", table, e)
            return False

    def get_category_usage(self, cat_id: int) -> dict[str, object]:
        """Liefert eine kompakte Auswirkungsanalyse für eine Kategorie-Löschung.

        Die App speichert viele Referenzen historisch noch per Kategorie-Name.
        Diese Methode ist deshalb die zentrale Stelle, an der die UI sehen kann,
        ob Budget, Buchungen, Favoriten, Warnungen usw. betroffen sind.
        """
        cat = self.get_by_id(int(cat_id))
        if not cat:
            return {"exists": False, "cat_id": int(cat_id)}

        typ, name = cat.typ, cat.name

        def count(table: str, where: str, params: tuple[object, ...]) -> int:
            if not self._table_exists(table):
                return 0
            try:
                return int(
                    self.conn.execute(
                        f"SELECT COUNT(*) FROM {table} WHERE {where}", params
                    ).fetchone()[0]
                    or 0
                )
            except Exception as e:
                logger.debug(
                    "get_category_usage count(%s) fehlgeschlagen: %s", table, e
                )
                return 0

        last_booking = None
        if self._table_exists("tracking"):
            row = self.conn.execute(
                "SELECT MAX(date) AS max_date FROM tracking WHERE typ=? AND category=?",
                (typ, name),
            ).fetchone()
            last_booking = row["max_date"] if row and row["max_date"] else None

        children = (
            count("categories", "parent_id=?", (int(cat_id),))
            if "parent_id" in self._cols("categories")
            else 0
        )
        return {
            "exists": True,
            "cat_id": int(cat.id),
            "typ": typ,
            "name": name,
            "children": children,
            "budget": count("budget", "typ=? AND category=?", (typ, name)),
            "tracking": count("tracking", "typ=? AND category=?", (typ, name)),
            "last_booking_date": last_booking,
            "favorites": count("favorites", "typ=? AND category=?", (typ, name)),
            "budget_warnings": count(
                "budget_warnings", "typ=? AND category=?", (typ, name)
            ),
            "recurring_transactions": count(
                "recurring_transactions", "typ=? AND category=?", (typ, name)
            ),
            "suggestion_accepted": count(
                "suggestion_accepted", "typ=? AND category=?", (typ, name)
            ),
            # Sparziele haben historisch keine typ-Spalte; deshalb nur für Ersparnisse hart zählen.
            "savings_goals": (
                count("savings_goals", "category=?", (name,))
                if typ == "Ersparnisse"
                else 0
            ),
            "category_tags": count("category_tags", "category_id=?", (int(cat_id),)),
        }

    def rename_and_cascade(
        self, cat_id: int, *, typ: str, old_name: str, new_name: str
    ) -> None:
        """Benennt eine Kategorie zentral um und aktualisiert alle bekannten Referenzen.

        Budgetmanager-Legacy-Tabellen referenzieren Kategorien noch per Text
        (typ + category). Deshalb darf Rename nie lokal in einer View passieren.
        Diese Methode ist die einzige erlaubte Rename-Quelle.
        """
        old_name = (old_name or "").strip()
        new_name = (new_name or "").strip()
        cat_id = int(cat_id)
        if not old_name or not new_name or old_name == new_name:
            return

        existing = self.conn.execute(
            "SELECT id FROM categories WHERE typ=? AND lower(name)=lower(?) AND id<>?",
            (typ, new_name, cat_id),
        ).fetchone()
        if existing:
            raise CategoryError("categories.category_exists", name=new_name)

        from model.database import db_transaction

        with db_transaction(self.conn):
            self.conn.execute(
                "UPDATE categories SET name=? WHERE id=?", (new_name, cat_id)
            )
            if self._table_exists("budget"):
                self.conn.execute(
                    "UPDATE budget SET category=? WHERE typ=? AND category=?",
                    (new_name, typ, old_name),
                )
            if self._table_exists("tracking"):
                self.conn.execute(
                    "UPDATE tracking SET category=? WHERE typ=? AND category=?",
                    (new_name, typ, old_name),
                )
            if self._table_exists("favorites"):
                self.conn.execute(
                    "UPDATE OR IGNORE favorites SET category=? WHERE typ=? AND category=?",
                    (new_name, typ, old_name),
                )
                self.conn.execute(
                    "DELETE FROM favorites WHERE typ=? AND category=?", (typ, old_name)
                )
            if self._table_exists("budget_warnings"):
                self.conn.execute(
                    "UPDATE OR IGNORE budget_warnings SET category=? WHERE typ=? AND category=?",
                    (new_name, typ, old_name),
                )
                self.conn.execute(
                    "DELETE FROM budget_warnings WHERE typ=? AND category=?",
                    (typ, old_name),
                )
            if self._table_exists("recurring_transactions"):
                self.conn.execute(
                    "UPDATE recurring_transactions SET category=? WHERE typ=? AND category=?",
                    (new_name, typ, old_name),
                )
            if self._table_exists("suggestion_accepted"):
                self.conn.execute(
                    "UPDATE OR IGNORE suggestion_accepted SET category=? WHERE typ=? AND category=?",
                    (new_name, typ, old_name),
                )
                self.conn.execute(
                    "DELETE FROM suggestion_accepted WHERE typ=? AND category=?",
                    (typ, old_name),
                )
            if typ == "Ersparnisse" and self._table_exists("savings_goals"):
                self.conn.execute(
                    "UPDATE savings_goals SET category=? WHERE category=?",
                    (new_name, old_name),
                )

        self.undo.record_operation(
            "categories",
            "RENAME_CASCADE",
            {"cat_id": cat_id, "typ": typ, "old_name": old_name},
            {"cat_id": cat_id, "typ": typ, "new_name": new_name},
        )

    def _move_category_text_references(
        self, *, typ: str, old_name: str, target_name: str, target_id: int
    ) -> None:
        """Hängt abhängige Daten von old_name auf target_name um.

        Budgetwerte werden additiv zusammengeführt, weil budget pro
        Jahr/Monat/Typ/Kategorie eindeutig ist. Tracking-Einträge können direkt
        umbenannt werden.
        """
        if self._table_exists("budget"):
            rows = self.conn.execute(
                "SELECT year, month, amount FROM budget WHERE typ=? AND category=?",
                (typ, old_name),
            ).fetchall()
            for r in rows:
                self.conn.execute(
                    """
                    INSERT INTO budget(year, month, typ, category, amount)
                    VALUES (?, ?, ?, ?, ?)
                    ON CONFLICT(year, month, typ, category)
                    DO UPDATE SET amount = amount + excluded.amount
                    """,
                    (
                        int(r["year"]),
                        int(r["month"]),
                        typ,
                        target_name,
                        float(r["amount"] or 0.0),
                    ),
                )
            self.conn.execute(
                "DELETE FROM budget WHERE typ=? AND category=?", (typ, old_name)
            )

        if self._table_exists("tracking"):
            self.conn.execute(
                "UPDATE tracking SET category=? WHERE typ=? AND category=?",
                (target_name, typ, old_name),
            )
        if self._table_exists("recurring_transactions"):
            self.conn.execute(
                "UPDATE recurring_transactions SET category=? WHERE typ=? AND category=?",
                (target_name, typ, old_name),
            )
        if self._table_exists("favorites"):
            self.conn.execute(
                "INSERT OR IGNORE INTO favorites(typ, category, sort_order) "
                "SELECT typ, ?, MIN(sort_order) FROM favorites WHERE typ=? AND category=? GROUP BY typ",
                (target_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM favorites WHERE typ=? AND category=?", (typ, old_name)
            )
        if self._table_exists("budget_warnings"):
            self.conn.execute(
                "INSERT OR IGNORE INTO budget_warnings(year, month, typ, category, threshold_percent, enabled) "
                "SELECT year, month, typ, ?, threshold_percent, enabled FROM budget_warnings WHERE typ=? AND category=?",
                (target_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM budget_warnings WHERE typ=? AND category=?",
                (typ, old_name),
            )
        if self._table_exists("suggestion_accepted"):
            self.conn.execute(
                "INSERT OR IGNORE INTO suggestion_accepted(typ, category, year, month, accepted_at) "
                "SELECT typ, ?, year, month, accepted_at FROM suggestion_accepted WHERE typ=? AND category=?",
                (target_name, typ, old_name),
            )
            self.conn.execute(
                "DELETE FROM suggestion_accepted WHERE typ=? AND category=?",
                (typ, old_name),
            )
        if typ == "Ersparnisse" and self._table_exists("savings_goals"):
            self.conn.execute(
                "UPDATE savings_goals SET category=? WHERE category=?",
                (target_name, old_name),
            )
        if self._table_exists("categories") and "funded_by_category_id" in self._cols(
            "categories"
        ):
            self.conn.execute(
                "UPDATE categories SET funded_by_category_id=? WHERE funded_by_category_id IN "
                "(SELECT id FROM categories WHERE typ=? AND name=?)",
                (int(target_id), typ, old_name),
            )

    def _delete_category_text_references(
        self, *, typ: str, name: str, delete_savings_goals: bool
    ) -> None:
        """Entfernt alle Text-Referenzen einer Kategorie ohne Zielkategorie."""
        if self._table_exists("tracking"):
            if self._table_exists("entry_tags"):
                self.conn.execute(
                    "DELETE FROM entry_tags WHERE entry_id IN "
                    "(SELECT id FROM tracking WHERE typ=? AND category=?)",
                    (typ, name),
                )
            self.conn.execute(
                "DELETE FROM tracking WHERE typ=? AND category=?", (typ, name)
            )
        for table in self._CATEGORY_TEXT_REFERENCE_TABLES:
            if self._table_exists(table):
                safe_table = self._safe_table(table)
                self.conn.execute(
                    f"DELETE FROM {safe_table} WHERE typ=? AND category=?", (typ, name)
                )
        if typ == "Ersparnisse" and self._table_exists("savings_goals"):
            if delete_savings_goals:
                self.conn.execute("DELETE FROM savings_goals WHERE category=?", (name,))
            else:
                self.conn.execute(
                    "UPDATE savings_goals SET category=NULL WHERE category=?", (name,)
                )

    def delete_category_safely(
        self,
        cat_id: int,
        *,
        data_action: str = "delete_until_last_booking",
        reassign_to_id: int | None = None,
        promote_children: bool = True,
    ) -> dict[str, object]:
        """Löscht eine Kategorie sicher.

        data_action:
        - ``delete_until_last_booking``: Buchungen/abhängige Budgetdaten der Kategorie entfernen;
          Sparziele bleiben erhalten, verlieren aber ihre Kategorie-Verknüpfung.
        - ``delete_all``: alle abhängigen Daten inklusive Sparziele löschen.
        - ``reassign``: alle abhängigen Daten auf ``reassign_to_id`` umhängen.

        Parent-Löschung: direkte Kinder werden standardmässig auf den Parent der
        gelöschten Kategorie gehoben, nicht gelöscht.
        """
        return self.delete_categories_safely(
            [int(cat_id)],
            data_action=data_action,
            reassign_to_id=reassign_to_id,
            promote_children=promote_children,
        )

    def delete_categories_safely(
        self,
        ids: List[int],
        *,
        data_action: str = "delete_until_last_booking",
        reassign_to_id: int | None = None,
        promote_children: bool = True,
    ) -> dict[str, object]:
        ids = sorted({int(i) for i in ids if i is not None})
        if not ids:
            return {"deleted": 0, "skipped": 0}
        if data_action not in {"delete_until_last_booking", "delete_all", "reassign"}:
            raise ValueError(f"Unbekannte Kategorie-Löschaktion: {data_action}")

        target = (
            self.get_by_id(int(reassign_to_id)) if reassign_to_id is not None else None
        )
        if data_action == "reassign":
            if target is None:
                raise CategoryError("category_delete.no_target")
            if int(target.id) in ids:
                raise CategoryError("category_delete.target_is_deleted")

        from model.database import db_transaction

        deleted = 0
        skipped = 0
        group = self.undo.new_group_id()
        undo_rows: List[dict] = []

        with db_transaction(self.conn):
            for cat_id in ids:
                cat = self.get_by_id(cat_id)
                if cat is None:
                    skipped += 1
                    continue
                if target is not None and cat.typ != target.typ:
                    raise CategoryError("category_delete.target_type_mismatch")

                old_row = self.conn.execute(
                    "SELECT * FROM categories WHERE id=?", (cat_id,)
                ).fetchone()
                old_d = dict(old_row) if old_row else None

                # Direkte Kinder hochziehen: Parent-Löschung löscht nicht automatisch den Unterbaum.
                if promote_children and "parent_id" in self._cols("categories"):
                    if ids:
                        q = ",".join(["?"] * len(ids))
                        self.conn.execute(
                            f"UPDATE categories SET parent_id=? WHERE parent_id=? AND id NOT IN ({q})",
                            [cat.parent_id, cat_id, *ids],
                        )
                    else:
                        self.conn.execute(
                            "UPDATE categories SET parent_id=? WHERE parent_id=?",
                            (cat.parent_id, cat_id),
                        )

                if data_action == "reassign" and target is not None:
                    self._move_category_text_references(
                        typ=cat.typ,
                        old_name=cat.name,
                        target_name=target.name,
                        target_id=int(target.id),
                    )
                    if self._table_exists("category_tags"):
                        self.conn.execute(
                            "INSERT OR IGNORE INTO category_tags(category_id, tag_id) "
                            "SELECT ?, tag_id FROM category_tags WHERE category_id=?",
                            (int(target.id), cat_id),
                        )
                        self.conn.execute(
                            "DELETE FROM category_tags WHERE category_id=?", (cat_id,)
                        )
                else:
                    self._delete_category_text_references(
                        typ=cat.typ,
                        name=cat.name,
                        delete_savings_goals=(data_action == "delete_all"),
                    )
                    if self._table_exists("category_tags"):
                        self.conn.execute(
                            "DELETE FROM category_tags WHERE category_id=?", (cat_id,)
                        )
                    if "funded_by_category_id" in self._cols("categories"):
                        self.conn.execute(
                            "UPDATE categories SET funded_by_category_id=NULL WHERE funded_by_category_id=?",
                            (cat_id,),
                        )

                self.conn.execute("DELETE FROM categories WHERE id=?", (cat_id,))
                deleted += 1
                if old_d:
                    undo_rows.append(old_d)

        for old_d in undo_rows:
            self.undo.record_operation(
                "categories", "DELETE_SAFE", old_d, None, group_id=group
            )

        return {"deleted": deleted, "skipped": skipped, "action": data_action}

    def delete(self, typ: str, name: str) -> None:
        row = self.conn.execute(
            "SELECT id FROM categories WHERE typ=? AND name=?", (typ, name)
        ).fetchone()
        if not row:
            return
        self.delete_category_safely(
            int(row["id"]), data_action="delete_until_last_booking"
        )

    def delete_by_ids(self, ids: List[int]) -> None:
        self.delete_categories_safely(ids, data_action="delete_until_last_booking")

    def get_by_id(self, cat_id: int) -> Category | None:
        """Einzelne Kategorie per ID (oder None)."""
        r = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (int(cat_id),)
        ).fetchone()
        if r is None:
            return None
        return Category(
            int(r["id"]),
            r["typ"],
            r["name"],
            (
                int(r["parent_id"])
                if "parent_id" in r.keys() and r["parent_id"] is not None
                else None
            ),
            bool(r["is_fix"]),
            bool(r["is_recurring"]),
            int(r["recurring_day"] or 1),
            (
                int(r["funded_by_category_id"])
                if "funded_by_category_id" in r.keys()
                and r["funded_by_category_id"] is not None
                else None
            ),
            (
                int(r["sort_order"])
                if "sort_order" in r.keys() and r["sort_order"] is not None
                else 0
            ),
        )

    def _descendant_ids(self, cat_id: int) -> set[int]:
        """Alle Nachfahren-IDs (rekursiv) einer Kategorie."""
        cols = self._cols("categories")
        if "parent_id" not in cols:
            return set()
        result: set[int] = set()
        frontier = [int(cat_id)]
        while frontier:
            current = frontier.pop()
            rows = self.conn.execute(
                "SELECT id FROM categories WHERE parent_id=?", (current,)
            ).fetchall()
            for r in rows:
                cid = int(r["id"])
                if cid not in result:
                    result.add(cid)
                    frontier.append(cid)
        return result

    def can_reparent(self, cat_id: int, new_parent_id: int | None) -> tuple[bool, str]:
        """Prüft, ob ``cat_id`` unter ``new_parent_id`` verschoben werden darf.

        Returns (ok, reason_key). ``reason_key`` ist ein i18n-Schlüssel, der bei
        ``ok=False`` erklärt, warum der Verschiebe-Vorgang nicht erlaubt ist.
        """
        cat_id = int(cat_id)
        if new_parent_id is None:
            return True, ""
        new_parent_id = int(new_parent_id)

        if new_parent_id == cat_id:
            return False, "catmgr.move_err_self"

        cur = self.conn.execute(
            "SELECT typ FROM categories WHERE id=?", (cat_id,)
        ).fetchone()
        par = self.conn.execute(
            "SELECT typ FROM categories WHERE id=?", (new_parent_id,)
        ).fetchone()
        if cur is None or par is None:
            return False, "catmgr.move_err_missing"
        if cur["typ"] != par["typ"]:
            return False, "catmgr.move_err_type"

        # Zyklus: Ziel darf kein Nachfahre der bewegten Kategorie sein.
        if new_parent_id in self._descendant_ids(cat_id):
            return False, "catmgr.move_err_cycle"

        return True, ""

    def update_parent(self, cat_id: int, new_parent_id: int | None) -> None:
        cols = self._cols("categories")
        if "parent_id" not in cols:
            return

        # Defensive Validierung – verhindert Zyklen / Typ-Mischung auch dann,
        # wenn ein Aufrufer die Prüfung über can_reparent() übersprungen hat.
        ok, reason = self.can_reparent(cat_id, new_parent_id)
        if not ok:
            raise CategoryError(reason)

        old = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (int(cat_id),)
        ).fetchone()
        old_d = dict(old) if old else None

        self.conn.execute(
            "UPDATE categories SET parent_id=? WHERE id=?",
            (None if new_parent_id is None else int(new_parent_id), int(cat_id)),
        )
        self.conn.commit()

        new = self.conn.execute(
            "SELECT * FROM categories WHERE id=?", (int(cat_id),)
        ).fetchone()
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

    def count(self) -> int:
        """Anzahl der Kategorien in der Datenbank."""
        row = self.conn.execute("SELECT COUNT(*) FROM categories").fetchone()
        return int(row[0]) if row else 0

    def delete_all(self) -> None:
        """Löscht alle Kategorien (für Reset/Setup)."""
        self.conn.execute("DELETE FROM categories")
        self.conn.commit()
