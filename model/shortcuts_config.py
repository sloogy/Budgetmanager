"""Zentrale Verwaltung der Tastenkürzel (Defaults + benutzerdefinierte Overrides).

Jeder Shortcut hat eine `action_id` (interner Schlüssel), ein
Standard-Kürzel (`default_key`) und eine Beschreibung (`label`).

Benutzerdefinierte Overrides werden unter dem Settings-Key ``"shortcuts"``
als ``{action_id: key_string}`` gespeichert.
"""

from __future__ import annotations

import logging
from typing import Any

from utils.i18n import tr

logger = logging.getLogger(__name__)

# ── Shortcut-Definitionen ──────────────────────────────────────────
# Jedes Tupel: (action_id, default_key, label_key, group_key)
# Label und Gruppe sind i18n-Keys. Dadurch bleiben Settings- und Hilfe-Dialog
# in DE/EN/FR vollständig übersetzt.

SHORTCUT_DEFS: list[tuple[str, str, str, str]] = [
    # --- General ---
    ("help", "F1", "shortcut.action.help", "shortcut.group.general"),
    ("shortcuts", "Ctrl+F1", "shortcut.action.shortcuts", "shortcut.group.general"),
    ("refresh", "F5", "shortcut.action.refresh", "shortcut.group.general"),
    ("save", "Ctrl+S", "shortcut.action.save", "shortcut.group.general"),
    ("settings", "Ctrl+,", "shortcut.action.settings", "shortcut.group.general"),
    ("quit", "Ctrl+Q", "shortcut.action.quit", "shortcut.group.general"),
    # --- Navigation ---
    ("tab_budget", "Ctrl+1", "shortcut.action.tab_budget", "shortcut.group.navigation"),
    ("tab_categories", "Ctrl+2", "shortcut.action.tab_categories", "shortcut.group.navigation"),
    ("tab_tracking", "Ctrl+3", "shortcut.action.tab_tracking", "shortcut.group.navigation"),
    ("tab_overview", "Ctrl+4", "shortcut.action.tab_overview", "shortcut.group.navigation"),
    # --- Functions ---
    ("current_year", "Ctrl+Y", "shortcut.action.current_year", "shortcut.group.functions"),
    ("search", "Ctrl+F", "shortcut.action.search", "shortcut.group.functions"),
    ("quick_add", "Ctrl+N", "shortcut.action.quick_add", "shortcut.group.functions"),
    ("undo", "Ctrl+Z", "shortcut.action.undo", "shortcut.group.functions"),
    ("redo", "Ctrl+Shift+Z", "shortcut.action.redo", "shortcut.group.functions"),
    ("export", "Ctrl+E", "shortcut.action.export", "shortcut.group.functions"),
    ("import", "Ctrl+I", "shortcut.action.import", "shortcut.group.functions"),
    ("favorites", "F12", "shortcut.action.favorites", "shortcut.group.functions"),
    ("fullscreen", "F11", "shortcut.action.fullscreen", "shortcut.group.functions"),
    ("maximize", "F10", "shortcut.action.maximize", "shortcut.group.functions"),
]

# Schneller Lookup: action_id → (default_key, label_key, group_key)
_LOOKUP: dict[str, tuple[str, str, str]] = {
    aid: (key, label_key, group_key) for aid, key, label_key, group_key in SHORTCUT_DEFS
}


def default_key(action_id: str) -> str:
    """Gibt das Standard-Kürzel für *action_id* zurück (oder ``""``)."""
    entry = _LOOKUP.get(action_id)
    return entry[0] if entry else ""


def label_key_for(action_id: str) -> str:
    """i18n-Key für den Beschreibungstext von *action_id*."""
    entry = _LOOKUP.get(action_id)
    return entry[1] if entry else action_id


def group_key_for(action_id: str) -> str:
    """i18n-Key für den Gruppennamen von *action_id*."""
    entry = _LOOKUP.get(action_id)
    return entry[2] if entry else ""


def label_for(action_id: str) -> str:
    """Lokalisierter Beschreibungstext für *action_id*."""
    return tr(label_key_for(action_id)) if action_id in _LOOKUP else action_id


def group_for(action_id: str) -> str:
    """Lokalisierter Gruppenname für *action_id*."""
    key = group_key_for(action_id)
    return tr(key) if key else ""


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
    """Wandelt Qt-Key-Strings in lokalisierte Anzeige-Bezeichnungen um."""
    if not key_string:
        return ""
    replacements = {
        "Ctrl": tr("shortcut.key.ctrl"),
        "Control": tr("shortcut.key.ctrl"),
        "Shift": tr("shortcut.key.shift"),
        "Alt": tr("shortcut.key.alt"),
        "Meta": tr("shortcut.key.meta"),
    }
    return "+".join(replacements.get(part, part) for part in key_string.split("+"))
