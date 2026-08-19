from __future__ import annotations
import logging

logger = logging.getLogger(__name__)
import json

from utils.cockpit_presets import PRESETS as _COCKPIT_PRESETS
import os
from pathlib import Path
from typing import Any


class Settings:
    """Verwaltet persistente Anwendungseinstellungen"""

    def __init__(self, settings_file: str | None = None):
        from model.app_paths import settings_path

        # Portable: Settings liegen im ./data/ Ordner neben dem Programm
        self.settings_file = Path(settings_file) if settings_file else settings_path()
        self.settings = self._load()

    def _load(self) -> dict[str, Any]:
        """Lädt Einstellungen aus Datei.

        Wichtig für Installer/Portable-Builds:
        Der Installer kann ein Teil-JSON schreiben (z.B. nur Sprache, Währung,
        bevorzugter Buchungstag und Datenpfad). Geladene Werte werden deshalb
        über die vollständigen Defaults gelegt. So fehlen keine neuen Keys wie
        ``budget_overview_drag_drop`` und bestehende Nutzerwerte bleiben trotzdem
        erhalten.
        """
        defaults = self._defaults()
        if self.settings_file.exists():
            try:
                with open(self.settings_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                if isinstance(loaded, dict):
                    merged = {**defaults, **loaded}
                    # Bestehende Nutzer behalten ihre individuell gewählten
                    # Cockpit-Panels. Nur echte Neuinstallationen starten im
                    # neuen Fokus-Preset.
                    if "cockpit_preset" not in loaded:
                        merged["cockpit_preset"] = "custom"
                        if "cockpit_visible_panels" not in loaded:
                            # Alt-Bestand vor dem Preset-Feature: bisheriges
                            # Erlebnis war "alle Bereiche sichtbar" – exakt so
                            # festschreiben, nichts umgestalten.
                            merged["cockpit_visible_panels"] = {
                                k: True for k in _COCKPIT_PRESETS["standard"]
                            }
                    # Zahlformat aus alten Builds normalisieren (ch/eu/us sowie
                    # swiss/german/french/anglo werden toleriert).
                    try:
                        from utils.money import normalize_number_format, CURRENCIES

                        merged["number_format"] = normalize_number_format(
                            merged.get("number_format")
                        )
                        cur = str(merged.get("currency", "CHF") or "CHF").upper()
                        merged["currency"] = cur if cur in CURRENCIES else "CHF"
                    except Exception as e:
                        logger.debug(
                            "Regionseinstellungen konnten nicht normalisiert werden: %s",
                            e,
                        )
                    return merged
                logger.error(
                    "Einstellungsdatei hat unerwartetes Format – nutze Defaults"
                )
                return defaults
            except Exception as e:
                logger.error("Fehler beim Laden der Einstellungen: %s", e)
                return defaults
        return defaults

    def _defaults(self) -> dict[str, Any]:
        """Standard-Einstellungen"""
        from pathlib import Path

        return {
            "theme": "light",  # "light" oder "dark"
            # Cockpit: ADHS-freundlicher, reduzierter Einstieg.
            "cockpit_preset": "focus",
            "auto_save": True,
            "ask_due": True,
            "warn_delete": True,
            # In dieser Version wird der Budget-Warner zentral über "Extras" genutzt.
            # Der Banner/Warner in der Übersicht bleibt standardmässig aus, um Doppel-Logik zu vermeiden.
            "warn_budget_overrun": False,
            "refresh_on_start": True,  # Beim Start automatisch aktualisieren
            "check_updates_on_start": True,  # Beim Start leichtgewichtig nach Updates suchen
            # Tracking: Schnellfilter "nur letzte X Tage".
            # Erlaubte Werte: 14 oder 30
            "recent_days": 14,
            # Wiederkehrende Buchungen: bevorzugter Tag (Default), der beim Setzen von
            # "wiederkehrend" automatisch übernommen wird.
            # 0 bedeutet "kein bevorzugter Tag", 31 bedeutet "Monatsende".
            "recurring_preferred_day": 25,
            # Budget-Übersicht: Mindestanzahl aufeinanderfolgender Monate für Vorschläge
            # Budget-Vorschläge: Standard-Fenster (N Monate)
            "budget_suggestion_months": 3,
            # Budget-Vorschläge: wie "stabil" muss die Richtung sein?
            # 0.7 = 70% der betrachteten Monate müssen die gleiche Tendenz zeigen.
            # 1.0 wäre zu streng (1 Ausreisser blockiert alles).
            "budget_suggestion_sign_ratio": 0.7,
            # Sanfte Null-Bilanz-Regel: Einkommen als Topf, Ausgaben+Ersparnisse dagegen.
            # Optional, damit die App nicht bevormundet. Wenn aktiv, entstehen
            # Vorschläge zum Erhöhen von Ersparnissen oder Reduzieren von Ersparnissen/flexiblen Ausgaben.
            "budget_zero_balance_rule": False,
            # Was mit regelmässigem Überschuss passieren soll: savings | carryover
            "budget_surplus_strategy": "savings",
            # Lernmodus: Kategorien, die nur getrackt werden und noch im ganzen
            # Jahr kein Budget haben, können separat als neues Budget
            # vorgeschlagen werden. Diese Logik greift NICHT in die normale
            # Budget-Anpassungslogik ein.
            "tracking_budget_learning_enabled": True,
            # 1. Monat beobachten, ab 2. Monat sanft hochrechnen/vorschlagen.
            "tracking_budget_learning_proposal_months": 2,
            # Ab diesem Wert gilt ein Lernvorschlag als stabil genug für eine
            # Vorauswahl im Dialog. Der Nutzer entscheidet weiterhin selbst.
            "tracking_budget_learning_stable_months": 3,
            # Laufenden Monat optional auf Monatsende hochrechnen, wenn bereits
            # Buchungen vorhanden sind.
            "tracking_budget_learning_include_current_month_projection": True,
            # Lernvorschläge im Budgetvorschlagsbericht anzeigen.
            "tracking_budget_learning_show_in_report": True,
            # v2.2.0: Cockpit ist die Startseite; Tracking merkt sich je Konto
            # (Typ) die zuletzt gebuchte Kategorie.
            "start_on_cockpit": True,
            "tracking_last_category": {},
            # Optionales automatisches Ausblenden nach langer stabiler Lernphase
            # ohne Übernahme. Ein positives Jahresbudget beendet den Lernmodus
            # unabhängig davon immer über die Kernregel.
            "tracking_budget_learning_auto_end": False,
            # Vorschläge benutzerfreundlich runden.
            "tracking_budget_learning_round_to": 10,
            # Budgetwarnungen: automatisch aus Budget generieren wenn keine gespeicherten Regeln.
            # True = Nutzer sieht Warnungen ohne explizite Konfiguration (empfohlen).
            # False = Nur explizit angelegte Warnungen werden angezeigt.
            "auto_generate_budget_warnings": True,
            # Budget-Übersicht: Ab welchem Monat der Übertrag kumuliert wird (1=Jan, 2=Feb, ...)
            "carryover_start_month": 1,
            # Budget-Übersicht: Ab welchem Jahr der Übertrag kumuliert wird (0 = aktuelles Jahr)
            "carryover_start_year": 0,
            # Budget-Tabelle: Kategorien per Drag & Drop unter-/umhängen
            "budget_overview_drag_drop": True,
            "window_width": 1280,
            "window_height": 800,
            "window_x": 100,  # X-Position des Fensters
            "window_y": 100,  # Y-Position des Fensters
            "window_is_maximized": False,  # Fenster maximiert?
            "window_is_fullscreen": False,  # Fenster im Fullscreen?
            "last_budget_year": None,
            "last_overview_year": None,
            "tab_order": [
                5,
                0,
                1,
                2,
                3,
                4,
            ],  # Reihenfolge der Tabs (Cockpit, Budget, Kategorien, Tracking, Übersicht, Sparziele)
            # Bedienmodus: simple reduziert sichtbare Spezialfunktionen,
            # advanced zeigt alle Module. Manuelle Anpassungen werden custom.
            "ui_experience_mode": "simple",
            # Kategorien-Tab anzeigen (Experten-Modus)
            # False = Kategorien werden über Budget-Dialog verwaltet
            # True = Separater Kategorien-Tab sichtbar (Fallback/Experten)
            "show_categories_tab": False,
            # Sichtbare Hauptreiter. Kategorien bleibt separat zusätzlich über show_categories_tab geschützt.
            "tab_visibility": {
                "cockpit": True,
                "budget": True,
                "categories": False,
                "tracking": True,
                "overview": True,
                "savings": False,
            },
            # Cockpit: frei gestaltbare Bereiche. Eine Wahrheit fuer die
            # Preset-Maps: utils/cockpit_presets.py (v2.2.22, UI/ADHS-Audit).
            "cockpit_visible_panels": dict(_COCKPIT_PRESETS["focus"]),
            # Cockpit: Automatik schiebt leere, geschrumpfte Bereiche nach unten.
            # "fixed" aktiviert Drag-and-drop und speichert Position + Spalte.
            "cockpit_layout_mode": "auto",
            "cockpit_panel_columns": {
                "kpis": "left",
                "quick_actions": "left",
                "action_needed": "right",
                "charts": "right",
                "favorites": "right",
                "savings": "right",
                "recent": "right",
            },
            # Übergangsschlüssel aus v2.2.42; werden synchron gehalten und
            # können nach erfolgreicher Migration später entfallen.
            "cockpit_tiles_fixed": False,
            "cockpit_tile_columns": {},
            # Cockpit: Basis-/Fixierreihenfolge. Alte Warnschlüssel werden beim
            # Laden im Cockpit auf "action_needed" migriert.
            "cockpit_panel_order": [
                "kpis",
                "quick_actions",
                "action_needed",
                "charts",
                "favorites",
                "savings",
                "recent",
            ],
            # Tab-Leiste Position und Sichtbarkeit
            "tab_position": "west",  # north / south / east / west
            "tab_bar_visible": True,  # Tab-Leiste anzeigen?
            # Datenbank und Backup Pfade
            # data_directory: leer = portabel ({app}/data). Wenn gesetzt (absoluter
            # Pfad), legt die App DB/Backups/verschlüsselte .enc-Dateien dort ab.
            "data_directory": "",
            "database_path": "data/budgetmanager.db",  # Portable Default (relativ zum Programmordner)
            "backup_directory": "data/backups",  # Portable Default (relativ zum Programmordner)
            # AutoBackup: ab Erststart aktiv, damit neue Nutzer nicht ohne Sicherung arbeiten.
            "auto_backup": True,
            # 7 Tage = guter Kompromiss: Schutz ohne Backup-Flut.
            "backup_days": 7,
            # AutoBackup: wie viele Auto-Backups sollen maximal behalten werden?
            "auto_backup_keep": 10,
            # AutoBackup: bei Überschreitung älteste Backups automatisch löschen?
            "backup_auto_delete": False,
            # Design/Theme (V2)
            "active_design_profile": "V2 Hell – Neon Cyan",
            "last_design_profile_hell": "V2 Hell – Neon Cyan",
            "last_design_profile_dunkel": "V2 Dunkel – Graphite Cyan",
            # Setup-Assistent / Onboarding
            "show_onboarding": True,  # Einführung beim Start anzeigen
            "setup_completed": False,  # Setup-Assistent abgeschlossen?
            # Sprache & Währung
            # Persistiert wird bevorzugt der Sprach-Code (de/en/fr/...)
            "language": "de",
            "currency": "CHF",
            # Zahlenformat (Dezimal-/Tausendertrennung): swiss|german|french|anglo
            "number_format": "swiss",
        }

    def save(self) -> None:
        """Speichert Einstellungen atomar in Datei.

        Schreibt zuerst in eine temporäre Datei (.tmp), dann wird diese
        per os.replace() atomar auf den Zielpfad verschoben.  So kann die
        Settings-Datei bei einem Absturz oder Stromentzug nicht korrupt werden.
        """
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.settings_file.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp_path), str(self.settings_file))
        except Exception as e:
            logger.error("Fehler beim Speichern der Einstellungen: %s", e)
            # Aufräumen: temporäre Datei entfernen falls vorhanden
            try:
                tmp_path = self.settings_file.with_suffix(".tmp")
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception as cleanup_err:
                logger.debug(
                    "Temporäre Settings-Datei konnte nicht gelöscht werden: %s",
                    cleanup_err,
                )

    def get(self, key: str, default: Any = None) -> Any:
        """Holt einen Wert"""
        return self.settings.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Setzt einen Wert und speichert"""
        self.settings[key] = value
        self.save()

    def set_many(self, values: dict[str, Any]) -> None:
        """Setzt zusammengehörige Werte und speichert sie atomar in einem Lauf.

        Das verhindert Zwischenstände bei Layout-/Migrationsdaten und reduziert
        mehrere teure fsync-Schreibvorgänge auf einen einzigen.
        """
        if not isinstance(values, dict):
            raise TypeError("values muss ein dict sein")
        self.settings.update(values)
        self.save()

    # Convenience-Methoden
    @property
    def theme(self) -> str:
        return self.get("theme", "light")

    @theme.setter
    def theme(self, value: str):
        self.set("theme", value)

    @property
    def auto_save(self) -> bool:
        return self.get("auto_save", True)

    @auto_save.setter
    def auto_save(self, value: bool):
        self.set("auto_save", value)

    @property
    def ask_due(self) -> bool:
        return self.get("ask_due", True)

    @ask_due.setter
    def ask_due(self, value: bool):
        self.set("ask_due", value)

    @property
    def refresh_on_start(self) -> bool:
        return self.get("refresh_on_start", True)

    @refresh_on_start.setter
    def refresh_on_start(self, value: bool):
        self.set("refresh_on_start", value)

    @property
    def tab_order(self) -> list[int]:
        return self.get("tab_order", [0, 1, 2, 3])

    @tab_order.setter
    def tab_order(self, value: list[int]):
        self.set("tab_order", value)

    @property
    def tab_visibility(self) -> dict:
        return dict(self.get("tab_visibility", {}) or {})

    @tab_visibility.setter
    def tab_visibility(self, value: dict):
        self.set("tab_visibility", dict(value or {}))

    @property
    def cockpit_visible_panels(self) -> dict:
        return dict(self.get("cockpit_visible_panels", {}) or {})

    @cockpit_visible_panels.setter
    def cockpit_visible_panels(self, value: dict):
        self.set("cockpit_visible_panels", dict(value or {}))

    @property
    def recent_days(self) -> int:
        """Anzahl Tage für den Quick-Filter im Tracking."""
        val = int(self.get("recent_days", 14) or 14)
        return 30 if val == 30 else 14

    @recent_days.setter
    def recent_days(self, value: int):
        v = 30 if int(value) == 30 else 14
        self.set("recent_days", v)

    @property
    def data_directory(self) -> str:
        """Frei wählbarer Datenordner (leer = portabel, {app}/data).

        Wird beim Start von model.app_paths.data_dir() ausgewertet. Eine Änderung
        wird erst nach einem Neustart wirksam (die aktive DB ist bereits geöffnet).
        """
        return str(self.get("data_directory", "") or "")

    @data_directory.setter
    def data_directory(self, value: str):
        self.set("data_directory", str(value or "").strip())

    @property
    def database_path(self) -> str:
        """Pfad zur Datenbank-Datei"""
        return self.get("database_path", "budgetmanager.db")

    @database_path.setter
    def database_path(self, value: str):
        self.set("database_path", value)

    @property
    def backup_directory(self) -> str:
        """Pfad zum Backup-Ordner"""
        from model.app_paths import backups_dir

        default = str(backups_dir())
        return self.get("backup_directory", default)

    @backup_directory.setter
    def backup_directory(self, value: str):
        self.set("backup_directory", value)

    # Window State Properties
    @property
    def window_x(self) -> int:
        """X-Position des Fensters"""
        return self.get("window_x", 100)

    @window_x.setter
    def window_x(self, value: int):
        self.set("window_x", value)

    @property
    def window_y(self) -> int:
        """Y-Position des Fensters"""
        return self.get("window_y", 100)

    @window_y.setter
    def window_y(self, value: int):
        self.set("window_y", value)

    @property
    def window_is_maximized(self) -> bool:
        """Ist das Fenster maximiert?"""
        return self.get("window_is_maximized", False)

    @window_is_maximized.setter
    def window_is_maximized(self, value: bool):
        self.set("window_is_maximized", value)

    @property
    def window_is_fullscreen(self) -> bool:
        """Ist das Fenster im Fullscreen?"""
        return self.get("window_is_fullscreen", False)

    @window_is_fullscreen.setter
    def window_is_fullscreen(self, value: bool):
        self.set("window_is_fullscreen", value)

    @property
    def show_categories_tab(self) -> bool:
        """Zeigt den separaten Kategorien-Tab (Experten-Modus)"""
        return self.get("show_categories_tab", False)

    @show_categories_tab.setter
    def show_categories_tab(self, value: bool):
        self.set("show_categories_tab", value)

    @property
    def currency(self) -> str:
        """Aktive Währung (CHF, EUR, USD, GBP)."""
        val = str(self.get("currency", "CHF") or "CHF").upper()
        try:
            from utils.money import CURRENCIES

            return val if val in CURRENCIES else "CHF"
        except Exception:
            return val

    @currency.setter
    def currency(self, value: str):
        val = str(value or "CHF").upper()
        try:
            from utils.money import CURRENCIES

            val = val if val in CURRENCIES else "CHF"
        except Exception:
            pass
        self.set("currency", val)

    @property
    def number_format(self) -> str:
        """Aktives Zahlenformat (swiss, german, french, anglo)."""
        try:
            from utils.money import normalize_number_format

            return normalize_number_format(self.get("number_format", "swiss"))
        except Exception:
            return self.get("number_format", "swiss")

    @number_format.setter
    def number_format(self, value: str):
        try:
            from utils.money import normalize_number_format

            value = normalize_number_format(value)
        except Exception:
            pass
        self.set("number_format", value)

    @property
    def language(self) -> str:
        """Aktive Sprache (Deutsch, Englisch)."""
        return self.get("language", "Deutsch")

    @language.setter
    def language(self, value: str):
        self.set("language", value)

    # (Duplikat entfernt)
