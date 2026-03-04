"""Zentrale Verwaltung der Tastenkürzel (Defaults + benutzerdefinierte Overrides).

Jeder Shortcut hat eine `action_id` (interner Schlüssel), ein
Standard-Kürzel (`default_key`) und eine Beschreibung (`label`).

Benutzerdefinierte Overrides werden unter dem Settings-Key ``"shortcuts"``
als ``{action_id: key_string}`` gespeichert.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# ── Shortcut-Definitionen ──────────────────────────────────────────
# Jedes Tupel: (action_id, default_key, label, group)
# `group` dient nur zur optischen Gruppierung in Hilfe / Settings.

SHORTCUT_DEFS: list[tuple[str, str, str, str]] = [
    # --- Allgemein ---
    ("help",           "F1",           "Hilfe / Tastenkürzel anzeigen",  "Allgemein"),
    ("refresh",        "F5",           "Aktuelle Ansicht aktualisieren", "Allgemein"),
    ("save",           "Ctrl+S",       "Budget speichern",               "Allgemein"),
    ("settings",       "Ctrl+,",       "Einstellungen öffnen",           "Allgemein"),
    ("quit",           "Ctrl+Q",       "Programm beenden",               "Allgemein"),
    # --- Navigation ---
    ("tab_budget",     "Ctrl+1",       "Zum Budget-Tab wechseln",        "Navigation"),
    ("tab_categories", "Ctrl+2",       "Zum Kategorien-Tab wechseln",    "Navigation"),
    ("tab_tracking",   "Ctrl+3",       "Zum Tracking-Tab wechseln",      "Navigation"),
    ("tab_overview",   "Ctrl+4",       "Zur Übersicht wechseln",         "Navigation"),
    # --- Funktionen ---
    ("current_year",   "Ctrl+Y",       "Aktuelles Jahr laden",           "Funktionen"),
    ("search",         "Ctrl+F",       "Globale Suche öffnen",           "Funktionen"),
    ("quick_add",      "Ctrl+N",       "Schnelleingabe (Quick-Add)",     "Funktionen"),
    ("undo",           "Ctrl+Z",       "Rückgängig (Undo)",              "Funktionen"),
    ("redo",           "Ctrl+Shift+Z", "Wiederholen (Redo)",             "Funktionen"),
    ("export",         "Ctrl+E",       "Export-Dialog öffnen",           "Funktionen"),
    ("import",         "Ctrl+I",       "Import-Dialog öffnen",           "Funktionen"),
    ("favorites",      "F12",          "Favoriten-Übersicht",            "Funktionen"),
    ("fullscreen",     "F11",          "Vollbild umschalten",            "Funktionen"),
    ("maximize",       "F10",          "Fenster maximieren",             "Funktionen"),
]

# Schneller Lookup: action_id → (default_key, label, group)
_LOOKUP: dict[str, tuple[str, str, str]] = {
    aid: (key, label, grp) for aid, key, label, grp in SHORTCUT_DEFS
}


def default_key(action_id: str) -> str:
    """Gibt das Standard-Kürzel für *action_id* zurück (oder ``""``).
    """
    entry = _LOOKUP.get(action_id)
    return entry[0] if entry else ""


def label_for(action_id: str) -> str:
    """Beschreibungstext für *action_id*."""
    entry = _LOOKUP.get(action_id)
    return entry[1] if entry else action_id


def group_for(action_id: str) -> str:
    """Gruppenname für *action_id*."""
    entry = _LOOKUP.get(action_id)
    return entry[2] if entry else ""


def all_action_ids() -> list[str]:
    """Alle definierten Action-IDs in Reihenfolge."""
    return [aid for aid, *_ in SHORTCUT_DEFS]


# ── Load / Save (Settings-Integration) ─────────────────────────────

def load_shortcuts(settings: Any) -> dict[str, str]:
    """Liefert ein vollständiges Mapping *action_id → key_string*.

    Merkt benutzerdefinierte Overrides aus ``settings.get("shortcuts")``.
    Fehlende oder ungültige Einträge werden mit Defaults ergänzt.
    """
    overrides: dict[str, str] = {}
    try:
        raw = settings.get("shortcuts", {})
        if isinstance(raw, dict):
            overrides = {k: str(v) for k, v in raw.items()}
    except Exception as exc:
        logger.debug("Shortcuts aus Settings laden: %s", exc)

    result: dict[str, str] = {}
    for aid, dkey, _label, _grp in SHORTCUT_DEFS:
        result[aid] = overrides.get(aid, dkey)
    return result


def save_shortcuts(settings: Any, mapping: dict[str, str]) -> None:
    """Speichert nur die *vom Default abweichenden* Kürzel in den Settings."""
    overrides: dict[str, str] = {}
    for aid, key in mapping.items():
        dk = default_key(aid)
        if key != dk:
            overrides[aid] = key
    settings.set("shortcuts", overrides)


def shortcut_display_name(key_string: str) -> str:
    """Wandelt Qt-Key-Strings in lesbare deutsche Bezeichnungen um.

    ``"Ctrl+S"`` → ``"Strg+S"``
    """
    return (
        key_string
        .replace("Ctrl", "Strg")
        .replace("Shift", "Umschalt")
        .replace("Alt", "Alt")
    )
