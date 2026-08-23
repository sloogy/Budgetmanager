"""Cockpit-Presets und Panel-Sichtbarkeit – Qt-frei und damit auditierbar.

v2.2.22 (UI/ADHS-Audit): Vorher lagen drei widersprüchliche Wahrheiten im
Code – die Preset-Maps im Cockpit-Tab, eine abweichende Default-Map in
``settings.py`` und eine v2.2.14-Zwangsmigration, die im Konstruktor IMMER
alle Panels materialisierte. Folgen:

1. Eine **Neuinstallation** stand laut Setting im "Fokus"-Preset, sichtbar
   waren aber ALLE Panels (die v2014-Migration schrieb die ALL-TRUE-Defaults
   fest) – der beworbene reduzierte Einstieg wirkte nie, und die Preset-Combo
   zeigte einen Zustand an, der nicht stimmte.
2. Ein **Panel-Toggle im Fokus-Modus** mischte über ``{**PANEL_DEFAULTS,
   **cfg}`` die ALL-TRUE-Basis ein: ein einziger Klick liess plötzlich
   Favoriten, Budget-Ampel und "Zuletzt gebucht" zusätzlich erscheinen.

Dieses Modul ist jetzt die EINE Wahrheit. ``settings.py`` bezieht seinen
Default von hier, der Cockpit-Tab delegiert hierher, und
``tools/ui_adhs_audit_1000.py`` spielt die Szenarien mit einem
Settings-Stub in 100 Loops real durch.

Semantik:
- ``preset != "custom"`` ⇒ die Sichtbarkeit folgt IMMER der Preset-Map.
- Jede manuelle Panel-Änderung wechselt auf ``custom`` und friert den dann
  wirksamen Zustand ein.
- Bestehende Nutzer (gespeicherte Panel-Auswahl oder Alt-Bestand ohne
  Preset-Feature) behalten ihr Erlebnis: ``custom`` + bisherige bzw.
  ALL-TRUE-Sichtbarkeit.
- Die v2014-Migration ("Warnbereiche wieder einblenden") gilt nur noch für
  ``custom``-Bestand mit vorhandener Konfiguration – ein Preset kippt sie
  nie mehr.
"""

from __future__ import annotations

from utils.defensive_log import uebersprungen as _uebersprungen

PANEL_KEYS = (
    "kpis",
    "quick_actions",
    "action_needed",
    "charts",
    "favorites",
    "savings",
    "recent",
)

# v2.2.40: Warnungen, Budget-Ampel und fehlende Buchungen beantworten alle
# dieselbe Frage ("muss ich etwas tun?") und bilden jetzt EINEN Abschnitt.
# Alt-Konfigurationen werden gemappt: war einer der drei sichtbar, ist der
# gebündelte Abschnitt sichtbar.
LEGACY_PANEL_MAP: dict[str, str] = {
    "warnings": "action_needed",
    "budget_warnings": "action_needed",
    "missing": "action_needed",
}


def migrate_panel_keys(cfg: dict[str, bool]) -> dict[str, bool]:
    """Übersetzt eine gespeicherte Panel-Auswahl auf die aktuellen Schlüssel."""
    if not isinstance(cfg, dict):
        return {}
    merged = {key: bool(value) for key, value in cfg.items() if key in PANEL_KEYS}
    legacy = [cfg[old] for old in LEGACY_PANEL_MAP if old in cfg]
    if legacy and "action_needed" not in merged:
        merged["action_needed"] = any(bool(value) for value in legacy)
    return merged


_ALL_TRUE: dict[str, bool] = {k: True for k in PANEL_KEYS}

PRESETS: dict[str, dict[str, bool]] = {
    # ADHS-freundlicher, reduzierter Einstieg: das Wesentliche zuerst.
    "focus": {
        "kpis": True,
        "quick_actions": True,
        "action_needed": True,
        "charts": True,
        "favorites": False,
        "savings": True,
        "recent": False,
    },
    "standard": dict(_ALL_TRUE),
    "analysis": dict(_ALL_TRUE),
}

_MIGRATION_MARKER = "cockpit_warnings_visible_migrated_v2014"


def _stored_panels(settings) -> dict[str, bool] | None:
    cfg = settings.get("cockpit_visible_panels", None)
    if not isinstance(cfg, dict) or not cfg:
        return None
    cfg = migrate_panel_keys(cfg)
    if not cfg:
        return None
    return {k: bool(cfg.get(k, True)) for k in PANEL_KEYS}


def current_preset(settings) -> str:
    preset = str(settings.get("cockpit_preset", "focus") or "focus")
    return preset if preset in (*PRESETS, "custom") else "focus"


def effective_panels(settings) -> dict[str, bool]:
    """Die tatsächlich wirksame Sichtbarkeit – Preset-Map oder Custom-Zustand."""
    preset = current_preset(settings)
    if preset != "custom":
        return dict(PRESETS[preset])
    stored = _stored_panels(settings)
    # Custom ohne gespeicherte Auswahl = Alt-Bestand: bisheriges Erlebnis
    # war "alles sichtbar".
    return stored if stored is not None else dict(_ALL_TRUE)


def materialize_initial(settings) -> None:
    """Beim Start: Sichtbarkeit konsistent zum Preset materialisieren.

    - Preset aktiv und keine Panels gespeichert ⇒ Preset-Map festschreiben
      (Neuinstallation startet damit WIRKLICH im Fokus-Layout).
    - ``custom`` ohne gespeicherte Panels (Alt-Bestand) ⇒ ALL-TRUE
      festschreiben, damit sich für Bestandsnutzer nichts ändert.
    - Gespeicherte Panels bleiben in jedem Fall unangetastet.
    """
    if _stored_panels(settings) is not None:
        return
    settings.set("cockpit_visible_panels", effective_panels(settings))


def migrate_v2014(settings) -> None:
    """Alt-Migration "Warnbereiche einblenden" – nur noch für Custom-Bestand.

    Früher lief das bedingungslos im Konstruktor und überschrieb damit auch
    frisch materialisierte Presets (Fokus wirkte nie). Jetzt: nur wenn der
    Nutzer im ``custom``-Modus ist UND bereits eine eigene Auswahl existiert.
    """
    try:
        if settings.get(_MIGRATION_MARKER, False):
            return
        if current_preset(settings) != "custom":
            # Preset definiert die Sichtbarkeit – Marker setzen und fertig.
            settings.set(_MIGRATION_MARKER, True)
            return
        stored = _stored_panels(settings)
        if stored is None:
            settings.set(_MIGRATION_MARKER, True)
            return
        # v2.2.40: die drei Warnbereiche sind ein Abschnitt geworden.
        stored["action_needed"] = True
        settings.set("cockpit_visible_panels", stored)
        settings.set(_MIGRATION_MARKER, True)
    except Exception as fehler:
        # Migration darf den Start nie verhindern - aber sie darf auch nicht
        # stumm halb angewandt bleiben. Ohne Meldung liefe sie bei jedem
        # Start neu, und niemand wuesste warum.
        _uebersprungen("Cockpit-Voreinstellungen migrieren", fehler)
        pass


def set_panel(settings, key: str, visible: bool) -> dict[str, bool]:
    """Manuelles Umschalten EINES Panels ⇒ Wechsel auf custom.

    Basis ist der aktuell WIRKSAME Zustand (nicht eine ALL-TRUE-Map) – genau
    ein Panel ändert sich.
    """
    cfg = effective_panels(settings)
    if key in cfg:
        cfg[key] = bool(visible)
    settings.set("cockpit_visible_panels", cfg)
    settings.set("cockpit_preset", "custom")
    return cfg


def apply_preset(settings, name: str) -> dict[str, bool]:
    """Preset-Wechsel über die Combo; ``custom`` lässt Panels unangetastet."""
    if name not in (*PRESETS, "custom"):
        name = "focus"
    settings.set("cockpit_preset", name)
    if name != "custom":
        settings.set("cockpit_visible_panels", dict(PRESETS[name]))
    return effective_panels(settings)
