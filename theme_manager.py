"""
Verbesserter Theme Manager für Budgetmanager
JSON-basierte Profile mit vollständiger Farb-Kontrolle
Version 0.18.0
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor


class ThemeProfile:
    """Repräsentiert ein komplettes Theme-Profil"""
    
    def __init__(self, name: str, data: Dict[str, Any]):
        self.name = name
        self.data = data
    
    def get(self, key: str, default: Any = None) -> Any:
        """Hole Wert aus Profil"""
        return self.data.get(key, default)
    
    def set(self, key: str, value: Any):
        """Setze Wert in Profil"""
        self.data[key] = value
    
    def to_dict(self) -> Dict[str, Any]:
        """Konvertiere zu Dictionary"""
        return self.data.copy()
    
    @classmethod
    def from_dict(cls, name: str, data: Dict[str, Any]) -> 'ThemeProfile':
        """Erstelle Profil aus Dictionary"""
        return cls(name, data)


class ThemeManager:
    """
    Zentraler Theme Manager für die gesamte Anwendung.
    
    Features:
    - JSON-basierte Profile (~/.budgetmanager/themes/)
    - Vordefinierte Themes (hell/dunkel Varianten)
    - Vollständige Farb-Kontrolle
    - Typ-Colorierung (Einnahmen/Ausgaben/Ersparnisse)
    - Fix für Dropdown-Probleme
    """
    
    # Vordefinierte Profile
    PREDEFINED_PROFILES = {
        "Standard Hell": {
            "modus": "hell",
            "hintergrund_app": "#ffffff",
            "hintergrund_panel": "#f6f7f9",
            "hintergrund_seitenleiste": "#f0f2f5",
            "sidebar_panel_bg": "#eef2f7",
            "filter_panel_bg": "#f6f7f9",
            "text": "#111111",
            "text_gedimmt": "#444444",
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
            # Dropdown-Farben
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
            "sidebar_panel_bg": "#2a2a2a",
            "filter_panel_bg": "#2d2d2d",
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
            # Dropdown-Farben
            "dropdown_bg": "#2d2d2d",
            "dropdown_text": "#e0e0e0",
            "dropdown_selection": "#0078d4",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#3d3d3d",
        },
        "Hell - Grün": {
            "modus": "hell",
            "hintergrund_app": "#ffffff",
            "hintergrund_panel": "#f7faf9",
            "hintergrund_seitenleiste": "#f0f5f3",
            "sidebar_panel_bg": "#eef7f3",
            "filter_panel_bg": "#f7faf9",
            "text": "#111111",
            "text_gedimmt": "#444444",
            "akzent": "#27ae60",
            "tabelle_hintergrund": "#ffffff",
            "tabelle_alt": "#f7fcf9",
            "tabelle_header": "#eef7f3",
            "tabelle_gitter": "#d6e8df",
            "auswahl_hintergrund": "#27ae60",
            "auswahl_text": "#ffffff",
            "negativ_text": "#e74c3c",
            "typ_einnahmen": "#27ae60",
            "typ_ausgaben": "#e74c3c",
            "typ_ersparnisse": "#3498db",
            "schriftgroesse": 10,
            "dropdown_bg": "#ffffff",
            "dropdown_text": "#111111",
            "dropdown_selection": "#27ae60",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#d6e8df",
        },
        "Dunkel - Blau": {
            "modus": "dunkel",
            "hintergrund_app": "#0d1b2a",
            "hintergrund_panel": "#1b263b",
            "hintergrund_seitenleiste": "#0f1e2e",
            "sidebar_panel_bg": "#162636",
            "filter_panel_bg": "#1b263b",
            "text": "#e0e1dd",
            "text_gedimmt": "#9db4c0",
            "akzent": "#1976d2",
            "tabelle_hintergrund": "#0d1b2a",
            "tabelle_alt": "#0f1e2e",
            "tabelle_header": "#1b263b",
            "tabelle_gitter": "#2c3e50",
            "auswahl_hintergrund": "#1976d2",
            "auswahl_text": "#ffffff",
            "negativ_text": "#ef5350",
            "typ_einnahmen": "#66bb6a",
            "typ_ausgaben": "#ef5350",
            "typ_ersparnisse": "#42a5f5",
            "schriftgroesse": 10,
            "dropdown_bg": "#1b263b",
            "dropdown_text": "#e0e1dd",
            "dropdown_selection": "#1976d2",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#2c3e50",
        },
        "Dunkel - Grün": {
            "modus": "dunkel",
            "hintergrund_app": "#0a1612",
            "hintergrund_panel": "#1b2d24",
            "hintergrund_seitenleiste": "#0e1f18",
            "sidebar_panel_bg": "#15271e",
            "filter_panel_bg": "#1b2d24",
            "text": "#e8f5e9",
            "text_gedimmt": "#a5d6a7",
            "akzent": "#388e3c",
            "tabelle_hintergrund": "#0a1612",
            "tabelle_alt": "#0e1f18",
            "tabelle_header": "#1b2d24",
            "tabelle_gitter": "#2e4a35",
            "auswahl_hintergrund": "#388e3c",
            "auswahl_text": "#ffffff",
            "negativ_text": "#ef5350",
            "typ_einnahmen": "#66bb6a",
            "typ_ausgaben": "#ef5350",
            "typ_ersparnisse": "#64b5f6",
            "schriftgroesse": 10,
            "dropdown_bg": "#1b2d24",
            "dropdown_text": "#e8f5e9",
            "dropdown_selection": "#388e3c",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#2e4a35",
        },
        "Kontrast - Schwarz/Weiß": {
            "modus": "hell",
            "hintergrund_app": "#ffffff",
            "hintergrund_panel": "#f0f0f0",
            "hintergrund_seitenleiste": "#e8e8e8",
            "sidebar_panel_bg": "#e0e0e0",
            "filter_panel_bg": "#f0f0f0",
            "text": "#000000",
            "text_gedimmt": "#333333",
            "akzent": "#000000",
            "tabelle_hintergrund": "#ffffff",
            "tabelle_alt": "#f8f8f8",
            "tabelle_header": "#e0e0e0",
            "tabelle_gitter": "#cccccc",
            "auswahl_hintergrund": "#000000",
            "auswahl_text": "#ffffff",
            "negativ_text": "#8b0000",
            "typ_einnahmen": "#006400",
            "typ_ausgaben": "#8b0000",
            "typ_ersparnisse": "#00008b",
            "schriftgroesse": 11,
            "dropdown_bg": "#ffffff",
            "dropdown_text": "#000000",
            "dropdown_selection": "#000000",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#000000",
        },
        "Pastell - Sanft": {
            "modus": "hell",
            "hintergrund_app": "#fffef7",
            "hintergrund_panel": "#f5f5f0",
            "hintergrund_seitenleiste": "#f0f0e8",
            "sidebar_panel_bg": "#ede7f6",
            "filter_panel_bg": "#f5f5f0",
            "text": "#5d4e6d",
            "text_gedimmt": "#8b7e8f",
            "akzent": "#b39ddb",
            "tabelle_hintergrund": "#fffef7",
            "tabelle_alt": "#fafaf5",
            "tabelle_header": "#ede7f6",
            "tabelle_gitter": "#d9d9d9",
            "auswahl_hintergrund": "#b39ddb",
            "auswahl_text": "#ffffff",
            "negativ_text": "#e57373",
            "typ_einnahmen": "#81c784",
            "typ_ausgaben": "#e57373",
            "typ_ersparnisse": "#64b5f6",
            "schriftgroesse": 10,
            "dropdown_bg": "#fffef7",
            "dropdown_text": "#5d4e6d",
            "dropdown_selection": "#b39ddb",
            "dropdown_selection_text": "#ffffff",
            "dropdown_border": "#d9d9d9",
        },
    }
    
    def __init__(self, settings):
        """
        Initialisiere Theme Manager
        
        Args:
            settings: Settings-Objekt der Anwendung
        """
        self.settings = settings
        self.profiles_dir = Path.home() / ".budgetmanager" / "themes"
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        
        self._current_profile_name = None
        self._current_profile = None
        
        # Initialisiere vordefinierte Profile
        self._initialize_predefined_profiles()
        
        # Lade benutzerdefinierte Profile
        self._load_custom_profiles()
    
    def _initialize_predefined_profiles(self):
        """Erstelle vordefinierte Profile als JSON-Dateien"""
        for name, data in self.PREDEFINED_PROFILES.items():
            filepath = self._get_profile_path(name)
            if not filepath.exists():
                self._save_profile_to_file(name, data)
    
    def _load_custom_profiles(self):
        """Lade alle benutzerdefinierten Profile aus dem Verzeichnis"""
        # Wird bei Bedarf geladen, keine zentrale Liste mehr nötig
        pass
    
    def _get_profile_path(self, profile_name: str) -> Path:
        """Generiere Dateipfad für Profil"""
        # Konvertiere Name zu Dateinamen
        filename = profile_name.lower().replace(" ", "_").replace("-", "_")
        filename = "".join(c for c in filename if c.isalnum() or c == "_")
        return self.profiles_dir / f"{filename}.json"
    
    def _save_profile_to_file(self, name: str, data: Dict[str, Any]) -> bool:
        """Speichere Profil als JSON"""
        try:
            filepath = self._get_profile_path(name)
            with open(filepath, 'w', encoding='utf-8') as f:
                profile_data = {"name": name, **data}
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Fehler beim Speichern des Profils '{name}': {e}")
            return False
    
    def _load_profile_from_file(self, name: str) -> Optional[Dict[str, Any]]:
        """Lade Profil aus JSON"""
        try:
            filepath = self._get_profile_path(name)
            if not filepath.exists():
                return None
            
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Entferne 'name' aus den Daten, da es bereits bekannt ist
                data.pop('name', None)
                return data
        except Exception as e:
            print(f"Fehler beim Laden des Profils '{name}': {e}")
            return None
    
    def get_all_profiles(self) -> List[str]:
        """Liste alle verfügbaren Profile"""
        profiles = []
        for filepath in self.profiles_dir.glob("*.json"):
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    profiles.append(data.get('name', filepath.stem))
            except Exception:
                pass
        return sorted(profiles)
    
    def get_profile(self, name: str) -> Optional[ThemeProfile]:
        """Hole ein spezifisches Profil"""
        data = self._load_profile_from_file(name)
        if data:
            return ThemeProfile(name, data)
        return None
    
    def get_current_profile(self) -> Optional[ThemeProfile]:
        """Hole aktuelles Profil"""
        if self._current_profile is None:
            # Lade aus Settings
            profile_name = self.settings.get("appearance_profile", "Standard Hell")
            self.set_current_profile(profile_name)
        
        return self._current_profile
    
    def set_current_profile(self, name: str):
        """Setze aktuelles Profil"""
        profile = self.get_profile(name)
        if profile:
            self._current_profile_name = name
            self._current_profile = profile
            self.settings.set("appearance_profile", name)
    
    def create_profile(self, name: str, base_profile: Optional[str] = None) -> bool:
        """
        Erstelle neues benutzerdefiniertes Profil
        
        Args:
            name: Name des neuen Profils
            base_profile: Name des Basis-Profils (Standard: "Standard Hell")
        
        Returns:
            True bei Erfolg
        """
        if name in self.get_all_profiles():
            return False
        
        # Hole Basis-Profil
        if base_profile is None:
            base_profile = "Standard Hell"
        
        base_data = self._load_profile_from_file(base_profile)
        if base_data is None:
            base_data = self.PREDEFINED_PROFILES.get(base_profile, self.PREDEFINED_PROFILES["Standard Hell"])
        
        return self._save_profile_to_file(name, base_data)
    
    def update_profile(self, name: str, data: Dict[str, Any]) -> bool:
        """Aktualisiere existierendes Profil"""
        if name not in self.get_all_profiles():
            return False
        
        return self._save_profile_to_file(name, data)
    
    def delete_profile(self, name: str) -> bool:
        """Lösche Profil (nur benutzerdefinierte)"""
        if name in self.PREDEFINED_PROFILES:
            return False  # Vordefinierte Profile können nicht gelöscht werden
        
        try:
            filepath = self._get_profile_path(name)
            if filepath.exists():
                filepath.unlink()
                
                # Wenn aktuelles Profil gelöscht wurde, wechsle zu Standard
                if self._current_profile_name == name:
                    self.set_current_profile("Standard Hell")
                
                return True
        except Exception as e:
            print(f"Fehler beim Löschen des Profils '{name}': {e}")
        
        return False
    
    def is_predefined(self, name: str) -> bool:
        """Prüfe ob Profil vordefiniert ist"""
        return name in self.PREDEFINED_PROFILES
    
    def export_profile(self, name: str, filepath: str) -> bool:
        """Exportiere Profil als JSON"""
        profile = self.get_profile(name)
        if profile is None:
            return False
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                export_data = {"name": name, **profile.data}
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Fehler beim Exportieren des Profils: {e}")
            return False
    
    def import_profile(self, filepath: str) -> Optional[str]:
        """
        Importiere Profil aus JSON
        
        Returns:
            Name des importierten Profils oder None bei Fehler
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            name = data.pop('name', 'Importiert')
            
            # Stelle sicher dass Name eindeutig ist
            original_name = name
            counter = 1
            while name in self.get_all_profiles():
                name = f"{original_name} ({counter})"
                counter += 1
            
            if self._save_profile_to_file(name, data):
                return name
        except Exception as e:
            print(f"Fehler beim Importieren des Profils: {e}")
        
        return None
    
    def build_stylesheet(self, profile: Optional[ThemeProfile] = None) -> str:
        """
        Generiere komplettes Stylesheet aus Profil
        
        Args:
            profile: Theme-Profil (Standard: aktuelles Profil)
        
        Returns:
            QSS-Stylesheet als String
        """
        if profile is None:
            profile = self.get_current_profile()
            if profile is None:
                profile = ThemeProfile("Standard Hell", self.PREDEFINED_PROFILES["Standard Hell"])
        
        p = profile.data
        
        # Basis-Farben
        bg_app = p.get("hintergrund_app", "#ffffff")
        bg_panel = p.get("hintergrund_panel", "#f6f7f9")
        bg_sidebar = p.get("hintergrund_seitenleiste", "#f0f2f5")
        sidebar_panel_bg = p.get("sidebar_panel_bg", "#eef2f7")
        filter_panel_bg = p.get("filter_panel_bg", "#f6f7f9")
        text = p.get("text", "#111111")
        text_dim = p.get("text_gedimmt", "#444444")
        accent = p.get("akzent", "#2f80ed")
        
        # Tabellen-Farben
        table_bg = p.get("tabelle_hintergrund", "#ffffff")
        table_alt = p.get("tabelle_alt", "#f7f9fc")
        table_header = p.get("tabelle_header", "#eef2f7")
        table_grid = p.get("tabelle_gitter", "#d6dbe3")
        
        # Auswahl-Farben
        sel_bg = p.get("auswahl_hintergrund", "#2f80ed")
        sel_text = p.get("auswahl_text", "#ffffff")
        
        # Dropdown-Farben (FIX für schwarze Schrift/Hintergrund)
        dropdown_bg = p.get("dropdown_bg", bg_panel)
        dropdown_text = p.get("dropdown_text", text)
        dropdown_sel = p.get("dropdown_selection", accent)
        dropdown_sel_text = p.get("dropdown_selection_text", "#ffffff")
        dropdown_border = p.get("dropdown_border", table_grid)
        
        # Negative Farbe
        neg_text = p.get("negativ_text", "#e74c3c")
        
        # Schriftgröße
        font_size = p.get("schriftgroesse", 10)
        
        stylesheet = f"""
/* ============================================================
   BUDGETMANAGER - GLOBALES STYLESHEET
   Profil: {profile.name}
   ============================================================ */

/* === HAUPTFENSTER UND DIALOGE === */
QMainWindow, QDialog {{
    background-color: {bg_app};
    color: {text};
    font-size: {font_size}pt;
}}

/* === LABELS === */
QLabel {{
    color: {text};
    background-color: transparent;
}}

QLabel[styleClass="header"] {{
    font-size: {font_size + 4}pt;
    font-weight: bold;
    color: {accent};
}}

QLabel[styleClass="subheader"] {{
    font-size: {font_size + 2}pt;
    font-weight: bold;
    color: {text};
}}

/* === BUTTONS === */
QPushButton {{
    background-color: {accent};
    color: {sel_text};
    border: none;
    padding: 8px 16px;
    border-radius: 4px;
    font-weight: bold;
    min-height: 28px;
}}

QPushButton:hover {{
    background-color: {self._adjust_color(accent, 15)};
}}

QPushButton:pressed {{
    background-color: {self._adjust_color(accent, -15)};
}}

QPushButton:disabled {{
    background-color: {text_dim};
    color: {bg_panel};
}}

QPushButton[styleClass="secondary"] {{
    background-color: {bg_panel};
    color: {text};
    border: 1px solid {table_grid};
}}

QPushButton[styleClass="secondary"]:hover {{
    background-color: {table_alt};
}}

QPushButton[styleClass="danger"] {{
    background-color: {neg_text};
    color: #ffffff;
}}

QPushButton[styleClass="danger"]:hover {{
    background-color: {self._adjust_color(neg_text, -15)};
}}

/* === INPUT-FELDER === */
QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox, QDateEdit {{
    background-color: {bg_panel};
    color: {text};
    border: 1px solid {table_grid};
    border-radius: 4px;
    padding: 6px;
    selection-background-color: {sel_bg};
    selection-color: {sel_text};
}}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus, 
QSpinBox:focus, QDoubleSpinBox:focus, QDateEdit:focus {{
    border: 2px solid {accent};
    padding: 5px;
}}

QLineEdit:disabled, QTextEdit:disabled, QPlainTextEdit:disabled,
QSpinBox:disabled, QDoubleSpinBox:disabled, QDateEdit:disabled {{
    background-color: {table_alt};
    color: {text_dim};
}}

/* === COMBOBOX (FIX FÜR SCHWARZE SCHRIFT) === */
QComboBox {{
    background-color: {dropdown_bg};
    color: {dropdown_text};
    border: 1px solid {dropdown_border};
    border-radius: 4px;
    padding: 6px;
    padding-right: 25px;
    selection-background-color: {dropdown_sel};
    selection-color: {dropdown_sel_text};
}}

QComboBox:hover {{
    border: 1px solid {accent};
}}

QComboBox:focus {{
    border: 2px solid {accent};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 25px;
    border: none;
}}

QComboBox::down-arrow {{
    image: none;
    border-left: 5px solid transparent;
    border-right: 5px solid transparent;
    border-top: 6px solid {dropdown_text};
    margin-right: 8px;
}}

QComboBox:disabled {{
    background-color: {table_alt};
    color: {text_dim};
}}

/* Dropdown-Liste (FIX FÜR SCHWARZEN HINTERGRUND) */
QComboBox QAbstractItemView {{
    background-color: {dropdown_bg};
    color: {dropdown_text};
    border: 1px solid {dropdown_border};
    selection-background-color: {dropdown_sel};
    selection-color: {dropdown_sel_text};
    outline: none;
}}

QComboBox QAbstractItemView::item {{
    background-color: {dropdown_bg};
    color: {dropdown_text};
    padding: 6px;
    min-height: 28px;
}}

QComboBox QAbstractItemView::item:selected {{
    background-color: {dropdown_sel};
    color: {dropdown_sel_text};
}}

QComboBox QAbstractItemView::item:hover {{
    background-color: {table_alt};
}}

/* === TABELLEN === */
QTableWidget, QTableView {{
    background-color: {table_bg};
    alternate-background-color: {table_alt};
    gridline-color: {table_grid};
    color: {text};
    border: 1px solid {table_grid};
    selection-background-color: {sel_bg};
    selection-color: {sel_text};
}}

QTableWidget::item, QTableView::item {{
    padding: 4px;
    border: none;
}}

QTableWidget::item:selected, QTableView::item:selected {{
    background-color: {sel_bg};
    color: {sel_text};
}}

QTableWidget::item:hover, QTableView::item:hover {{
    background-color: {table_alt};
}}

QHeaderView::section {{
    background-color: {table_header};
    color: {text};
    padding: 8px;
    border: none;
    border-right: 1px solid {table_grid};
    border-bottom: 1px solid {table_grid};
    font-weight: bold;
}}

QHeaderView::section:hover {{
    background-color: {self._adjust_color(table_header, 10)};
}}

/* === SCROLLBARS === */
QScrollBar:vertical {{
    background-color: {bg_panel};
    width: 14px;
    border: none;
}}

QScrollBar::handle:vertical {{
    background-color: {text_dim};
    border-radius: 7px;
    min-height: 30px;
    margin: 2px;
}}

QScrollBar::handle:vertical:hover {{
    background-color: {accent};
}}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0px;
}}

QScrollBar:horizontal {{
    background-color: {bg_panel};
    height: 14px;
    border: none;
}}

QScrollBar::handle:horizontal {{
    background-color: {text_dim};
    border-radius: 7px;
    min-width: 30px;
    margin: 2px;
}}

QScrollBar::handle:horizontal:hover {{
    background-color: {accent};
}}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0px;
}}

/* === TABS === */
QTabWidget::pane {{
    border: 1px solid {table_grid};
    background-color: {bg_panel};
}}

QTabBar::tab {{
    background-color: {bg_panel};
    color: {text};
    padding: 10px 20px;
    border: 1px solid {table_grid};
    border-bottom: none;
    border-top-left-radius: 4px;
    border-top-right-radius: 4px;
}}

QTabBar::tab:selected {{
    background-color: {bg_app};
    color: {accent};
    font-weight: bold;
    border-bottom: 2px solid {accent};
}}

QTabBar::tab:hover:!selected {{
    background-color: {table_alt};
}}

/* === MENÜS === */
QMenuBar {{
    background-color: {bg_panel};
    color: {text};
    border-bottom: 1px solid {table_grid};
}}

QMenuBar::item {{
    background-color: transparent;
    padding: 6px 12px;
}}

QMenuBar::item:selected {{
    background-color: {accent};
    color: {sel_text};
}}

QMenu {{
    background-color: {bg_panel};
    color: {text};
    border: 1px solid {table_grid};
}}

QMenu::item {{
    padding: 6px 30px 6px 20px;
}}

QMenu::item:selected {{
    background-color: {accent};
    color: {sel_text};
}}

QMenu::separator {{
    height: 1px;
    background-color: {table_grid};
    margin: 4px 0px;
}}

/* === GROUPBOX === */
QGroupBox {{
    border: 1px solid {table_grid};
    border-radius: 4px;
    margin-top: 12px;
    font-weight: bold;
    padding: 12px;
    background-color: transparent;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: {accent};
    background-color: {bg_app};
}}

/* === CHECKBOX & RADIOBUTTON === */
QCheckBox, QRadioButton {{
    color: {text};
    spacing: 8px;
}}

QCheckBox::indicator, QRadioButton::indicator {{
    width: 18px;
    height: 18px;
    border: 2px solid {table_grid};
    background-color: {bg_panel};
}}

QCheckBox::indicator:hover, QRadioButton::indicator:hover {{
    border: 2px solid {accent};
}}

QCheckBox::indicator:checked {{
    background-color: {accent};
    border: 2px solid {accent};
    image: none;
}}

QRadioButton::indicator {{
    border-radius: 9px;
}}

QRadioButton::indicator:checked {{
    background-color: {accent};
    border: 2px solid {accent};
}}

QCheckBox:disabled, QRadioButton:disabled {{
    color: {text_dim};
}}

/* === PROGRESSBAR === */
QProgressBar {{
    background-color: {bg_panel};
    border: 1px solid {table_grid};
    border-radius: 4px;
    text-align: center;
    color: {text};
    height: 20px;
}}

QProgressBar::chunk {{
    background-color: {accent};
    border-radius: 3px;
}}

/* === SLIDER === */
QSlider::groove:horizontal {{
    background-color: {bg_panel};
    height: 6px;
    border-radius: 3px;
}}

QSlider::handle:horizontal {{
    background-color: {accent};
    width: 16px;
    height: 16px;
    margin: -5px 0;
    border-radius: 8px;
}}

QSlider::handle:horizontal:hover {{
    background-color: {self._adjust_color(accent, 15)};
}}

/* === STATUSBAR === */
QStatusBar {{
    background-color: {bg_panel};
    color: {text};
    border-top: 1px solid {table_grid};
}}

/* === TOOLBAR === */
QToolBar {{
    background-color: {bg_panel};
    border: none;
    spacing: 4px;
    padding: 4px;
}}

QToolButton {{
    background-color: transparent;
    color: {text};
    border: none;
    padding: 6px;
    border-radius: 4px;
}}

QToolButton:hover {{
    background-color: {table_alt};
}}

QToolButton:pressed {{
    background-color: {accent};
    color: {sel_text};
}}

/* === SPLITTER === */
QSplitter::handle {{
    background-color: {table_grid};
}}

QSplitter::handle:horizontal {{
    width: 2px;
}}

QSplitter::handle:vertical {{
    height: 2px;
}}

QSplitter::handle:hover {{
    background-color: {accent};
}}

/* === SPEZIELLE PANELS === */
QWidget[styleClass="sidebar"] {{
    background-color: {bg_sidebar};
    border-right: 1px solid {table_grid};
}}

QWidget[styleClass="sidebar-panel"] {{
    background-color: {sidebar_panel_bg};
    border: 1px solid {table_grid};
    border-radius: 4px;
    padding: 8px;
}}

QWidget[styleClass="filter-panel"] {{
    background-color: {filter_panel_bg};
    border: 1px solid {table_grid};
    border-radius: 4px;
    padding: 12px;
}}

/* === TOOLTIPS === */
QToolTip {{
    background-color: {bg_panel};
    color: {text};
    border: 1px solid {table_grid};
    border-radius: 4px;
    padding: 4px;
}}

/* === NEGATIVE ZAHLEN === */
QLabel[negativeValue="true"], QTableWidget::item[negativeValue="true"] {{
    color: {neg_text};
}}

/* === BESONDERE WIDGET-STATES === */
*:disabled {{
    color: {text_dim};
}}
"""
        
        return stylesheet
    
    def apply_theme(self, app: Optional[QApplication] = None, profile_name: Optional[str] = None):
        """
        Wende Theme auf Anwendung an
        
        Args:
            app: QApplication-Instanz (Standard: aktuelle App)
            profile_name: Name des Profils (Standard: aktuelles Profil)
        """
        if app is None:
            app = QApplication.instance()
        
        if app is None:
            return
        
        if profile_name:
            self.set_current_profile(profile_name)
        
        profile = self.get_current_profile()
        if profile:
            stylesheet = self.build_stylesheet(profile)
            app.setStyleSheet(stylesheet)
    
    def get_type_colors(self, profile: Optional[ThemeProfile] = None) -> Dict[str, str]:
        """
        Hole Typ-Farben aus Profil für type_color_helper
        
        Args:
            profile: Theme-Profil (Standard: aktuelles Profil)
        
        Returns:
            Dictionary mit Typ-Namen und Hex-Farben
        """
        if profile is None:
            profile = self.get_current_profile()
            if profile is None:
                return {}
        
        return {
            "Einnahmen": profile.get("typ_einnahmen", "#2ecc71"),
            "Ausgaben": profile.get("typ_ausgaben", "#e74c3c"),
            "Ersparnisse": profile.get("typ_ersparnisse", "#3498db"),
        }
    
    def get_negative_color(self, profile: Optional[ThemeProfile] = None) -> str:
        """Hole Farbe für negative Zahlen"""
        if profile is None:
            profile = self.get_current_profile()
            if profile is None:
                return "#e74c3c"
        
        return profile.get("negativ_text", "#e74c3c")
    
    @staticmethod
    def _adjust_color(color: str, percent: int) -> str:
        """
        Passe Helligkeit einer Farbe an
        
        Args:
            color: Hex-Farbe (#RRGGBB)
            percent: Prozent zur Anpassung (+/- 0-100)
        
        Returns:
            Angepasste Hex-Farbe
        """
        try:
            color = color.lstrip('#')
            r, g, b = int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)
            
            # Berechne Anpassung
            adjustment = int(255 * (percent / 100))
            
            r = max(0, min(255, r + adjustment))
            g = max(0, min(255, g + adjustment))
            b = max(0, min(255, b + adjustment))
            
            return f"#{r:02X}{g:02X}{b:02X}"
        except:
            return color
    
    @staticmethod
    def get_predefined_profiles() -> List[str]:
        """Hole Liste vordefinierter Profile"""
        return list(ThemeManager.PREDEFINED_PROFILES.keys())


# Singleton-Instanz
_theme_manager_instance = None


def get_theme_manager(settings=None) -> ThemeManager:
    """Hole globale ThemeManager-Instanz"""
    global _theme_manager_instance
    if _theme_manager_instance is None and settings is not None:
        _theme_manager_instance = ThemeManager(settings)
    return _theme_manager_instance
