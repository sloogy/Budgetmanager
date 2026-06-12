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


def load_default_categories() -> list[DefaultCategory]:
    """Lädt die Default-Kategorien aus der JSON-Quelle (mit Fallback)."""
    for path in _candidate_paths():
        try:
            if not path.exists():
                continue
            raw = json.loads(path.read_text(encoding="utf-8"))
            cats = raw.get("categories", [])
            out: list[DefaultCategory] = []
            for c in cats:
                typ = str(c.get("typ", "")).strip()
                name = str(c.get("name", "")).strip()
                if typ not in ALL_TYPEN or not name:
                    logger.warning("default_categories.json: Eintrag übersprungen (typ=%r, name=%r)", typ, name)
                    continue
                if not c.get("enabled", True):
                    continue
                out.append(DefaultCategory(
                    typ=typ,
                    name=name,
                    is_fix=bool(c.get("is_fix", False)),
                    is_recurring=bool(c.get("is_recurring", False)),
                    recurring_day=int(c.get("recurring_day", 1) or 1),
                ))
            if out:
                logger.info("Default-Kategorien geladen: %d aus %s", len(out), path)
                return out
            logger.warning("default_categories.json gefunden, aber leer/ungültig: %s", path)
        except Exception as e:
            logger.warning("default_categories.json konnte nicht geladen werden (%s): %s", path, e)
    logger.warning("Keine gültige default_categories.json gefunden — eingebauter Fallback wird verwendet")
    return list(_FALLBACK)
