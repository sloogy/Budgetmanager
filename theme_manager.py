"""
Vollständiger Theme Manager für Budgetmanager
Verwaltet Themes, Profile und Stylesheets zentral
"""

from __future__ import annotations
from typing import Dict, Any, Optional, List
from pathlib import Path
import json
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QColor


class ThemeManager:
    """
    Zentraler Theme Manager für die gesamte Anwendung.
    Verwaltet:
    - Basis-Themes (hell/dunkel)
    - Benutzerdefinierte Appearance Profile
    - Dynamisches Laden und Anwenden von Themes
    """
    
    # Basis-Themes (hell/dunkel)
    _base_themes = {
        "light": {
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
        },
        "dark": {
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
        }
    }
    
    # Vordefinierte Profile
    _predefined_profiles = {
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
        },
        "Blau-Grau": {
            "modus": "dunkel",
            "hintergrund_app": "#263238",
            "hintergrund_panel": "#37474f",
            "hintergrund_seitenleiste": "#2c3a41",
            "sidebar_panel_bg": "#324148",
            "filter_panel_bg": "#37474f",
            "text": "#eceff1",
            "text_gedimmt": "#b0bec5",
            "akzent": "#42a5f5",
            "tabelle_hintergrund": "#263238",
            "tabelle_alt": "#2e3c43",
            "tabelle_header": "#37474f",
            "tabelle_gitter": "#455a64",
            "auswahl_hintergrund": "#42a5f5",
            "auswahl_text": "#ffffff",
            "negativ_text": "#ef5350",
            "typ_einnahmen": "#66bb6a",
            "typ_ausgaben": "#ef5350",
            "typ_ersparnisse": "#42a5f5",
            "schriftgroesse": 10,
        },
        "Grün-Natur": {
            "modus": "hell",
            "hintergrund_app": "#f1f8e9",
            "hintergrund_panel": "#dcedc8",
            "hintergrund_seitenleiste": "#c5e1a5",
            "sidebar_panel_bg": "#d4e9bc",
            "filter_panel_bg": "#dcedc8",
            "text": "#33691e",
            "text_gedimmt": "#558b2f",
            "akzent": "#7cb342",
            "tabelle_hintergrund": "#f1f8e9",
            "tabelle_alt": "#e8f5e0",
            "tabelle_header": "#dcedc8",
            "tabelle_gitter": "#aed581",
            "auswahl_hintergrund": "#7cb342",
            "auswahl_text": "#ffffff",
            "negativ_text": "#d32f2f",
            "typ_einnahmen": "#43a047",
            "typ_ausgaben": "#e53935",
            "typ_ersparnisse": "#1e88e5",
            "schriftgroesse": 10,
        },
        "Lila-Premium": {
            "modus": "dunkel",
            "hintergrund_app": "#1a1a2e",
            "hintergrund_panel": "#16213e",
            "hintergrund_seitenleiste": "#0f1626",
            "sidebar_panel_bg": "#141d33",
            "filter_panel_bg": "#16213e",
            "text": "#eee4e1",
            "text_gedimmt": "#c1b8b5",
            "akzent": "#bb86fc",
            "tabelle_hintergrund": "#1a1a2e",
            "tabelle_alt": "#1e1e35",
            "tabelle_header": "#16213e",
            "tabelle_gitter": "#2d3561",
            "auswahl_hintergrund": "#bb86fc",
            "auswahl_text": "#000000",
            "negativ_text": "#cf6679",
            "typ_einnahmen": "#03dac6",
            "typ_ausgaben": "#cf6679",
            "typ_ersparnisse": "#bb86fc",
            "schriftgroesse": 10,
        },
        "Orange-Warm": {
            "modus": "hell",
            "hintergrund_app": "#fff8e1",
            "hintergrund_panel": "#ffecb3",
            "hintergrund_seitenleiste": "#ffe082",
            "sidebar_panel_bg": "#ffe69c",
            "filter_panel_bg": "#ffecb3",
            "text": "#e65100",
            "text_gedimmt": "#f57c00",
            "akzent": "#ff9800",
            "tabelle_hintergrund": "#fff8e1",
            "tabelle_alt": "#fff3d8",
            "tabelle_header": "#ffecb3",
            "tabelle_gitter": "#ffd54f",
            "auswahl_hintergrund": "#ff9800",
            "auswahl_text": "#ffffff",
            "negativ_text": "#d32f2f",
            "typ_einnahmen": "#43a047",
            "typ_ausgaben": "#e53935",
            "typ_ersparnisse": "#1e88e5",
            "schriftgroesse": 10,
        }
    }
    
    def __init__(self, settings):
        """
        Initialisiert den Theme Manager.
        
        Args:
            settings: Settings-Instanz zur Speicherung von Profilen
        """
        self.settings = settings
        self.current_profile = None
        self.custom_profiles = {}
        self._load_profiles()
    
    def _load_profiles(self):
        """Lädt alle Profile aus den Settings."""
        # Benutzerdefinierte Profile laden
        profiles = self.settings.get('appearance_profiles', {})
        if isinstance(profiles, dict):
            self.custom_profiles = profiles.copy()
        
        # Aktives Profil laden
        active = self.settings.get('appearance_profile_active', '')
        if active:
            self.current_profile = active
        elif self.settings.theme:
            # Fallback auf altes Theme-System
            self.current_profile = "Standard Hell" if self.settings.theme == "light" else "Standard Dunkel"
    
    def _save_profiles(self):
        """Speichert alle Profile in die Settings."""
        self.settings.set('appearance_profiles', self.custom_profiles)
        if self.current_profile:
            self.settings.set('appearance_profile_active', self.current_profile)
        self.settings.save()
    
    def get_all_profiles(self) -> Dict[str, Dict[str, Any]]:
        """
        Gibt alle verfügbaren Profile zurück (vordefiniert + benutzerdefiniert).
        
        Returns:
            Dictionary mit Profilnamen als Keys
        """
        profiles = self._predefined_profiles.copy()
        profiles.update(self.custom_profiles)
        return profiles
    
    def get_profile(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Gibt ein spezifisches Profil zurück.
        
        Args:
            name: Name des Profils
        
        Returns:
            Profil-Dictionary oder None
        """
        all_profiles = self.get_all_profiles()
        return all_profiles.get(name)
    
    def get_current_profile(self) -> Optional[Dict[str, Any]]:
        """
        Gibt das aktuell aktive Profil zurück.
        
        Returns:
            Profil-Dictionary oder None
        """
        if self.current_profile:
            return self.get_profile(self.current_profile)
        return None
    
    def set_current_profile(self, name: str):
        """
        Setzt das aktuelle Profil.
        
        Args:
            name: Name des Profils
        """
        if name in self.get_all_profiles():
            self.current_profile = name
            self._save_profiles()
    
    def create_profile(self, name: str, profile_data: Dict[str, Any]) -> bool:
        """
        Erstellt ein neues benutzerdefiniertes Profil.
        
        Args:
            name: Name des Profils
            profile_data: Profil-Daten
        
        Returns:
            True bei Erfolg, False wenn Name bereits existiert
        """
        if name in self._predefined_profiles:
            return False  # Vordefinierte Profile können nicht überschrieben werden
        
        self.custom_profiles[name] = profile_data
        self._save_profiles()
        return True
    
    def update_profile(self, name: str, profile_data: Dict[str, Any]) -> bool:
        """
        Aktualisiert ein bestehendes Profil.
        
        Args:
            name: Name des Profils
            profile_data: Neue Profil-Daten
        
        Returns:
            True bei Erfolg, False wenn Profil nicht existiert oder vordefiniert ist
        """
        if name in self._predefined_profiles:
            return False  # Vordefinierte Profile können nicht geändert werden
        
        if name not in self.custom_profiles:
            return False
        
        self.custom_profiles[name] = profile_data
        self._save_profiles()
        return True
    
    def delete_profile(self, name: str) -> bool:
        """
        Löscht ein benutzerdefiniertes Profil.
        
        Args:
            name: Name des Profils
        
        Returns:
            True bei Erfolg, False wenn Profil nicht existiert oder vordefiniert ist
        """
        if name in self._predefined_profiles:
            return False  # Vordefinierte Profile können nicht gelöscht werden
        
        if name not in self.custom_profiles:
            return False
        
        del self.custom_profiles[name]
        
        # Falls das gelöschte Profil aktiv war, auf Standard zurücksetzen
        if self.current_profile == name:
            self.current_profile = "Standard Hell"
        
        self._save_profiles()
        return True
    
    def is_predefined(self, name: str) -> bool:
        """
        Prüft ob ein Profil vordefiniert ist.
        
        Args:
            name: Name des Profils
        
        Returns:
            True wenn vordefiniert
        """
        return name in self._predefined_profiles
    
    def export_profile(self, name: str, filepath: str) -> bool:
        """
        Exportiert ein Profil als JSON-Datei.
        
        Args:
            name: Name des Profils
            filepath: Ziel-Dateipfad
        
        Returns:
            True bei Erfolg
        """
        profile = self.get_profile(name)
        if not profile:
            return False
        
        try:
            export_data = {
                "name": name,
                "profile": profile,
                "version": "1.0"
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False
    
    def import_profile(self, filepath: str) -> Optional[str]:
        """
        Importiert ein Profil aus einer JSON-Datei.
        
        Args:
            filepath: Quell-Dateipfad
        
        Returns:
            Name des importierten Profils oder None bei Fehler
        """
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            name = data.get('name', 'Importiert')
            profile = data.get('profile', {})
            
            # Namenskonflikte vermeiden
            original_name = name
            counter = 1
            while name in self.get_all_profiles():
                name = f"{original_name} ({counter})"
                counter += 1
            
            self.custom_profiles[name] = profile
            self._save_profiles()
            return name
        except Exception:
            return None
    
    def build_stylesheet(self, profile: Optional[Dict[str, Any]] = None) -> str:
        """
        Erstellt ein komplettes Stylesheet aus einem Profil.
        
        Args:
            profile: Profil-Dictionary (optional, verwendet aktuelles Profil wenn None)
        
        Returns:
            QSS Stylesheet als String
        """
        if profile is None:
            profile = self.get_current_profile()
            if profile is None:
                profile = self._base_themes["light"]
        
        # Werte extrahieren
        app_bg = profile.get("hintergrund_app", "#ffffff")
        panel_bg = profile.get("hintergrund_panel", "#f6f7f9")
        side_bg = profile.get("hintergrund_seitenleiste", "#f0f2f5")
        sidebar_panel_bg = profile.get("sidebar_panel_bg", side_bg)
        filter_panel_bg = profile.get("filter_panel_bg", panel_bg)
        text = profile.get("text", "#111111")
        text_muted = profile.get("text_gedimmt", "#444444")
        accent = profile.get("akzent", "#2f80ed")
        
        table_bg = profile.get("tabelle_hintergrund", "#ffffff")
        table_alt = profile.get("tabelle_alt", "#f7f9fc")
        table_header = profile.get("tabelle_header", "#eef2f7")
        grid = profile.get("tabelle_gitter", "#d6dbe3")
        sel_bg = profile.get("auswahl_hintergrund", "#2f80ed")
        sel_text = profile.get("auswahl_text", "#ffffff")
        
        negative = profile.get("negativ_text", "#e74c3c")
        income = profile.get("typ_einnahmen", "#2ecc71")
        expense = profile.get("typ_ausgaben", "#e74c3c")
        savings = profile.get("typ_ersparnisse", "#3498db")
        
        font_size = int(profile.get("schriftgroesse", 10))
        
        # Berechne abgeleitete Farben
        hover_bg = self._adjust_color(accent, 10)
        pressed_bg = self._adjust_color(accent, -10)
        border_color = self._adjust_color(grid, -10)
        
        qss = f"""
        /* === BASIS === */
        QWidget {{
            font-size: {font_size}pt;
            color: {text};
            background-color: {app_bg};
        }}
        
        QMainWindow, QDialog {{
            background-color: {app_bg};
        }}
        
        /* === PANELS & GROUPBOX === */
        QGroupBox {{
            background-color: {panel_bg};
            border: 2px solid {border_color};
            border-radius: 8px;
            margin-top: 12px;
            padding: 10px;
            font-weight: bold;
        }}
        
        QGroupBox::title {{
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 6px;
            color: {text};
        }}
        
        /* === MENÜ === */
        QMenuBar {{
            background-color: {panel_bg};
            color: {text};
            border-bottom: 1px solid {border_color};
            padding: 4px;
        }}
        
        QMenuBar::item {{
            background-color: transparent;
            padding: 6px 12px;
            border-radius: 4px;
        }}
        
        QMenuBar::item:selected {{
            background-color: {hover_bg};
        }}
        
        QMenu {{
            background-color: {panel_bg};
            color: {text};
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 4px;
        }}
        
        QMenu::item {{
            padding: 6px 30px 6px 10px;
            border-radius: 3px;
        }}
        
        QMenu::item:selected {{
            background-color: {accent};
            color: {sel_text};
        }}
        
        QMenu::separator {{
            height: 1px;
            background-color: {border_color};
            margin: 4px 8px;
        }}
        
        /* === TABS === */
        QTabWidget::pane {{
            border: 1px solid {border_color};
            background-color: {app_bg};
            border-radius: 4px;
        }}
        
        QTabBar::tab {{
            background-color: {panel_bg};
            color: {text};
            border: 1px solid {border_color};
            padding: 8px 16px;
            margin-right: 2px;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
        }}
        
        QTabBar::tab:selected {{
            background-color: {app_bg};
            border-bottom-color: {app_bg};
            font-weight: bold;
        }}
        
        QTabBar::tab:hover {{
            background-color: {hover_bg};
        }}
        
        /* === TABELLEN === */
        QTableWidget {{
            background-color: {table_bg};
            alternate-background-color: {table_alt};
            gridline-color: {grid};
            color: {text};
            border: 1px solid {border_color};
            border-radius: 4px;
        }}
        
        QTableWidget::item {{
            padding: 4px;
        }}
        
        QTableWidget::item:selected {{
            background-color: {sel_bg};
            color: {sel_text};
        }}
        
        QHeaderView::section {{
            background-color: {table_header};
            color: {text};
            padding: 6px;
            border: none;
            border-right: 1px solid {grid};
            border-bottom: 1px solid {grid};
            font-weight: bold;
        }}
        
        QHeaderView::section:first {{
            border-top-left-radius: 4px;
        }}
        
        QHeaderView::section:last {{
            border-top-right-radius: 4px;
            border-right: none;
        }}
        
        /* === BUTTONS === */
        QPushButton {{
            background-color: {accent};
            color: {sel_text};
            border: none;
            padding: 6px 16px;
            border-radius: 4px;
            font-weight: 500;
        }}
        
        QPushButton:hover {{
            background-color: {hover_bg};
        }}
        
        QPushButton:pressed {{
            background-color: {pressed_bg};
        }}
        
        QPushButton:disabled {{
            background-color: {grid};
            color: {text_muted};
        }}
        
        /* === INPUTS === */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox, QDateEdit {{
            background-color: {table_bg};
            color: {text};
            border: 1px solid {border_color};
            padding: 6px;
            border-radius: 4px;
        }}
        
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, 
        QComboBox:focus, QDateEdit:focus {{
            border: 2px solid {accent};
        }}
        
        QComboBox::drop-down {{
            border: none;
            background-color: {panel_bg};
            width: 20px;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }}
        
        QComboBox::down-arrow {{
            image: none;
            border-left: 5px solid transparent;
            border-right: 5px solid transparent;
            border-top: 5px solid {text};
            margin-right: 5px;
        }}
        
        QComboBox QAbstractItemView {{
            background-color: {panel_bg};
            color: {text};
            selection-background-color: {accent};
            selection-color: {sel_text};
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 4px;
        }}
        
        /* === SPINBOX BUTTONS === */
        QSpinBox::up-button, QDoubleSpinBox::up-button,
        QSpinBox::down-button, QDoubleSpinBox::down-button {{
            background-color: {panel_bg};
            border: none;
            width: 16px;
        }}
        
        QSpinBox::up-button:hover, QDoubleSpinBox::up-button:hover,
        QSpinBox::down-button:hover, QDoubleSpinBox::down-button:hover {{
            background-color: {hover_bg};
        }}
        
        /* === CHECKBOXEN & RADIO === */
        QCheckBox, QRadioButton {{
            color: {text};
            spacing: 8px;
        }}
        
        QCheckBox::indicator, QRadioButton::indicator {{
            width: 18px;
            height: 18px;
            border: 2px solid {border_color};
            background-color: {table_bg};
            border-radius: 3px;
        }}
        
        QCheckBox::indicator:checked, QRadioButton::indicator:checked {{
            background-color: {accent};
            border-color: {accent};
        }}
        
        /* === SCROLLBARS === */
        QScrollBar:vertical {{
            background-color: {panel_bg};
            width: 14px;
            border: none;
            border-radius: 7px;
            margin: 0;
        }}
        
        QScrollBar::handle:vertical {{
            background-color: {border_color};
            min-height: 20px;
            border-radius: 7px;
            margin: 2px;
        }}
        
        QScrollBar::handle:vertical:hover {{
            background-color: {text_muted};
        }}
        
        QScrollBar:horizontal {{
            background-color: {panel_bg};
            height: 14px;
            border: none;
            border-radius: 7px;
            margin: 0;
        }}
        
        QScrollBar::handle:horizontal {{
            background-color: {border_color};
            min-width: 20px;
            border-radius: 7px;
            margin: 2px;
        }}
        
        QScrollBar::handle:horizontal:hover {{
            background-color: {text_muted};
        }}
        
        QScrollBar::add-line, QScrollBar::sub-line {{
            background: none;
            border: none;
        }}
        
        QScrollBar::add-page, QScrollBar::sub-page {{
            background: none;
        }}
        
        /* === PROGRESS BAR === */
        QProgressBar {{
            background-color: {panel_bg};
            border: 1px solid {border_color};
            border-radius: 4px;
            color: {text};
            text-align: center;
            height: 20px;
        }}
        
        QProgressBar::chunk {{
            background-color: {accent};
            border-radius: 3px;
        }}
        
        /* === STATUS BAR === */
        QStatusBar {{
            background-color: {panel_bg};
            color: {text};
            border-top: 1px solid {border_color};
        }}
        
        /* === LABELS === */
        QLabel {{
            color: {text};
        }}
        
        QLabel#kpi_label {{
            color: {text_muted};
            font-size: {font_size - 1}pt;
        }}
        
        QLabel#info_label {{
            padding: 10px;
            background-color: {panel_bg};
            border: 1px solid {border_color};
            border-radius: 5px;
        }}
        
        /* === SPEZIAL: TYP-FARBEN === */
        QLabel#typ_einnahmen {{
            color: {income};
            font-weight: bold;
        }}
        
        QLabel#typ_ausgaben {{
            color: {expense};
            font-weight: bold;
        }}
        
        QLabel#typ_ersparnisse {{
            color: {savings};
            font-weight: bold;
        }}
        
        /* === NEGATIVE WERTE === */
        QLabel#negativ {{
            color: {negative};
        }}
        
        /* === TOOLTIPS === */
        QToolTip {{
            background-color: {panel_bg};
            color: {text};
            border: 1px solid {border_color};
            border-radius: 4px;
            padding: 5px;
        }}
        """
        
        return qss
    
    def apply_theme(self, app: Optional[QApplication] = None, 
                    profile_name: Optional[str] = None):
        """
        Wendet ein Theme auf die Anwendung an.
        
        Args:
            app: QApplication Instanz (optional, wird automatisch geholt wenn None)
            profile_name: Name des Profils (optional, verwendet aktuelles wenn None)
        """
        if app is None:
            app = QApplication.instance()
            if app is None:
                return
        
        # Profil bestimmen
        if profile_name:
            profile = self.get_profile(profile_name)
            if profile:
                self.current_profile = profile_name
        else:
            profile = self.get_current_profile()
        
        # Stylesheet erstellen und anwenden
        stylesheet = self.build_stylesheet(profile)
        app.setStyleSheet(stylesheet)
        
        # Settings speichern
        self._save_profiles()
    
    def apply_base_theme(self, app: Optional[QApplication] = None, 
                         theme: str = "light"):
        """
        Wendet ein Basis-Theme an (light/dark).
        
        Args:
            app: QApplication Instanz
            theme: "light" oder "dark"
        """
        if theme not in self._base_themes:
            theme = "light"
        
        profile = self._base_themes[theme]
        stylesheet = self.build_stylesheet(profile)
        
        if app is None:
            app = QApplication.instance()
            if app is None:
                return
        
        app.setStyleSheet(stylesheet)
    
    @staticmethod
    def _adjust_color(color: str, percent: int) -> str:
        """
        Passt eine Farbe um einen Prozentsatz an (heller/dunkler).
        
        Args:
            color: Hex-Farbcode
            percent: Prozent (+/-), positiv = heller, negativ = dunkler
        
        Returns:
            Angepasster Hex-Farbcode
        """
        try:
            qcolor = QColor(color)
            h, s, v, a = qcolor.getHsvF()
            
            # Value anpassen
            v = max(0.0, min(1.0, v + (percent / 100.0)))
            
            qcolor.setHsvF(h, s, v, a)
            return qcolor.name()
        except:
            return color
    
    @staticmethod
    def get_predefined_profiles() -> List[str]:
        """
        Gibt die Namen aller vordefinierten Profile zurück.
        
        Returns:
            Liste von Profilnamen
        """
        return list(ThemeManager._predefined_profiles.keys())
    
    def get_custom_profiles(self) -> List[str]:
        """
        Gibt die Namen aller benutzerdefinierten Profile zurück.
        
        Returns:
            Liste von Profilnamen
        """
        return list(self.custom_profiles.keys())


# Hilfsfunktion für build_stylesheet (von appearance_profiles_dialog.py verwendet)
def build_stylesheet(profile: Dict[str, Any]) -> str:
    """
    Erstellt ein Stylesheet aus einem Profil (für Kompatibilität).
    
    Args:
        profile: Profil-Dictionary
    
    Returns:
        QSS Stylesheet als String
    """
    manager = ThemeManager(None)
    return manager.build_stylesheet(profile)


# Hilfsfunktionen für Kompatibilität mit altem Code
def get_light_theme() -> str:
    """Gibt das helle Basis-Theme zurück (Legacy)."""
    manager = ThemeManager(None)
    return manager.build_stylesheet(ThemeManager._base_themes["light"])


def get_dark_theme() -> str:
    """Gibt das dunkle Basis-Theme zurück (Legacy)."""
    manager = ThemeManager(None)
    return manager.build_stylesheet(ThemeManager._base_themes["dark"])


def apply_theme(app: QApplication, theme: str) -> None:
    """Wendet ein Basis-Theme an (Legacy)."""
    manager = ThemeManager(None)
    manager.apply_base_theme(app, theme)
