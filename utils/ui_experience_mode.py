"""ADHS-freundliche Bedienmodi für die Hauptoberfläche.

Der Modus entfernt keine Funktionen. Er setzt nur nachvollziehbare Sichtbarkeits-
und Cockpit-Presets. Manuelle Anpassungen bleiben als ``custom`` erkennbar.
Das Modul ist Qt-frei und deshalb leicht testbar.
"""

from __future__ import annotations

from utils.cockpit_presets import PRESETS

MODE_SIMPLE = "simple"
MODE_ADVANCED = "advanced"
MODE_CUSTOM = "custom"
VALID_MODES = {MODE_SIMPLE, MODE_ADVANCED, MODE_CUSTOM}

_SIMPLE_VISIBILITY = {
    "cockpit": True,
    "budget": True,
    "categories": False,
    "tracking": True,
    "overview": True,
    "savings": False,
}
_ADVANCED_VISIBILITY = {
    "cockpit": True,
    "budget": True,
    "categories": True,
    "tracking": True,
    "overview": True,
    "savings": True,
}


def normalise_mode(value: object) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode in VALID_MODES else MODE_CUSTOM


def mode_payload(mode: str) -> dict[str, object]:
    """Liefert alle zusammengehörigen Settings für einen Bedienmodus."""
    mode = normalise_mode(mode)
    if mode == MODE_SIMPLE:
        return {
            "ui_experience_mode": MODE_SIMPLE,
            "show_categories_tab": False,
            "tab_visibility": dict(_SIMPLE_VISIBILITY),
            "cockpit_preset": "focus",
            "cockpit_visible_panels": dict(PRESETS["focus"]),
        }
    if mode == MODE_ADVANCED:
        return {
            "ui_experience_mode": MODE_ADVANCED,
            "show_categories_tab": True,
            "tab_visibility": dict(_ADVANCED_VISIBILITY),
            "cockpit_preset": "standard",
            "cockpit_visible_panels": dict(PRESETS["standard"]),
        }
    return {"ui_experience_mode": MODE_CUSTOM}


def detect_mode(settings) -> str:
    """Erkennt den tatsächlich wirksamen Modus statt nur einem Label zu trauen."""
    visibility = dict(settings.get("tab_visibility", {}) or {})
    show_categories = bool(settings.get("show_categories_tab", False))
    preset = str(settings.get("cockpit_preset", "focus") or "focus")

    simple_matches = (
        all(
            bool(visibility.get(key, expected)) is expected
            for key, expected in _SIMPLE_VISIBILITY.items()
        )
        and not show_categories
    )
    if simple_matches and preset == "focus":
        return MODE_SIMPLE

    advanced_matches = (
        all(
            bool(visibility.get(key, expected)) is expected
            for key, expected in _ADVANCED_VISIBILITY.items()
        )
        and show_categories
    )
    if advanced_matches and preset in {"standard", "analysis"}:
        return MODE_ADVANCED

    return MODE_CUSTOM
