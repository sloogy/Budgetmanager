from __future__ import annotations

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
from views.ui_colors import ui_colors
import json


import logging
from utils.i18n import tr, trf, display_typ, db_typ_from_display
logger = logging.getLogger(__name__)

class ThemeEditorDialog(QDialog):
    """Vollständiger Theme-Editor für alle Themes"""
    
    def __init__(self, settings, theme_manager, parent=None):
        super().__init__(parent)
        self.settings = settings
        self.theme_manager = theme_manager
        self.current_theme = None
        self.color_buttons = {}
        
        self._loading = False
        self.setWindowTitle(tr("dlg.theme_editor"))
        self.resize(1000, 700)
        
        self._setup_ui()
        self._load_themes()
        
    def _setup_ui(self):
        """Setup UI"""
        layout = QHBoxLayout(self)
        
        # Links: Theme-Liste
        left = QVBoxLayout()
        left.addWidget(QLabel(tr("dlg.bverfuegbare_themesb")))
        
        self.theme_list = QListWidget()
        self.theme_list.currentTextChanged.connect(self._on_theme_selected)
        left.addWidget(self.theme_list)
        
        # Buttons
        btn_layout = QHBoxLayout()
        self.btn_new = QPushButton("➕ " + tr("btn.new_theme"))
        self.btn_duplicate = QPushButton(tr("tracking.ctx.duplicate"))
        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_reset = QPushButton(tr("dlg.zuruecksetzen_1"))
        
        btn_layout.addWidget(self.btn_new)
        btn_layout.addWidget(self.btn_duplicate)
        btn_layout.addWidget(self.btn_delete)
        btn_layout.addWidget(self.btn_reset)
        left.addLayout(btn_layout)
        
        # Import/Export
        io_layout = QHBoxLayout()
        self.btn_import = QPushButton("📥 " + tr("btn.import_theme"))
        self.btn_export = QPushButton("📤 " + tr("btn.export_theme"))
        io_layout.addWidget(self.btn_import)
        io_layout.addWidget(self.btn_export)
        left.addLayout(io_layout)
        
        # Apply Button
        self.btn_apply = QPushButton("✅ " + tr("btn.apply_theme"))
        self.btn_apply.setStyleSheet(f"background-color: {ui_colors(self).accent}; color: white; font-weight: bold; padding: 10px;")
        left.addWidget(self.btn_apply)
        
        layout.addLayout(left, 1)
        
        # Rechts: Editor
        right = QVBoxLayout()
        right.addWidget(QLabel("<h2>" + tr("dlg.theme_edit_title") + "</h2>"))
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.editor_layout = QVBoxLayout(scroll_widget)
        
        # Name & Modus
        basic_group = QGroupBox(tr("grp.base_settings"))
        basic_form = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        self.name_edit.setReadOnly(True)  # Name nicht änderbar
        basic_form.addRow(tr("lbl.theme_name") + ":", self.name_edit)
        
        self.modus_combo = QComboBox()
        self.modus_combo.addItems(["hell", "dunkel"])  # Internal values, not translated
        self.modus_combo.currentTextChanged.connect(self._on_changed)
        basic_form.addRow(tr("lbl.theme_mode") + ":", self.modus_combo)
        
        self.font_size_combo = QComboBox()
        self.font_size_combo.addItems([str(i) for i in range(8, 17)])
        self.font_size_combo.currentTextChanged.connect(self._on_changed)
        basic_form.addRow(tr("dlg.schriftgroesse_1"), self.font_size_combo)
        
        self.editor_layout.addWidget(basic_group)
        
        # Farb-Gruppen
        self._create_color_group(tr("dlg.hintergruende"), [
            ("hintergrund_app", tr("dlg.bg_app")),
            ("hintergrund_panel", tr("dlg.bg_panel")),
            ("hintergrund_seitenleiste", tr("dlg.bg_sidebar")),
        ])
        
        self._create_color_group(tr("dlg.color_text"), [
            ("text", tr("dlg.color_main_text")),
            ("text_gedimmt", tr("dlg.sekundaertext")),
            ("akzent", tr("dlg.color_accent")),
        ])
        
        self._create_color_group(tr("dlg.color_tables"), [
            ("tabelle_hintergrund", tr("dlg.bg_table")),
            ("tabelle_alt", tr("dlg.bg_table_alt")),
            ("tabelle_header", tr("dlg.bg_table_header")),
            ("tabelle_gitter", "Gitterlinien"),
            ("auswahl_hintergrund", "Auswahl-Hintergrund"),
            ("auswahl_text", "Auswahl-Text"),
        ])
        
        self._create_color_group(tr("dlg.hover_mausueber"), [
            ("hover_hintergrund", "Hover-Hintergrund"),
            ("hover_text", "Hover-Text"),
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
            ("typ_ausgaben", tr("kpi.expenses")),
            ("typ_ersparnisse", tr("typ.Ersparnisse")),
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

            # Fallback für Hover-Farben berechnen (für ältere Themes)
            if not profile.get("hover_hintergrund"):
                hover_fb = self.theme_manager._fallback_hover(
                    profile.get("auswahl_hintergrund", "#2f80ed"),
                    profile.get("tabelle_hintergrund", "#ffffff"),
                )
                profile.data.setdefault("hover_hintergrund", hover_fb)
            if not profile.get("hover_text"):
                profile.data.setdefault("hover_text", profile.get("text", "#111111"))

            # Lade alle Farben
            for key, btn in self.color_buttons.items():
                color = profile.get(key, "#ffffff")
                self._set_button_color(btn, color)
        finally:
            self._loading = False

    def _set_button_color(self, button, color_hex):
        """Setze Button-Farbe"""
        button.setStyleSheet(f"background-color: {color_hex}; border: 2px solid {ui_colors(self).border};")
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
        
        color = QColorDialog.getColor(current_color, self, tr("dlg.farbe_waehlen"))
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
        """Theme löschen."""
        if not self.current_theme:
            return

        # Mitgelieferte Themes können nicht gelöscht werden – nur Overrides via tr("dlg.zuruecksetzen") entfernen.
        if self.theme_manager.is_bundled(self.current_theme) and not self.theme_manager.has_override(self.current_theme):
            QMessageBox.warning(
                self,
                "Fehler",
                "Mitgelieferte Themes können nicht gelöscht werden.\n\n" +
                tr("msg.theme_override_hinweis"),
            )
            return

        reply = QMessageBox.question(
            self,
            tr("btn.theme_loeschen"),
            f"Möchten Sie '{self.current_theme}' wirklich löschen?\n\n" +
            tr("msg.hinweis_bei_mitgelieferten_themes"),
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
                "Dieses Theme hat kein mitgeliefertes Standard-Profil zum Zurücksetzen.\n" +
                tr("dlg.tipp_eigene_themes_koennen"),
            )
            return

        reply = QMessageBox.question(
            self,
            tr("dlg.zuruecksetzen"),
            f"Möchten Sie '{self.current_theme}' wirklich zurücksetzen?\n\n" +
            tr("dlg.alle_lokalen_aenderungen_overrides"),
            QMessageBox.Yes | QMessageBox.No,
        )

        if reply == QMessageBox.Yes:
            self.theme_manager.reset_profile(self.current_theme)
            self._on_theme_selected(self.current_theme)  # Neu laden
            QMessageBox.information(self, "Erfolg", tr("dlg.theme_wurde_zurueckgesetzt"))

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
            
            QMessageBox.information(self, tr("dlg.backup_erfolg"), trf("msg.theme_importiert", name=name))
            
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Import fehlgeschlagen:\n{e}")
    
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
                
                QMessageBox.information(self, "Erfolg", tr("dlg.theme_wurde_exportiert"))
                
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Export fehlgeschlagen:\n{e}")
    
    def _apply_theme(self):
        """Theme anwenden"""
        if self.current_theme:
            # Cache leeren damit das frisch gespeicherte Profil geladen wird
            self.theme_manager._current_profile = None
            self.theme_manager.apply_theme(profile_name=self.current_theme)
            # Alle offenen Fenster zum Neuzeichnen zwingen
            from PySide6.QtWidgets import QApplication
            for w in QApplication.allWidgets():
                try:
                    w.update()
                except Exception:
                    pass
            QMessageBox.information(
                self, tr("msg.success"),
                trf("msg.theme_applied", name=self.current_theme),
            )
