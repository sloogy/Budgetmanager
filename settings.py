from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
import json
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
        """Lädt Einstellungen aus Datei"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.error("Fehler beim Laden der Einstellungen: %s", e)
                return self._defaults()
        return self._defaults()
    
    def _defaults(self) -> dict[str, Any]:
        """Standard-Einstellungen"""
        from pathlib import Path
        return {
            "theme": "light",  # "light" oder "dark"
            "auto_save": False,
            "ask_due": True,
            "warn_delete": True,
            # In dieser Version wird der Budget-Warner zentral über "Extras" genutzt.
            # Der Banner/Warner in der Übersicht bleibt standardmässig aus, um Doppel-Logik zu vermeiden.
            "warn_budget_overrun": False,
            "refresh_on_start": True,  # Beim Start automatisch aktualisieren
            # Tracking: Schnellfilter "nur letzte X Tage".
            # Erlaubte Werte: 14 oder 30
            "recent_days": 14,

            # Wiederkehrende Buchungen: bevorzugter Tag (Default), der beim Setzen von
            # "wiederkehrend" automatisch übernommen wird.
            # 31 bedeutet "Monatsende".
            "recurring_preferred_day": 25,
            # Budget-Übersicht: Mindestanzahl aufeinanderfolgender Monate für Vorschläge
            # Budget-Vorschläge: Standard-Fenster (N Monate)
            "budget_suggestion_months": 3,
            # Budget-Vorschläge: wie "stabil" muss die Richtung sein?
            # 0.7 = 70% der betrachteten Monate müssen die gleiche Tendenz zeigen.
            # 1.0 wäre zu streng (1 Ausreisser blockiert alles).
            "budget_suggestion_sign_ratio": 0.7,
            # Budgetwarnungen: automatisch aus Budget generieren wenn keine gespeicherten Regeln.
            # True = Nutzer sieht Warnungen ohne explizite Konfiguration (empfohlen).
            # False = Nur explizit angelegte Warnungen werden angezeigt.
            "auto_generate_budget_warnings": True,
            # Budget-Übersicht: Ab welchem Monat der Übertrag kumuliert wird (1=Jan, 2=Feb, ...)
            "carryover_start_month": 1,
            # Budget-Übersicht: Ab welchem Jahr der Übertrag kumuliert wird (0 = aktuelles Jahr)
            "carryover_start_year": 0,
            "window_width": 1280,
            "window_height": 800,
            "window_x": 100,  # X-Position des Fensters
            "window_y": 100,  # Y-Position des Fensters
            "window_is_maximized": False,  # Fenster maximiert?
            "window_is_fullscreen": False,  # Fenster im Fullscreen?
            "last_budget_year": None,
            "last_overview_year": None,
            "tab_order": [0, 1, 2, 3],  # Reihenfolge der Tabs (Budget, Kategorien, Tracking, Übersicht)
            # Kategorien-Tab anzeigen (Experten-Modus)
            # False = Kategorien werden über Budget-Dialog verwaltet
            # True = Separater Kategorien-Tab sichtbar (Fallback/Experten)
            "show_categories_tab": False,
            # Tab-Leiste Position und Sichtbarkeit
            "tab_position": "west",    # north / south / east / west
            "tab_bar_visible": True,   # Tab-Leiste anzeigen?
            # Datenbank und Backup Pfade
            "database_path": "data/budgetmanager.db",  # Portable Default (relativ zum Programmordner)
            "backup_directory": "data/backups",  # Portable Default (relativ zum Programmordner)

            # AutoBackup: wie viele Auto-Backups sollen maximal behalten werden?
            "auto_backup_keep": 10,
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
        }
    
    def save(self) -> None:
        """Speichert Einstellungen atomar in Datei.

        Schreibt zuerst in eine temporäre Datei (.tmp), dann wird diese
        per os.replace() atomar auf den Zielpfad verschoben.  So kann die
        Settings-Datei bei einem Absturz oder Stromentzug nicht korrupt werden.
        """
        try:
            self.settings_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_path = self.settings_file.with_suffix('.tmp')
            with open(tmp_path, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(str(tmp_path), str(self.settings_file))
        except Exception as e:
            logger.error("Fehler beim Speichern der Einstellungen: %s", e)
            # Aufräumen: temporäre Datei entfernen falls vorhanden
            try:
                tmp_path = self.settings_file.with_suffix('.tmp')
                if tmp_path.exists():
                    tmp_path.unlink()
            except Exception as cleanup_err:
                logger.debug("Temporäre Settings-Datei konnte nicht gelöscht werden: %s", cleanup_err)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Holt einen Wert"""
        return self.settings.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Setzt einen Wert und speichert"""
        self.settings[key] = value
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
        return self.get("auto_save", False)
    
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
    def recent_days(self) -> int:
        """Anzahl Tage für den Quick-Filter im Tracking."""
        val = int(self.get("recent_days", 14) or 14)
        return 30 if val == 30 else 14

    @recent_days.setter
    def recent_days(self, value: int):
        v = 30 if int(value) == 30 else 14
        self.set("recent_days", v)

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
        from pathlib import Path
        default = str(Path.home() / "BudgetManager_Backups")
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
        return self.get("currency", "CHF")

    @currency.setter
    def currency(self, value: str):
        self.set("currency", value)

    @property
    def language(self) -> str:
        """Aktive Sprache (Deutsch, Englisch)."""
        return self.get("language", "Deutsch")

    @language.setter
    def language(self, value: str):
        self.set("language", value)

    # (Duplikat entfernt)
