from __future__ import annotations
import json
from pathlib import Path
from typing import Any

class Settings:
    """Verwaltet persistente Anwendungseinstellungen"""
    
    def __init__(self, settings_file: str = "budgetmanager_settings.json"):
        self.settings_file = Path(settings_file)
        self.settings = self._load()
    
    def _load(self) -> dict[str, Any]:
        """Lädt Einstellungen aus Datei"""
        if self.settings_file.exists():
            try:
                with open(self.settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                print(f"Fehler beim Laden der Einstellungen: {e}")
                return self._defaults()
        return self._defaults()
    
    def _defaults(self) -> dict[str, Any]:
        """Standard-Einstellungen"""
        from pathlib import Path
        return {
            "theme": "light",  # "light" oder "dark"
            "auto_save": False,
            "ask_due": True,
            "refresh_on_start": True,  # Beim Start automatisch aktualisieren
            # Tracking: Schnellfilter "nur letzte X Tage".
            # Erlaubte Werte: 14 oder 30
            "recent_days": 14,
            "window_width": 1280,
            "window_height": 800,
            "last_budget_year": None,
            "last_overview_year": None,
            "tab_order": [0, 1, 2, 3],  # Reihenfolge der Tabs (Budget, Kategorien, Tracking, Übersicht)
            # Datenbank und Backup Pfade
            "database_path": "budgetmanager.db",  # Relativer oder absoluter Pfad
            "backup_directory": str(Path.home() / "BudgetManager_Backups"),  # Backup-Ordner
        }
    
    def save(self) -> None:
        """Speichert Einstellungen in Datei"""
        try:
            with open(self.settings_file, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"Fehler beim Speichern der Einstellungen: {e}")
    
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

    # (Duplikat entfernt)
