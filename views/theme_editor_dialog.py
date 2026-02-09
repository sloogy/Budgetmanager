"""
Vollständiger Theme-Editor - ALLE Themes komplett editierbar
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QScrollArea, QWidget, QFormLayout, QLineEdit,
    QComboBox, QColorDialog, QMessageBox, QGroupBox, QInputDialog,
    QFileDialog
)
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QColor
import json
from pathlib import Path


class ThemeEditorDialog(QDialog):
    """Vollständiger Theme-Editor für alle Themes"""
    
    def __init__(self, settings, theme_manager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.theme_manager = theme_manager
        self.current_theme = None
        self.color_buttons = {}
        
        self._loading = False
        self.setWindowTitle("Theme-Editor - Alle Themes editierbar")
        self.resize(1000, 700)
        
        self._setup_ui()
        self._load_themes()
        
    def _setup_ui(self):
        """Setup UI"""
        layout = QHBoxLayout(self)
        
        # Links: Theme-Liste
        left = QVBoxLayout()
        left.addWidget(QLabel("<b>Verfügbare Themes:</b>"))
        
        self.theme_list = QListWidget()
        self.theme_list.currentTextChanged.connect(self._on_theme_selected)
        left.addWidget(self.theme_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("➕ Neu")
        self.btn_duplicate = QPushButton("📋 Duplizieren")
        self.btn_delete = QPushButton("🗑️ Löschen")
        self.btn_reset = QPushButton("↺ Zurücksetzen")
        
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_duplicate)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_reset)
        left.addLayout(btn_layout)
        
        # Import/Export
        io_layout = QHBoxLayout()
        self.btn_import = QPushButton("📥 Import")
        self.btn_export = QPushButton("📤 Export")
        io_layout.addWidget(self.btn_import)
        io_layout.addWidget(self.btn_export)
        left.addLayout(io_layout)
        
        # Apply Button
        self.btn_apply = QPushButton("✅ Anwenden")
        self.btn_apply.setStyleSheet("background-color: #2f80ed; color: white; font-weight: bold; padding: 10px;")
        left.addWidget(self.btn_apply)
        
        layout.addLayout(left, 1)
        
        # Rechts: Editor
        right = QVBoxLayout()
        right.addWidget(QLabel("<h2>Theme bearbeiten</h2>"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.editor_layout = QVBoxLayout(scroll_widget)
        
        # Name & Modus
        basic_group = QGroupBox("Basis-Einstellungen")
        basic_form = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)  # Name nicht änderbar
        basic_form.addRow("Name:", self.name_edit)
        
        self.modus_combo = QComboBox()
        self.modus_combo.addItems(["hell", "dunkel"])
        self.modus_combo.currentTextChanged.connect(self._on_changed)
        basic_form.addRow("Modus:", self.modus_combo)
        
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems([str(i) for i in range(8, 17)])
        self.font_size_combo.currentTextChanged.connect(self._on_changed)
        basic_form.addRow("Schriftgröße:", self.font_size_combo)
        
        self.editor_layout.addWidget(basic_group)
        
        # Farb-Gruppen
        self._create_color_group("Hintergründe", [
            ("hintergrund_app", "App-Hintergrund"),
            ("hintergrund_panel", "Panel-Hintergrund"),
            ("hintergrund_seitenleiste", "Seitenleiste"),
        ])
        
        self._create_color_group("Text", [
            ("text", "Haupttext"),
            ("text_gedimmt", "Sekundärtext"),
            ("akzent", "Akzentfarbe"),
        ])
        
        self._create_color_group("Tabellen", [
            ("tabelle_hintergrund", "Hintergrund"),
            ("tabelle_alt", "Alternierend"),
            ("tabelle_header", "Kopfzeile"),
            ("tabelle_gitter", "Gitterlinien"),
            ("auswahl_hintergrund", "Auswahl-Hintergrund"),
            ("auswahl_text", "Auswahl-Text"),
        ])
        
        self._create_color_group("Dropdowns", [
            ("dropdown_bg", "Hintergrund"),
            ("dropdown_text", "Text"),
            ("dropdown_selection", "Auswahl-Hintergrund"),
            ("dropdown_selection_text", "Auswahl-Text"),
            ("dropdown_border", "Rahmen"),
        ])
        
        self._create_color_group("Typ-Farben", [
            ("typ_einnahmen", "Einnahmen"),
            ("typ_ausgaben", "Ausgaben"),
            ("typ_ersparnisse", "Ersparnisse"),
        ])
        
        self._create_color_group("Sonstiges", [
            ("negativ_text", "Negative Zahlen"),
        ])
        
        scroll.setWidget(scroll_widget)
        right.addWidget(scroll)
        
        layout.addLayout(right, 2)
        
        # Signals verbinden
        self.btn_new.clicked.connect(self._new_theme)
        self.btn_duplicate.clicked.connect(self._duplicate_theme)
        self.btn_delete.clicked.connect(self._delete_theme)
        self.btn_reset.clicked.connect(self._reset_theme)
        self.btn_import.clicked.connect(self._import_theme)
        self.btn_export.clicked.connect(self._export_theme)
        self.btn_apply.clicked.connect(self._apply_theme)
    
    def _create_color_group(self, title, colors):
        """Erstelle Farb-Gruppe"""
        group = QGroupBox(title)
        form = QFormLayout(group)
        
        for key, label in colors:
            row = QHBoxLayout()
            
            # Farb-Vorschau
            color_btn = QPushButton()
            color_btn.setFixedSize(100, 30)
            color_btn.setProperty("color_key", key)
            color_btn.clicked.connect(lambda checked, k=key: self._pick_color(k))
            self.color_buttons[key] = color_btn
            
            # Hex-Anzeige
            hex_label = QLabel("#000000")
            hex_label.setProperty("color_key", key)
            
            row.addWidget(color_btn)
            row.addWidget(hex_label)
            row.addStretch()
            
            form.addRow(label + ":", row)
        
        self.editor_layout.addWidget(group)
    
    def _load_themes(self):
        """Lade alle Themes"""
        self.theme_list.clear()
        themes = self.theme_manager.get_all_profiles()
        self.theme_list.addItems(themes)
        
        # Aktuelles Theme auswählen
        current = self.settings.get("active_design_profile", "Standard Hell")
        items = self.theme_list.findItems(current, Qt.MatchExactly)
        if items:
            self.theme_list.setCurrentItem(items[0])
    
    def _on_theme_selected(self, theme_name):
        """Theme wurde ausgewählt"""
        if not theme_name:
            return

        self.current_theme = theme_name
        profile = self.theme_manager.get_profile(theme_name)
        if not profile:
            return

        # Beim Laden KEIN Auto-Save auslösen
        self._loading = True
        try:
            b1 = QSignalBlocker(self.modus_combo)
            b2 = QSignalBlocker(self.font_size_combo)

            # Lade Daten in Editor
            self.name_edit.setText(profile.name)
            self.modus_combo.setCurrentText(profile.get("modus", "hell"))
            self.font_size_combo.setCurrentText(str(profile.get("schriftgroesse", 10)))

            del b1
            del b2

            # Lade alle Farben
            for key, btn in self.color_buttons.items():
                color = profile.get(key, "#ffffff")
                self._set_button_color(btn, color)
        finally:
            self._loading = False

    def _set_button_color(self, button, color_hex):
        """Setze Button-Farbe"""
        button.setStyleSheet(f"background-color: {color_hex}; border: 2px solid #ccc;")
        button.setProperty("current_color", color_hex)  # Speichere als Attribut
        
        # Update Hex-Label
        for widget in self.findChildren(QLabel):
            if widget.property("color_key") == button.property("color_key"):
                widget.setText(color_hex)
    
    def _pick_color(self, key):
        """Farbwähler öffnen"""
        btn = self.color_buttons[key]
        current_color_hex = btn.property("current_color") or "#ffffff"
        current_color = QColor(current_color_hex)
        
        color = QColorDialog.getColor(current_color, self, "Farbe wählen")
        if color.isValid():
            self._set_button_color(btn, color.name())
            self._on_changed()
    
    def _on_changed(self):
        """Daten wurden geändert"""
        if not self.current_theme:
            return
        if getattr(self, "_loading", False):
            return
        
        # Sammle alle Daten
        data = {
            "modus": self.modus_combo.currentText(),
            "schriftgroesse": int(self.font_size_combo.currentText()),
        }
        
        # Alle Farben (aus Property lesen)
        for key, btn in self.color_buttons.items():
            color = btn.property("current_color") or "#000000"
            data[key] = color
        
        # Speichere sofort
        self.theme_manager.update_profile(self.current_theme, data)
    
    def _new_theme(self):
        """Neues Theme erstellen"""
        name, ok = QInputDialog.getText(self, "Neues Theme", "Theme-Name:")
        if ok and name:
            # Basis von Standard Hell
            base = self.theme_manager.get_profile("Standard Hell")
            if base:
                self.theme_manager.update_profile(name, base.to_dict())
                self._load_themes()
                
                # Auswählen
                items = self.theme_list.findItems(name, Qt.MatchExactly)
                if items:
                    self.theme_list.setCurrentItem(items[0])
    
    def _duplicate_theme(self):
        """Theme duplizieren"""
        if not self.current_theme:
            return
        
        name, ok = QInputDialog.getText(
            self, "Theme duplizieren", 
            "Neuer Name:",
            text=f"{self.current_theme} (Kopie)"
        )
        
        if ok and name:
            profile = self.theme_manager.get_profile(self.current_theme)
            if profile:
                self.theme_manager.update_profile(name, profile.to_dict())
                self._load_themes()
                
                items = self.theme_list.findItems(name, Qt.MatchExactly)
                if items:
                    self.theme_list.setCurrentItem(items[0])
    
    def _delete_theme(self):
        """Theme löschen"""
        if not self.current_theme:
            return

        # Mitgelieferte Themes können nicht gelöscht werden – nur Overrides via 'Zurücksetzen' entfernen.
        if self.theme_manager.is_bundled(self.current_theme) and not self.theme_manager.has_override(self.current_theme):
            QMessageBox.warning(
                self,
                "Fehler",
                "Mitgelieferte Themes können nicht gelöscht werden.\n\n"
                "Verwenden Sie 'Zurücksetzen', um lokale Änderungen (Overrides) zu entfernen.",
            )
            return

        reply = QMessageBox.question(
            self,
            "Theme löschen",
            f"Möchten Sie '{self.current_theme}' wirklich löschen?\n\n"
            "(Hinweis: Bei mitgelieferten Themes wird nur das Override entfernt.)",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.theme_manager.delete_profile(self.current_theme)
            self._load_themes()

    def _reset_theme(self):
        """Theme zurücksetzen = Override entfernen (falls vorhanden)."""
        if not self.current_theme:
            return

        if not self.theme_manager.is_bundled(self.current_theme) and not self.theme_manager.has_override(self.current_theme):
            QMessageBox.information(
                self,
                "Hinweis",
                "Dieses Theme hat kein mitgeliefertes Standard-Profil zum Zurücksetzen.\n"
                "(Tipp: Eigene Themes können gelöscht werden.)",
            )
            return

        reply = QMessageBox.question(
            self,
            "Zurücksetzen",
            f"Möchten Sie '{self.current_theme}' wirklich zurücksetzen?\n\n"
            "Alle lokalen Änderungen (Overrides) gehen verloren!",
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.theme_manager.reset_profile(self.current_theme)
            self._on_theme_selected(self.current_theme)  # Neu laden
            QMessageBox.information(self, "Erfolg", "Theme wurde zurückgesetzt!")

    def _import_theme(self):
        """Theme importieren"""
        file, _ = QFileDialog.getOpenFileName(
            self, "Theme importieren", "", "JSON (*.json)"
        )
        
        if not file:
            return
        
        try:
            with open(file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            name = data.get("name", "Importiertes Theme")
            
            # Falls Name existiert, frage nach neuem Namen
            if name in self.theme_manager.get_all_profiles():
                name, ok = QInputDialog.getText(
                    self, "Name existiert", 
                    "Theme-Name existiert bereits. Neuer Name:",
                    text=f"{name} (Import)"
                )
                if not ok:
                    return
            
            # Speichere Theme
            data.pop("name", None)
            self.theme_manager.update_profile(name, data)
            self._load_themes()
            
            QMessageBox.information(self, "Erfolg", f"Theme '{name}' wurde importiert!")
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Import fehlgeschlagen:\n{e}")
    
    def _export_theme(self):
        """Theme exportieren"""
        if not self.current_theme:
            return
        
        file, _ = QFileDialog.getSaveFileName(
            self, "Theme exportieren", 
            f"{self.current_theme}.json",
            "JSON (*.json)"
        )
        
        if not file:
            return
        
        try:
            profile = self.theme_manager.get_profile(self.current_theme)
            if profile:
                with open(file, 'w', encoding='utf-8') as f:
                    data = {"name": self.current_theme, **profile.to_dict()}
                    json.dump(data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "Erfolg", "Theme wurde exportiert!")
                
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Export fehlgeschlagen:\n{e}")
    
    def _apply_theme(self):
        """Theme anwenden"""
        if self.current_theme:
            self.theme_manager.apply_theme(profile_name=self.current_theme)
            QMessageBox.information(
                self, "Erfolg", 
                f"Theme '{self.current_theme}' wurde angewendet!"
            )
