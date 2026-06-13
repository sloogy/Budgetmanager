"""Zentrale Quelle für Default-Kategorien (v1.0.30, P1.2).

Vorher existierten DREI unabhängige Definitionen mit unterschiedlichen Listen:
    1. CategoryModel.ensure_defaults()            (hardcodiert, inkl. persönlicher
                                                   Einträge und Tippfehler)
    2. DatabaseManagementModel.DEFAULT_CATEGORIES (hardcodiert, andere Liste)
    3. data/default_categories.json               (Release-Quelle)

Erststart und Reset erzeugten dadurch unterschiedliche Kategorien.

Ab jetzt gilt: ``data/default_categories.json`` ist die EINZIGE Quelle.
Diese Datei wird im PyInstaller-Build mitgeliefert (siehe BudgetManager.spec,
``datas``). Nur wenn sie fehlt oder defekt ist, greift die eingebaute
generische Minimal-Liste als Fallback — damit die App nie ohne Kategorien
startet.

DB-Konvention: ``typ`` ist ein DB-Schlüssel (Einkommen/Ausgaben/Ersparnisse,
siehe model/typ_constants.py) und wird nie übersetzt.
"""
from __future__ import annotations

import json
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, ALL_TYPEN

logger = logging.getLogger(__name__)

_JSON_NAME = "default_categories.json"


@dataclass(frozen=True)
class DefaultCategory:
    typ: str
    name: str
    is_fix: bool = False
    is_recurring: bool = False
    recurring_day: int = 1
    enabled: bool = True
    children: tuple["DefaultCategory", ...] = ()


# Eingebauter Fallback — bewusst klein, generisch und tippfehlerfrei.
_FALLBACK: tuple[DefaultCategory, ...] = (
    DefaultCategory(TYP_INCOME, "Lohn (Netto)", is_recurring=True, recurring_day=25),
    DefaultCategory(TYP_INCOME, "Nebenverdienst"),
    DefaultCategory(TYP_INCOME, "Sonstige Einnahmen"),
    DefaultCategory(TYP_EXPENSES, "Miete/Hypothek", is_fix=True, is_recurring=True),
    DefaultCategory(TYP_EXPENSES, "Nebenkosten", is_fix=True, is_recurring=True),
    DefaultCategory(TYP_EXPENSES, "Krankenversicherung", is_fix=True, is_recurring=True),
    DefaultCategory(TYP_EXPENSES, "Versicherungen", is_fix=True, is_recurring=True),
    DefaultCategory(TYP_EXPENSES, "Steuern", is_fix=True, is_recurring=True),
    DefaultCategory(TYP_EXPENSES, "Lebensmittel"),
    DefaultCategory(TYP_EXPENSES, "Transport"),
    DefaultCategory(TYP_EXPENSES, "Freizeit"),
    DefaultCategory(TYP_SAVINGS, "Rücklagen"),
    DefaultCategory(TYP_SAVINGS, "Ferien"),
    DefaultCategory(TYP_SAVINGS, "Altersvorsorge", is_recurring=True),
)


def _candidate_paths() -> list[Path]:
    """Mögliche Speicherorte der JSON-Quelle (Dev, Frozen-Bundle)."""
    paths = []
    # 1. Projekt-Root bzw. PyInstaller-Bundle (_MEIPASS via __file__-Auflösung)
    paths.append(Path(__file__).resolve().parents[1] / "data" / _JSON_NAME)
    # 2. Explizit _MEIPASS (Onefile-Build)
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        paths.append(Path(meipass) / "data" / _JSON_NAME)
    # 3. Portable: data/-Ordner neben der EXE (erlaubt Nutzer-Anpassung)
    try:
        from model.app_paths import app_dir
        paths.append(app_dir() / "data" / _JSON_NAME)
    except Exception as e:
        logger.debug("app_dir() für default_categories nicht verfügbar: %s", e)
    return paths


def _parse_entry(c: dict, parent_typ: str | None = None) -> DefaultCategory | None:
    """Parst einen Kategorie-Eintrag inkl. (rekursiv) seiner Unterkategorien.

    Kinder erben den ``typ`` des Eltern-Eintrags, falls sie keinen eigenen haben.
    Deaktivierte Einträge (``enabled: false``) werden übersprungen.
    """
    typ = str(c.get("typ", parent_typ or "")).strip()
    name = str(c.get("name", "")).strip()
    if typ not in ALL_TYPEN or not name:
        logger.warning("default_categories.json: Eintrag übersprungen (typ=%r, name=%r)", typ, name)
        return None
    if not c.get("enabled", True):
        return None

    children_raw = c.get("children", []) or []
    children: list[DefaultCategory] = []
    for child in children_raw:
        parsed = _parse_entry(child, parent_typ=typ)
        if parsed is not None:
            children.append(parsed)

    return DefaultCategory(
        typ=typ,
        name=name,
        is_fix=bool(c.get("is_fix", False)),
        is_recurring=bool(c.get("is_recurring", False)),
        recurring_day=int(c.get("recurring_day", 1) or 1),
        children=tuple(children),
    )


def load_default_categories() -> list[DefaultCategory]:
    """Lädt die Default-Kategorien aus der JSON-Quelle (mit Fallback).

    Rückgabe ist eine Liste der **Top-Level**-Kategorien; Unterkategorien hängen
    rekursiv unter ``DefaultCategory.children``.
    """
    for path in _candidate_paths():
        try:
            if not path.exists():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            cats = raw.get("categories", [])
            out: list[DefaultCategory] = []
            for c in cats:
                parsed = _parse_entry(c)
                if parsed is not None:
                    out.append(parsed)
            if out:
                total = sum(1 + len(d.children) for d in out)
                logger.info("Default-Kategorien geladen: %d Top-Level (%d gesamt) aus %s",
                            len(out), total, path)
                return out
            logger.warning("default_categories.json gefunden, aber leer/ungültig: %s", path)
        except Exception as e:
            logger.warning("default_categories.json konnte nicht geladen werden (%s): %s", path, e)
    logger.warning("Keine gültige default_categories.json gefunden — eingebauter Fallback wird verwendet")
    return list(_FALLBACK)


def insert_default_categories(conn) -> int:
    """Fügt die Default-Kategorien inkl. Unterkategorien in die DB ein.

    Gemeinsame Routine für Erststart (``ensure_defaults``) und Reset, damit beide
    Pfade nie wieder auseinanderlaufen. Eigenschaften:

    - Parents werden zuerst eingefügt, danach ihre Kinder mit gesetztem ``parent_id``.
    - ``INSERT OR IGNORE`` (Tabelle hat ``UNIQUE(typ, name)``) → idempotent.
    - Schema-tolerant: nutzt ``parent_id``/``sort_order`` nur, wenn die Spalten
      existieren. Auf Alt-Schemata ohne ``parent_id`` werden Unterkategorien als
      flache Top-Level-Einträge angelegt (kein Datenverlust).

    Gibt die Anzahl tatsächlich neu eingefügter Kategorien zurück.
    """
    tree = load_default_categories()
    cols = {r[1] for r in conn.execute("PRAGMA table_info(categories)").fetchall()}
    has_tree = {"parent_id", "sort_order", "funded_by_category_id"} <= cols
    has_flags = {"is_fix", "is_recurring", "recurring_day"} <= cols

    cur = conn.cursor()
    inserted = 0

    def _insert(dc: DefaultCategory, parent_id: int | None, sort_order: int) -> None:
        nonlocal inserted
        if has_tree:
            cur.execute(
                "INSERT OR IGNORE INTO categories"
                "(typ,name,parent_id,is_fix,is_recurring,recurring_day,funded_by_category_id,sort_order) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (dc.typ, dc.name, parent_id, int(dc.is_fix), int(dc.is_recurring),
                 int(dc.recurring_day), None, sort_order),
            )
        elif has_flags:
            cur.execute(
                "INSERT OR IGNORE INTO categories(typ,name,is_fix,is_recurring,recurring_day) "
                "VALUES(?,?,?,?,?)",
                (dc.typ, dc.name, int(dc.is_fix), int(dc.is_recurring), int(dc.recurring_day)),
            )
        else:
            cur.execute("INSERT OR IGNORE INTO categories(typ,name) VALUES(?,?)", (dc.typ, dc.name))

        if cur.rowcount and cur.rowcount > 0:
            inserted += 1

        # parent_id für die Kinder ermitteln (auch wenn der Eintrag schon existierte)
        row = conn.execute(
            "SELECT id FROM categories WHERE typ=? AND name=?", (dc.typ, dc.name)
        ).fetchone()
        cat_id = (row[0] if not hasattr(row, "keys") else row["id"]) if row else None

        for j, child in enumerate(dc.children):
            # Ohne parent_id-Spalte: Kind als Top-Level einfügen (parent_id bleibt None)
            _insert(child, cat_id if has_tree else None, j)

    for i, dc in enumerate(tree):
        _insert(dc, None, i)

    logger.info("Default-Kategorien eingefügt: %d neu", inserted)
    return inserted
