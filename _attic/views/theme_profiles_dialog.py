from __future__ import annotations
import sqlite3
import json

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QListWidget, QListWidgetItem, QMessageBox, QInputDialog,
    QColorDialog, QGroupBox, QFormLayout
)
from PySide6.QtGui import QColor
from PySide6.QtCore import Qt

from theme_manager import ThemeManager


class ThemeProfilesDialog(QDialog):
    def __init__(self, parent, conn: sqlite3.Connection, theme_manager: ThemeManager):
        super().__init__(parent)
        self.conn = conn
        self.theme_manager = theme_manager
        
        self.setWindowTitle("Erscheinungsprofile")
        self.setModal(True)
        self.resize(700, 500)
        
        # Buttons
        self.btn_create = QPushButton("Neues Profil")
        self.btn_apply = QPushButton("Anwenden")
        self.btn_delete = QPushButton("Löschen")
        self.btn_export = QPushButton("Exportieren")
        self.btn_import = QPushButton("Importieren")
        self.btn_close = QPushButton("Schließen")
        
        # Liste der Profile
        self.profile_list = QListWidget()
        
        # Vorschau-Bereich
        preview_group = QGroupBox("Vorschau")
        preview_layout = QVBoxLayout()
        
        self.preview_primary = QLabel("Primärfarbe")
        self.preview_secondary = QLabel("Sekundärfarbe")
        self.preview_background = QLabel("Hintergrund")
        self.preview_text = QLabel("Textfarbe")
        self.preview_accent = QLabel("Akzentfarbe")
        
        for label in [self.preview_primary, self.preview_secondary, 
                     self.preview_background, self.preview_text, self.preview_accent]:
            label.setMinimumHeight(30)
            label.setAutoFillBackground(True)
            preview_layout.addWidget(label)
        
        preview_group.setLayout(preview_layout)
        
        # Layout
        btn_layout1 = QHBoxLayout()
        btn_layout1.addWidget(self.btn_create)
        btn_layout1.addWidget(self.btn_apply)
        btn_layout1.addWidget(self.btn_delete)
        
        btn_layout2 = QHBoxLayout()
        btn_layout2.addWidget(self.btn_export)
        btn_layout2.addWidget(self.btn_import)
        btn_layout2.addStretch()
        btn_layout2.addWidget(self.btn_close)
        
        content_layout = QHBoxLayout()
        
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Gespeicherte Profile:"))
        left_layout.addWidget(self.profile_list)
        left_layout.addLayout(btn_layout1)
        
        content_layout.addLayout(left_layout, 2)
        content_layout.addWidget(preview_group, 1)
        
        layout = QVBoxLayout()
        layout.addWidget(QLabel("<b>Erscheinungsprofile verwalten</b>"))
        layout.addSpacing(10)
        layout.addLayout(content_layout)
        layout.addLayout(btn_layout2)
        self.setLayout(layout)
        
        # Connections
        self.btn_create.clicked.connect(self.create_profile)
        self.btn_apply.clicked.connect(self.apply_profile)
        self.btn_delete.clicked.connect(self.delete_profile)
        self.btn_export.clicked.connect(self.export_profile)
        self.btn_import.clicked.connect(self.import_profile)
        self.btn_close.clicked.connect(self.accept)
        self.profile_list.currentItemChanged.connect(self.update_preview)
        
        self.refresh_profile_list()
        self._add_default_profiles()
    
    def _add_default_profiles(self):
        """Fügt Standard-Profile hinzu, falls noch keine existieren"""
        cur = self.conn.execute("SELECT COUNT(*) FROM theme_profiles")
        if cur.fetchone()[0] > 0:
            return
        
        default_profiles = [
            ("Standard", {
                "primary_color": "#2c3e50",
                "secondary_color": "#34495e",
                "background_color": "#ecf0f1",
                "text_color": "#2c3e50",
                "accent_color": "#3498db"
            }),
            ("Hell", {
                "primary_color": "#ffffff",
                "secondary_color": "#f5f5f5",
                "background_color": "#fafafa",
                "text_color": "#333333",
                "accent_color": "#2196F3"
            }),
            ("Dunkel", {
                "primary_color": "#1e1e1e",
                "secondary_color": "#2d2d2d",
                "background_color": "#121212",
                "text_color": "#e0e0e0",
                "accent_color": "#bb86fc"
            }),
            ("Blau", {
                "primary_color": "#1565c0",
                "secondary_color": "#1976d2",
                "background_color": "#e3f2fd",
                "text_color": "#0d47a1",
                "accent_color": "#42a5f5"
            }),
            ("Grün", {
                "primary_color": "#2e7d32",
                "secondary_color": "#388e3c",
                "background_color": "#e8f5e9",
                "text_color": "#1b5e20",
                "accent_color": "#66bb6a"
            })
        ]
        
        for name, settings in default_profiles:
            self._save_profile(name, settings)
        
        self.refresh_profile_list()
    
    def _save_profile(self, name: str, settings: dict):
        """Speichert ein Profil in der Datenbank"""
        try:
            self.conn.execute(
                "INSERT OR REPLACE INTO theme_profiles (name, settings) VALUES (?, ?)",
                (name, json.dumps(settings))
            )
            self.conn.commit()
        except Exception as e:
            print(f"Fehler beim Speichern des Profils: {e}")
    
    def refresh_profile_list(self):
        self.profile_list.clear()
        cur = self.conn.execute("SELECT name, settings FROM theme_profiles ORDER BY name")
        
        for row in cur.fetchall():
            name = row[0]
            settings = json.loads(row[1])
            
            item = QListWidgetItem(name)
            item.setData(Qt.UserRole, settings)
            self.profile_list.addItem(item)
        
        if self.profile_list.count() > 0:
            self.profile_list.setCurrentRow(0)
    
    def update_preview(self, current, previous):
        if not current:
            return
        
        settings = current.data(Qt.UserRole)
        
        # Vorschau aktualisieren
        self._set_preview_color(self.preview_primary, settings.get("primary_color", "#2c3e50"))
        self._set_preview_color(self.preview_secondary, settings.get("secondary_color", "#34495e"))
        self._set_preview_color(self.preview_background, settings.get("background_color", "#ecf0f1"))
        self._set_preview_color(self.preview_text, settings.get("text_color", "#2c3e50"))
        self._set_preview_color(self.preview_accent, settings.get("accent_color", "#3498db"))
    
    def _set_preview_color(self, label: QLabel, color: str):
        """Setzt die Hintergrundfarbe eines Labels"""
        qcolor = QColor(color)
        # Textfarbe basierend auf Helligkeit anpassen
        lightness = qcolor.lightness()
        text_color = "#000000" if lightness > 128 else "#ffffff"
        
        label.setStyleSheet(f"""
            QLabel {{
                background-color: {color};
                color: {text_color};
                padding: 5px;
                border-radius: 3px;
            }}
        """)
    
    def create_profile(self):
        # Profil-Editor Dialog
        dlg = CreateProfileDialog(self, self.theme_manager)
        if dlg.exec() == QDialog.Accepted:
            name, settings = dlg.get_data()
            self._save_profile(name, settings)
            self.refresh_profile_list()
    
    def apply_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte ein Profil auswählen.")
            return
        
        settings = item.data(Qt.UserRole)
        
        # Theme-Einstellungen anwenden
        for key, value in settings.items():
            if hasattr(self.theme_manager, f"set_{key}"):
                getattr(self.theme_manager, f"set_{key}")(value)
        
        self.theme_manager.apply()
        
        QMessageBox.information(
            self,
            "Erfolg",
            f"Profil '{item.text()}' wurde angewendet."
        )
    
    def delete_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte ein Profil auswählen.")
            return
        
        name = item.text()
        
        if QMessageBox.question(
            self,
            "Löschen",
            f"Profil '{name}' wirklich löschen?"
        ) != QMessageBox.Yes:
            return
        
        try:
            self.conn.execute("DELETE FROM theme_profiles WHERE name = ?", (name,))
            self.conn.commit()
            self.refresh_profile_list()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Löschen fehlgeschlagen:\n{e}")
    
    def export_profile(self):
        item = self.profile_list.currentItem()
        if not item:
            QMessageBox.information(self, "Hinweis", "Bitte ein Profil auswählen.")
            return
        
        # Hier könnte man ein JSON-Export implementieren
        QMessageBox.information(self, "Info", "Export-Funktion wird in einer zukünftigen Version hinzugefügt.")
    
    def import_profile(self):
        # Hier könnte man einen JSON-Import implementieren
        QMessageBox.information(self, "Info", "Import-Funktion wird in einer zukünftigen Version hinzugefügt.")


class CreateProfileDialog(QDialog):
    def __init__(self, parent, theme_manager: ThemeManager):
        super().__init__(parent)
        self.theme_manager = theme_manager
        
        self.setWindowTitle("Neues Farbprofil erstellen")
        self.setModal(True)
        
        self.colors = {
            "primary_color": "#2c3e50",
            "secondary_color": "#34495e",
            "background_color": "#ecf0f1",
            "text_color": "#2c3e50",
            "accent_color": "#3498db"
        }
        
        # Farbauswahl-Buttons
        layout = QFormLayout()
        
        self.btn_primary = self._create_color_button("primary_color")
        self.btn_secondary = self._create_color_button("secondary_color")
        self.btn_background = self._create_color_button("background_color")
        self.btn_text = self._create_color_button("text_color")
        self.btn_accent = self._create_color_button("accent_color")
        
        layout.addRow("Primärfarbe:", self.btn_primary)
        layout.addRow("Sekundärfarbe:", self.btn_secondary)
        layout.addRow("Hintergrund:", self.btn_background)
        layout.addRow("Textfarbe:", self.btn_text)
        layout.addRow("Akzentfarbe:", self.btn_accent)
        
        # Name
        from PySide6.QtWidgets import QLineEdit
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Profilname eingeben...")
        layout.addRow("Name:", self.name_edit)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_ok = QPushButton("Erstellen")
        btn_cancel = QPushButton("Abbrechen")
        btn_ok.clicked.connect(self.accept)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_ok)
        btn_layout.addWidget(btn_cancel)
        
        main_layout = QVBoxLayout()
        main_layout.addLayout(layout)
        main_layout.addLayout(btn_layout)
        self.setLayout(main_layout)
    
    def _create_color_button(self, key: str) -> QPushButton:
        """Erstellt einen Farbauswahl-Button"""
        btn = QPushButton(self.colors[key])
        btn.setStyleSheet(f"background-color: {self.colors[key]};")
        btn.clicked.connect(lambda: self._pick_color(key, btn))
        return btn
    
    def _pick_color(self, key: str, button: QPushButton):
        """Öffnet einen Farbauswahl-Dialog"""
        color = QColorDialog.getColor(QColor(self.colors[key]), self)
        if color.isValid():
            self.colors[key] = color.name()
            button.setText(color.name())
            button.setStyleSheet(f"background-color: {color.name()};")
    
    def get_data(self):
        """Gibt Name und Einstellungen zurück"""
        name = self.name_edit.text().strip() or "Neues Profil"
        return name, self.colors
