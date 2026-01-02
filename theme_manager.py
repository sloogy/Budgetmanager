"""
Überarbeiteter Theme Manager - ALLE Themes als JSON editierbar  
Version 0.19.0 - Vollständige JSON-basierte Theme-Verwaltung
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from PySide6.QtWidgets import QApplication


class ThemeProfile:
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data
    
    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
    
    def to_dict(self) -> Dict[str, Any]:
        return self.data.copy()


def get_default_themes() -> Dict[str, Dict[str, Any]]:
    """Alle Standard-Themes"""
    return {
        "Standard Hell": {
            "modus": "hell",
            "hintergrund_app": "#ffffff",
            "hintergrund_panel": "#f6f7f9",
            "hintergrund_seitenleiste": "#f0f2f5",
            "text": "#111111",
            "text_gedimmt": "#666666",
            "akzent": "#2f80ed",
            "tabelle_hintergrund": "#ffffff",
            "tabelle_alt": "#f7f9fc",
            "tabelle_header": "#eef2f7",
            "tabelle_gitter": "#d6dbe3",
            "auswahl_hintergrund": "#2f80ed",
            "auswahl_text": "#ffffff",
            "negativ_text": "#e74c3c",
            "typ_einnahmen": "#2ecc71",
            "typ_ausgaben": "#e74c3c",
            "typ_ersparnisse": "#3498db",
            "schriftgroesse": 10,
            "dropdown_bg": "#ffffff",
            "dropdown_text": "#111111",
            "dropdown_selection": "#2f80ed",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#d6dbe3",
        },
        "Standard Dunkel": {
            "modus": "dunkel",
            "hintergrund_app": "#1e1e1e",
            "hintergrund_panel": "#2d2d2d",
            "hintergrund_seitenleiste": "#252525",
            "text": "#e0e0e0",
            "text_gedimmt": "#aaaaaa",
            "akzent": "#0078d4",
            "tabelle_hintergrund": "#1e1e1e",
            "tabelle_alt": "#252525",
            "tabelle_header": "#2d2d2d",
            "tabelle_gitter": "#3d3d3d",
            "auswahl_hintergrund": "#0078d4",
            "auswahl_text": "#ffffff",
            "negativ_text": "#ff6b6b",
            "typ_einnahmen": "#4caf50",
            "typ_ausgaben": "#f44336",
            "typ_ersparnisse": "#2196f3",
            "schriftgroesse": 10,
            "dropdown_bg": "#2d2d2d",
            "dropdown_text": "#e0e0e0",
            "dropdown_selection": "#0078d4",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#3d3d3d",
        },
    }


class ThemeManager:
    def __init__(self, settings):
        self.settings = settings
        self.themes_dir = Path.home() / ".budgetmanager" / "themes"
        self.themes_dir.mkdir(parents=True, exist_ok=True)
        self._current_profile = None
        self._ensure_default_themes()
    
    def _ensure_default_themes(self):
        """Stelle sicher dass Standard-Themes existieren"""
        for name, data in get_default_themes().items():
            path = self._get_path(name)
            if not path.exists():
                self._save_to_file(name, data)
    
    def _get_path(self, name: str) -> Path:
        filename = name.lower().replace(" ", "_").replace("-", "_")
        filename = "".join(c for c in filename if c.isalnum() or c == "_")
        return self.themes_dir / f"{filename}.json"
    
    def _save_to_file(self, name: str, data: Dict[str, Any]) -> bool:
        try:
            with open(self._get_path(name), 'w', encoding='utf-8') as f:
                json.dump({"name": name, **data}, f, indent=2, ensure_ascii=False)
            return True
        except:
            return False
    
    def _load_from_file(self, name: str) -> Optional[Dict[str, Any]]:
        try:
            path = self._get_path(name)
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    data.pop('name', None)
                    return data
        except:
            pass
        return None
    
    def get_all_profiles(self) -> List[str]:
        profiles = []
        for file in self.themes_dir.glob("*.json"):
            try:
                with open(file, 'r') as f:
                    data = json.load(f)
                    if 'name' in data:
                        profiles.append(data['name'])
            except:
                pass
        return sorted(profiles)
    
    def get_profile(self, name: str) -> Optional[ThemeProfile]:
        data = self._load_from_file(name)
        if data:
            return ThemeProfile(name, data)
        return None
    
    def update_profile(self, name: str, data: Dict[str, Any]) -> bool:
        return self._save_to_file(name, data)
    
    def set_current_profile(self, name: str) -> bool:
        profile = self.get_profile(name)
        if profile:
            self._current_profile = profile
            self.settings.set("active_design_profile", name)
            return True
        return False
    
    def get_current_profile(self) -> Optional[ThemeProfile]:
        if not self._current_profile:
            saved = self.settings.get("active_design_profile", "Standard Hell")
            self.set_current_profile(saved)
        return self._current_profile
    
    def get_type_colors(self) -> Dict[str, str]:
        p = self.get_current_profile()
        if not p:
            return {"Einnahmen": "#2ecc71", "Ausgaben": "#e74c3c", "Ersparnisse": "#3498db"}
        return {
            "Einnahmen": p.get("typ_einnahmen", "#2ecc71"),
            "Einkommen": p.get("typ_einnahmen", "#2ecc71"),
            "Ausgaben": p.get("typ_ausgaben", "#e74c3c"),
            "Ersparnisse": p.get("typ_ersparnisse", "#3498db"),
        }
    
    def build_stylesheet(self, profile: ThemeProfile) -> str:
        p = profile.data
        bg_app = p.get("hintergrund_app", "#fff")
        bg_panel = p.get("hintergrund_panel", "#f6f7f9")
        text = p.get("text", "#111")
        text_dim = p.get("text_gedimmt", "#666")
        accent = p.get("akzent", "#2f80ed")
        table_bg = p.get("tabelle_hintergrund", "#fff")
        table_alt = p.get("tabelle_alt", "#f7f9fc")
        table_header = p.get("tabelle_header", "#eef2f7")
        table_grid = p.get("tabelle_gitter", "#d6dbe3")
        sel_bg = p.get("auswahl_hintergrund", "#2f80ed")
        sel_text = p.get("auswahl_text", "#fff")
        dropdown_bg = p.get("dropdown_bg", bg_panel)
        dropdown_text = p.get("dropdown_text", text)
        dropdown_sel = p.get("dropdown_selection", accent)
        dropdown_sel_text = p.get("dropdown_selection_text", "#fff")
        dropdown_border = p.get("dropdown_border", table_grid)
        font_size = p.get("schriftgroesse", 10)
        
        return f"""
* {{ font-size: {font_size}pt; }}
QMainWindow, QDialog, QWidget {{ background-color: {bg_app}; color: {text}; }}
QPushButton {{ background-color: {accent}; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; }}
QPushButton:hover {{ background-color: {accent}aa; }}
QLineEdit, QTextEdit, QSpinBox, QDateEdit {{ background-color: {bg_panel}; color: {text}; border: 1px solid {table_grid}; border-radius: 4px; padding: 6px; }}
QComboBox {{ background-color: {dropdown_bg}; color: {dropdown_text}; border: 1px solid {dropdown_border}; border-radius: 4px; padding: 6px; min-height: 20px; }}
QComboBox::drop-down {{ border: none; width: 20px; }}
QComboBox QAbstractItemView {{ background-color: {dropdown_bg}; color: {dropdown_text}; border: 1px solid {dropdown_border}; selection-background-color: {dropdown_sel}; selection-color: {dropdown_sel_text}; }}
QComboBox QAbstractItemView::item {{ padding: 6px; min-height: 24px; background-color: {dropdown_bg}; color: {dropdown_text}; }}
QComboBox QAbstractItemView::item:selected {{ background-color: {dropdown_sel}; color: {dropdown_sel_text}; }}
QTableWidget {{ background-color: {table_bg}; alternate-background-color: {table_alt}; gridline-color: {table_grid}; selection-background-color: {sel_bg}; selection-color: {sel_text}; }}
QHeaderView::section {{ background-color: {table_header}; border: 1px solid {table_grid}; padding: 6px; }}
QGroupBox {{ background-color: {bg_panel}; border: 1px solid {table_grid}; border-radius: 8px; padding: 12px; margin-top: 12px; }}
QGroupBox::title {{ color: {accent}; padding: 0 8px; }}
"""
    
    def apply_theme(self, app=None, profile_name=None):
        if app is None:
            app = QApplication.instance()
        if profile_name:
            self.set_current_profile(profile_name)
        profile = self.get_current_profile()
        if profile and app:
            app.setStyleSheet(self.build_stylesheet(profile))
            self.settings.set("typ_einnahmen_color", profile.get("typ_einnahmen", "#2ecc71"))
            self.settings.set("typ_ausgaben_color", profile.get("typ_ausgaben", "#e74c3c"))
            self.settings.set("typ_ersparnisse_color", profile.get("typ_ersparnisse", "#3498db"))
