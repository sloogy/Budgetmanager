from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog, QHBoxLayout, QVBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QColorDialog,
    QGroupBox, QFormLayout, QComboBox, QCheckBox, QFileDialog
)

from settings import Settings


def _default_profile() -> Dict[str, Any]:
    # Werte bewusst "neutral" halten: funktionieren für hell & dunkel.
    return {
        # Grundfarben
        "modus": "hell",  # hell|dunkel
        "hintergrund_app": "#ffffff",
        "hintergrund_panel": "#f6f7f9",
        "hintergrund_seitenleiste": "#f0f2f5",

        # Optional: getrennte Panel-Hintergründe (App-Feeling)
        "sidebar_panel_bg": "#eef2f7",
        "filter_panel_bg": "#f6f7f9",
        "hintergrund_sidebarpanel": "#eef2f7",
        "hintergrund_filterpanel": "#eef2f7",
        "text": "#111111",
        "text_gedimmt": "#444444",
        "akzent": "#2f80ed",

        # Tabellen
        "tabelle_hintergrund": "#ffffff",
        "tabelle_alt": "#f7f9fc",
        "tabelle_header": "#eef2f7",
        "tabelle_gitter": "#d6dbe3",
        "auswahl_hintergrund": "#2f80ed",
        "auswahl_text": "#ffffff",

        # Zahlen / Sonderfälle
        "negativ_text": "#e74c3c",

        # Typ-Farben (Tracking Spalte „Typ“)
        "typ_einnahmen": "#2ecc71",
        "typ_ausgaben": "#e74c3c",
        "typ_ersparnisse": "#3498db",

        # Schriftgrößen (optional)
        "schriftgroesse": 10,
    }


def build_stylesheet(p: Dict[str, Any]) -> str:
    # QSS: bewusst simpel & robust, damit es nicht "alles zerschiesst".
    app_bg = p["hintergrund_app"]
    panel_bg = p["hintergrund_panel"]
    side_bg = p["hintergrund_seitenleiste"]
    sidebar_panel_bg = p.get("sidebar_panel_bg", side_bg)
    filter_panel_bg = p.get("filter_panel_bg", panel_bg)
    text = p["text"]
    text_muted = p["text_gedimmt"]
    accent = p["akzent"]

    table_bg = p["tabelle_hintergrund"]
    table_alt = p["tabelle_alt"]
    table_header = p["tabelle_header"]
    grid = p["tabelle_gitter"]
    sel_bg = p["auswahl_hintergrund"]
    sel_text = p["auswahl_text"]

    font_size = int(p.get("schriftgroesse", 10))

    qss = f"""
    /* Basis */
    QWidget {{
        font-size: {font_size}pt;
        color: {text};
    }}
    QMainWindow, QDialog {{
        background-color: {app_bg};
    }}

    /* Panels / GroupBox */
    QGroupBox {{
        background-color: {panel_bg};
        border: 1px solid {grid};
        border-radius: 8px;
        margin-top: 12px;
        padding: 10px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 10px;
        padding: 0 6px;
        color: {text};
        font-weight: bold;
    }}

    /* Seitenleisten & Listen */
    QListWidget {{
        background-color: {side_bg};
        border: 1px solid {grid};
        border-radius: 10px;
        padding: 6px;
    }}
    QListWidget::item {{
        padding: 6px;
        border-radius: 6px;
    }}
    QListWidget::item:selected {{
        background-color: {sel_bg};
        color: {sel_text};
    }}

    /* Menü */
    QMenuBar {{
        background-color: {side_bg};
        color: {text};
    }}
    QMenu {{
        background-color: {side_bg};
        border: 1px solid {grid};
    }}
    QMenu::item:selected {{
        background-color: {sel_bg};
        color: {sel_text};
    }}

    /* Buttons */
    QPushButton {{
        background-color: {panel_bg};
        border: 1px solid {grid};
        padding: 6px 10px;
        border-radius: 8px;
    }}
    QPushButton:hover {{
        border: 1px solid {accent};
    }}
    QPushButton:default {{
        border: 2px solid {accent};
    }}

    /* Inputs */
    QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QDateEdit {{
        background-color: {table_bg};
        border: 1px solid {grid};
        padding: 5px 8px;
        border-radius: 8px;
        selection-background-color: {sel_bg};
        selection-color: {sel_text};
    }}

    /* Tabellen (QTableWidget basiert auf QTableView) */
    QTableView, QTableWidget {{
        background-color: {table_bg};
        alternate-background-color: {table_alt};
        gridline-color: {grid};
        selection-background-color: {sel_bg};
        selection-color: {sel_text};
        border: 1px solid {grid};
        border-radius: 10px;
    }}
    QHeaderView::section {{
        background-color: {table_header};
        border: 1px solid {grid};
        padding: 6px;
        font-weight: bold;
    }}

    /* Statusbar */
    QStatusBar {{
        background-color: {side_bg};
        border-top: 1px solid {grid};
        color: {text_muted};
    }}


    /* Optional: Panels gezielt anders färben (mehr App-Feeling)
       WICHTIG: In f-Strings müssen "{" und "}" als "{{" und "}}" geschrieben werden,
       sonst versucht Python den Inhalt als Ausdruck zu interpretieren. */
    QWidget[role="sidebar_panel"] {{
        background-color: {sidebar_panel_bg};
    }}
    QWidget[role="filter_panel"] {{
        background-color: {filter_panel_bg};
    }}
    
    /* Tooltips */
    QToolTip {{
        background-color: {side_bg};
        border: 1px solid {grid};
        color: {text};
        padding: 6px;
    }}
    """
    return qss


def _set_color_preview(lbl: QLabel, hex_color: str) -> None:
    lbl.setText(hex_color)
    lbl.setAlignment(Qt.AlignCenter)
    lbl.setStyleSheet(f"background-color: {hex_color}; border: 1px solid #00000033; border-radius: 6px; padding: 4px;")


class AppearanceProfilesDialog(QDialog):
    """
    Vollständiger UI Profilmanager für Erscheinungsprofile:
    - Profile erstellen / duplizieren / umbenennen / löschen
    - Farben für Hintergründe, Seitenleisten, Tabellen, Auswahl, Text, Negative, Typen
    - Schriftgröße
    - Anwenden (sofort) + optional automatisch anwenden
    - Import/Export (JSON)
    """
    def __init__(self, parent=None, settings: Optional[Settings] = None):
        super().__init__(parent)
        self.setWindowTitle("Erscheinungsprofile")
        self.resize(980, 620)

        self.settings = settings or Settings()
        self._profiles: Dict[str, Dict[str, Any]] = {}
        self._active_name: str = ""

        self._build_ui()
        self._load_from_settings()
        self._refresh_list()
        self._select_active_or_first()

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        root = QHBoxLayout(self)

        # Links: Profil-Liste + Aktionen
        left = QVBoxLayout()
        self.list_profiles = QListWidget()
        left.addWidget(QLabel("Profile"))
        left.addWidget(self.list_profiles, 1)

        row_actions = QHBoxLayout()
        self.btn_new = QPushButton("Neu…")
        self.btn_dup = QPushButton("Duplizieren")
        self.btn_rename = QPushButton("Umbenennen…")
        self.btn_delete = QPushButton("Löschen")
        row_actions.addWidget(self.btn_new)
        row_actions.addWidget(self.btn_dup)
        row_actions.addWidget(self.btn_rename)
        row_actions.addWidget(self.btn_delete)
        left.addLayout(row_actions)

        row_io = QHBoxLayout()
        self.btn_export = QPushButton("Export…")
        self.btn_import = QPushButton("Import…")
        self.btn_reset = QPushButton("Auf Standard zurücksetzen")
        self.btn_reset.setToolTip("Setzt ein Standard-Theme auf die Originalwerte zurück")
        row_io.addWidget(self.btn_export)
        row_io.addWidget(self.btn_import)
        row_io.addWidget(self.btn_reset)
        left.addLayout(row_io)

        self.cb_auto_apply = QCheckBox("Änderungen sofort anwenden")
        self.cb_auto_apply.setChecked(True)
        left.addWidget(self.cb_auto_apply)

        self.btn_apply = QPushButton("Profil anwenden")
        self.btn_apply.setDefault(True)
        left.addWidget(self.btn_apply)

        root.addLayout(left, 1)

        # Rechts: Editor
        right = QVBoxLayout()
        self.lbl_title = QLabel("Profil bearbeiten")
        self.lbl_title.setStyleSheet("font-weight: bold; font-size: 14pt;")
        right.addWidget(self.lbl_title)

        # Profilname
        gb_name = QGroupBox("Profil")
        fl_name = QFormLayout(gb_name)
        self.le_profile_name = QLineEdit()
        self.le_profile_name.setPlaceholderText("Profilname")
        self.cmb_mode = QComboBox()
        self.cmb_mode.addItems(["hell", "dunkel"])
        fl_name.addRow("Name", self.le_profile_name)
        fl_name.addRow("Modus", self.cmb_mode)
        right.addWidget(gb_name)

        # Farben: Allgemein
        self.gb_colors_general = QGroupBox("Allgemeine Farben")
        self.fl_general = QFormLayout(self.gb_colors_general)

        self._color_widgets: Dict[str, tuple[QLabel, QPushButton]] = {}
        for key, label in [
            ("hintergrund_app", "Hintergrund (App)"),
            ("hintergrund_panel", "Hintergrund (Panels)"),
            ("hintergrund_seitenleiste", "Hintergrund (Seitenleisten)"),
            ("hintergrund_sidebarpanel", "Hintergrund (Sidebar-Panels)"),
            ("hintergrund_filterpanel", "Hintergrund (Filter-Panels)"),
            ("text", "Schriftfarbe"),
            ("text_gedimmt", "Schriftfarbe (gedimmt)"),
            ("akzent", "Akzentfarbe (Buttons/Selektion)"),
        ]:
            self._add_color_row(self.fl_general, key, label)

        right.addWidget(self.gb_colors_general)

        # Farben: Tabellen
        self.gb_colors_table = QGroupBox("Tabellen")
        self.fl_table = QFormLayout(self.gb_colors_table)
        for key, label in [
            ("tabelle_hintergrund", "Tabelle Hintergrund"),
            ("tabelle_alt", "Tabelle Alternierend"),
            ("tabelle_header", "Header Hintergrund"),
            ("tabelle_gitter", "Gitter/Trennlinien"),
            ("auswahl_hintergrund", "Auswahl Hintergrund"),
            ("auswahl_text", "Auswahl Schrift"),
        ]:
            self._add_color_row(self.fl_table, key, label)
        right.addWidget(self.gb_colors_table)

        # Farben: Zahlen & Typen
        self.gb_colors_special = QGroupBox("Zahlen & Typen")
        self.fl_special = QFormLayout(self.gb_colors_special)
        for key, label in [
            ("negativ_text", "Negativ-Betrag Schrift"),
            ("typ_einnahmen", "Typfarbe: Einnahmen"),
            ("typ_ausgaben", "Typfarbe: Ausgaben"),
            ("typ_ersparnisse", "Typfarbe: Ersparnisse"),
        ]:
            self._add_color_row(self.fl_special, key, label)
        right.addWidget(self.gb_colors_special)

        # Schriftgröße
        gb_font = QGroupBox("Schrift")
        fl_font = QFormLayout(gb_font)
        self.cmb_font_size = QComboBox()
        self.cmb_font_size.addItems([str(x) for x in range(9, 15)])
        fl_font.addRow("Schriftgröße", self.cmb_font_size)
        right.addWidget(gb_font)

        # Spacer
        right.addStretch(1)

        root.addLayout(right, 2)

        # Signals
        self.list_profiles.currentItemChanged.connect(self._on_profile_selected)
        self.btn_new.clicked.connect(self._new_profile)
        self.btn_dup.clicked.connect(self._duplicate_profile)
        self.btn_rename.clicked.connect(self._rename_profile)
        self.btn_delete.clicked.connect(self._delete_profile)
        self.btn_apply.clicked.connect(self._apply_profile)
        self.btn_export.clicked.connect(self._export_profile)
        self.btn_import.clicked.connect(self._import_profile)
        self.btn_reset.clicked.connect(self._reset_to_default)

        self.le_profile_name.textEdited.connect(self._on_editor_changed)
        self.cmb_mode.currentTextChanged.connect(self._on_editor_changed)
        self.cmb_font_size.currentTextChanged.connect(self._on_editor_changed)

    def _add_color_row(self, form: QFormLayout, key: str, title: str) -> None:
        row = QHBoxLayout()
        preview = QLabel()
        preview.setMinimumWidth(140)
        btn = QPushButton("Ändern…")
        row.addWidget(preview, 1)
        row.addWidget(btn)
        form.addRow(title, row)

        self._color_widgets[key] = (preview, btn)
        btn.clicked.connect(lambda: self._pick_color(key))

    # ---------------- Data ----------------
    def _load_from_settings(self) -> None:
        self._profiles = self.settings.get("appearance_profiles", {})
        if not isinstance(self._profiles, dict):
            self._profiles = {}

        # Migration: falls keine Profile existieren, Defaults erstellen
        if not self._profiles:
            # 6 Presets: 3 Hell, 3 Dunkel (modern, kontrastreich, freundlich)
            def make(base: dict, **kw):
                p = dict(base)
                p.update(kw)
                return p

            base_hell = _default_profile()
            base_dunkel = make(_default_profile(),
                               modus="dunkel",
                               hintergrund_app="#1f2329",
                               hintergrund_panel="#2b3038",
                               hintergrund_seitenleiste="#1f2329",
                               text="#e6e6e6",
                               text_gedimmt="#b9bec6",
                               tabelle_hintergrund="#1f2329",
                               tabelle_alt="#232833",
                               tabelle_header="#2b3038",
                               tabelle_gitter="#3a3f46",
                               auswahl_hintergrund="#2f80ed",
                               auswahl_text="#ffffff",
                               sidebar_panel_bg="#1b1f26",
                               filter_panel_bg="#2b3038")

            # Hell 1: Klar (Blue)
            self._profiles["Hell – Klar (Blau)"] = make(base_hell,
                akzent="#2f80ed",
                hintergrund_app="#ffffff",
                hintergrund_panel="#f6f7f9",
                hintergrund_seitenleiste="#f0f2f5",
                text="#111111",
                text_gedimmt="#444444",
                tabelle_hintergrund="#ffffff",
                tabelle_alt="#f7f9fc",
                tabelle_header="#eef2f7",
                tabelle_gitter="#d6dbe3",
                auswahl_hintergrund="#2f80ed",
                auswahl_text="#ffffff",
                sidebar_panel_bg="#eef2f7",
                filter_panel_bg="#f6f7f9",
                typ_einnahmen="#2ecc71",
                typ_ausgaben="#e74c3c",
                typ_ersparnisse="#3498db",
            )

            # Hell 2: Warm (Amber)
            self._profiles["Hell – Warm (Amber)"] = make(base_hell,
                akzent="#f2994a",
                hintergrund_app="#fffdf8",
                hintergrund_panel="#fbf4ea",
                hintergrund_seitenleiste="#f7efe2",
                text="#2b2b2b",
                text_gedimmt="#5a5a5a",
                tabelle_hintergrund="#fffdf8",
                tabelle_alt="#fbf4ea",
                tabelle_header="#f4e7d6",
                tabelle_gitter="#e3d2bd",
                auswahl_hintergrund="#f2994a",
                auswahl_text="#1b1b1b",
                sidebar_panel_bg="#f4e7d6",
                filter_panel_bg="#fbf4ea",
                typ_einnahmen="#27ae60",
                typ_ausgaben="#c0392b",
                typ_ersparnisse="#2980b9",
            )

            # Hell 3: Fresh (Mint)
            self._profiles["Hell – Fresh (Mint)"] = make(base_hell,
                akzent="#27ae60",
                hintergrund_app="#fbfffd",
                hintergrund_panel="#eefaf3",
                hintergrund_seitenleiste="#e3f5ea",
                text="#143024",
                text_gedimmt="#2f4f40",
                tabelle_hintergrund="#fbfffd",
                tabelle_alt="#eefaf3",
                tabelle_header="#dff3e8",
                tabelle_gitter="#c7e6d4",
                auswahl_hintergrund="#27ae60",
                auswahl_text="#ffffff",
                sidebar_panel_bg="#dff3e8",
                filter_panel_bg="#eefaf3",
                typ_einnahmen="#2ecc71",
                typ_ausgaben="#e74c3c",
                typ_ersparnisse="#3498db",
            )

            # Dunkel 1: Graphit (Blue)
            self._profiles["Dunkel – Graphit (Blau)"] = make(base_dunkel,
                akzent="#2f80ed",
                hintergrund_app="#1f2329",
                hintergrund_panel="#2b3038",
                hintergrund_seitenleiste="#1b1f26",
                text="#e6e6e6",
                text_gedimmt="#b9bec6",
                tabelle_hintergrund="#1f2329",
                tabelle_alt="#232833",
                tabelle_header="#2b3038",
                tabelle_gitter="#3a3f46",
                auswahl_hintergrund="#2f80ed",
                auswahl_text="#ffffff",
                sidebar_panel_bg="#1b1f26",
                filter_panel_bg="#2b3038",
                typ_einnahmen="#2ecc71",
                typ_ausgaben="#e74c3c",
                typ_ersparnisse="#3498db",
            )

            # Dunkel 2: Nacht (Violett)
            self._profiles["Dunkel – Nacht (Violett)"] = make(base_dunkel,
                akzent="#9b51e0",
                hintergrund_app="#14151a",
                hintergrund_panel="#1f2028",
                hintergrund_seitenleiste="#111218",
                text="#f2f2f2",
                text_gedimmt="#c7c7d1",
                tabelle_hintergrund="#14151a",
                tabelle_alt="#191a22",
                tabelle_header="#1f2028",
                tabelle_gitter="#343544",
                auswahl_hintergrund="#9b51e0",
                auswahl_text="#ffffff",
                sidebar_panel_bg="#111218",
                filter_panel_bg="#1f2028",
                typ_einnahmen="#6fcf97",
                typ_ausgaben="#eb5757",
                typ_ersparnisse="#56ccf2",
            )

            # Dunkel 3: Ozean (Cyan)
            self._profiles["Dunkel – Ozean (Cyan)"] = make(base_dunkel,
                akzent="#56ccf2",
                hintergrund_app="#0f1720",
                hintergrund_panel="#16202c",
                hintergrund_seitenleiste="#0b1118",
                text="#eaf2f7",
                text_gedimmt="#b6c6d1",
                tabelle_hintergrund="#0f1720",
                tabelle_alt="#121c27",
                tabelle_header="#16202c",
                tabelle_gitter="#2b3a47",
                auswahl_hintergrund="#56ccf2",
                auswahl_text="#0b1118",
                sidebar_panel_bg="#0b1118",
                filter_panel_bg="#16202c",
                typ_einnahmen="#2ecc71",
                typ_ausgaben="#ff6b6b",
                typ_ersparnisse="#56ccf2",
            )

            self._active_name = "Hell – Klar (Blau)"
        self._active_name = self.settings.get("appearance_profile_active", "Hell – Klar (Blau)")
        if self._active_name not in self._profiles:
            self._active_name = next(iter(self._profiles.keys()))

    def _save_to_settings(self) -> None:
        self.settings.set("appearance_profiles", self._profiles)
        self.settings.set("appearance_profile_active", self._active_name)

    # ---------------- List/UI sync ----------------
    def _refresh_list(self) -> None:
        self.list_profiles.clear()
        for name in sorted(self._profiles.keys(), key=str.lower):
            it = QListWidgetItem(name)
            if name == self._active_name:
                it.setText(f"✅ {name}")
                it.setData(Qt.UserRole, name)
            else:
                it.setData(Qt.UserRole, name)
            self.list_profiles.addItem(it)

    def _select_active_or_first(self) -> None:
        # Select active row
        target = self._active_name
        for i in range(self.list_profiles.count()):
            name = self.list_profiles.item(i).data(Qt.UserRole)
            if name == target:
                self.list_profiles.setCurrentRow(i)
                return
        if self.list_profiles.count() > 0:
            self.list_profiles.setCurrentRow(0)

    def _current_name(self) -> Optional[str]:
        it = self.list_profiles.currentItem()
        if not it:
            return None
        return it.data(Qt.UserRole)

    def _on_profile_selected(self, cur: QListWidgetItem, prev: QListWidgetItem) -> None:
        name = self._current_name()
        if not name:
            return
        self._load_profile_to_editor(name)

    def _load_profile_to_editor(self, name: str) -> None:
        p = self._profiles.get(name, _default_profile())
        self.le_profile_name.setText(name)
        self.cmb_mode.setCurrentText(p.get("modus", "hell"))
        self.cmb_font_size.setCurrentText(str(int(p.get("schriftgroesse", 10))))

        for key, (preview, _) in self._color_widgets.items():
            val = p.get(key, _default_profile().get(key))
            _set_color_preview(preview, val)

        # Prüfe ob es ein Standard-Theme ist
        from theme_manager import ThemeManager
        is_predefined = name in ['Standard Hell', 'Standard Dunkel', 'Solarized Hell', 'Solarized Dunkel', 'Nord Dunkel', 'Dracula Dunkel']
        
        if is_predefined:
            self.lbl_title.setText(f"Profil bearbeiten: {name} (Standard-Theme - Änderungen werden gespeichert)")
            self.le_profile_name.setEnabled(False)  # Name nicht änderbar für Standard-Themes
        else:
            self.lbl_title.setText(f"Profil bearbeiten: {name}")
            self.le_profile_name.setEnabled(True)

    def _read_editor_to_profile(self) -> Dict[str, Any]:
        name = self._current_name()
        if not name:
            return _default_profile()
        p = dict(self._profiles.get(name, _default_profile()))
        p["modus"] = self.cmb_mode.currentText()
        p["schriftgroesse"] = int(self.cmb_font_size.currentText())
        # Farben aus Preview-Text
        for key, (preview, _) in self._color_widgets.items():
            p[key] = preview.text().strip()
        return p

    def _on_editor_changed(self) -> None:
        name = self._current_name()
        if not name:
            return
        
        # Prüfe ob Standard-Theme
        from theme_manager import ThemeManager
        is_predefined = name in ['Standard Hell', 'Standard Dunkel', 'Solarized Hell', 'Solarized Dunkel', 'Nord Dunkel', 'Dracula Dunkel']
        
        # Profil speichern (auch für Standard-Themes erlaubt - wird in JSON gespeichert)
        self._profiles[name] = self._read_editor_to_profile()
        self._save_to_settings()
        
        if self.cb_auto_apply.isChecked():
            self._active_name = name
            self._apply_profile()

    # ---------------- Actions ----------------
    def _new_profile(self) -> None:
        new_name, ok = self._ask_name("Neues Profil", "Name des neuen Profils:")
        if not ok or not new_name:
            return
        if new_name in self._profiles:
            QMessageBox.warning(self, "Hinweis", "Ein Profil mit diesem Namen existiert bereits.")
            return
        self._profiles[new_name] = _default_profile()
        self._active_name = new_name
        self._save_to_settings()
        self._refresh_list()
        self._select_active_or_first()

    def _duplicate_profile(self) -> None:
        name = self._current_name()
        if not name:
            return
        new_name, ok = self._ask_name("Duplizieren", "Neuer Name für das Duplikat:", preset=f"{name} (Kopie)")
        if not ok or not new_name:
            return
        if new_name in self._profiles:
            QMessageBox.warning(self, "Hinweis", "Ein Profil mit diesem Namen existiert bereits.")
            return
        self._profiles[new_name] = dict(self._profiles[name])
        self._active_name = new_name
        self._save_to_settings()
        self._refresh_list()
        self._select_active_or_first()

    def _rename_profile(self) -> None:
        name = self._current_name()
        if not name:
            return
        new_name, ok = self._ask_name("Umbenennen", "Neuer Name:", preset=name)
        if not ok or not new_name or new_name == name:
            return
        if new_name in self._profiles:
            QMessageBox.warning(self, "Hinweis", "Ein Profil mit diesem Namen existiert bereits.")
            return
        self._profiles[new_name] = self._profiles.pop(name)
        if self._active_name == name:
            self._active_name = new_name
        self._save_to_settings()
        self._refresh_list()
        # select renamed
        for i in range(self.list_profiles.count()):
            if self.list_profiles.item(i).data(Qt.UserRole) == new_name:
                self.list_profiles.setCurrentRow(i)
                break

    def _delete_profile(self) -> None:
        name = self._current_name()
        if not name:
            return
        if len(self._profiles) <= 1:
            QMessageBox.information(self, "Hinweis", "Mindestens ein Profil muss vorhanden sein.")
            return
        reply = QMessageBox.question(self, "Löschen", f"Profil „{name}“ wirklich löschen?",
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return
        self._profiles.pop(name, None)
        if self._active_name == name:
            self._active_name = next(iter(self._profiles.keys()))
        self._save_to_settings()
        self._refresh_list()
        self._select_active_or_first()

    def _apply_profile(self) -> None:
        name = self._current_name() or self._active_name
        if not name:
            return
        self._profiles[name] = self._read_editor_to_profile()
        self._active_name = name
        self._save_to_settings()

        # QSS anwenden
        qss = build_stylesheet(self._profiles[name])
        app = self.parent().window().windowHandle() if self.parent() else None  # unused, keep simple
        from PySide6.QtWidgets import QApplication
        QApplication.instance().setStyleSheet(qss)

        # Damit Tabellen (Tracking) neu einfärben können, legen wir Farben global ab
        self.settings.set("type_colors", {
            "Einkommen": self._profiles[name]["typ_einnahmen"],
            "Einnahmen": self._profiles[name]["typ_einnahmen"],  # Alias (Legacy)
            "Income": self._profiles[name]["typ_einnahmen"],     # optional
            "Ausgaben": self._profiles[name]["typ_ausgaben"],
            "Expenses": self._profiles[name]["typ_ausgaben"],    # optional
            "Ersparnisse": self._profiles[name]["typ_ersparnisse"],
            "Savings": self._profiles[name]["typ_ersparnisse"],  # optional
        })
        self.settings.set("negative_color", self._profiles[name]["negativ_text"])

        QMessageBox.information(self, "Angewendet", f"Profil „{name}“ wurde angewendet.")

    def _export_profile(self) -> None:
        name = self._current_name()
        if not name:
            return
        file, _ = QFileDialog.getSaveFileName(self, "Profil exportieren", f"{name}.json", "JSON (*.json)")
        if not file:
            return
        data = {"name": name, "profile": self._profiles[name]}
        with open(file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        QMessageBox.information(self, "Export", "Profil wurde exportiert.")

    def _import_profile(self) -> None:
        file, _ = QFileDialog.getOpenFileName(self, "Profil importieren", "", "JSON (*.json)")
        if not file:
            return
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name") or "Importiertes Profil"
            prof = data.get("profile") or {}
            # merge with defaults
            d = _default_profile()
            d.update(prof)
            base = name
            i = 1
            while name in self._profiles:
                i += 1
                name = f"{base} ({i})"
            self._profiles[name] = d
            self._active_name = name
            self._save_to_settings()
            self._refresh_list()
            self._select_active_or_first()
            QMessageBox.information(self, "Import", f"Profil „{name}“ wurde importiert.")
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Import fehlgeschlagen:\n{e}")

    def _reset_to_default(self) -> None:
        """Setzt ein Standard-Theme auf die Originalwerte zurück"""
        name = self._current_name()
        if not name:
            return
        
        # Prüfe ob es ein Standard-Theme ist
        from theme_manager import ThemeManager
        is_predefined = name in ['Standard Hell', 'Standard Dunkel', 'Solarized Hell', 'Solarized Dunkel', 'Nord Dunkel', 'Dracula Dunkel']
        
        if not is_predefined:
            QMessageBox.information(
                self, "Hinweis",
                f"'{name}' ist kein Standard-Theme.\n\n"
                "Diese Funktion ist nur für Standard-Themes verfügbar."
            )
            return
        
        # Bestätigung
        reply = QMessageBox.question(
            self, "Auf Standard zurücksetzen?",
            f"Möchten Sie das Theme '{name}' wirklich auf die Standardwerte zurücksetzen?\n\n"
            "Alle Ihre Änderungen an diesem Theme gehen verloren!",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        
        if reply != QMessageBox.Yes:
            return
        
        # Originale Werte aus PREDEFINED_PROFILES holen
        original = self.theme_manager.get_profile(name).to_dict() if self.theme_manager.get_profile(name) else {}
        if not original:
            QMessageBox.warning(self, "Fehler", f"Konnte Original-Daten für '{name}' nicht finden.")
            return
        
        # Profil zurücksetzen
        self._profiles[name] = dict(original)
        self._save_to_settings()
        
        # Editor aktualisieren
        self._load_profile_to_editor(name)
        
        QMessageBox.information(
            self, "Zurückgesetzt",
            f"Theme '{name}' wurde auf die Standardwerte zurückgesetzt."
        )

    # ---------------- Helpers ----------------
    def _pick_color(self, key: str) -> None:
        name = self._current_name()
        if not name:
            return
        current_hex = self._color_widgets[key][0].text().strip() or _default_profile()[key]
        col = QColorDialog.getColor(QColor(current_hex), self, "Farbe auswählen")
        if not col.isValid():
            return
        hex_color = col.name()
        preview, _ = self._color_widgets[key]
        _set_color_preview(preview, hex_color)
        self._on_editor_changed()

    def _ask_name(self, title: str, label: str, preset: str = "") -> tuple[str, bool]:
        dlg = QDialog(self)
        dlg.setWindowTitle(title)
        lay = QVBoxLayout(dlg)
        lay.addWidget(QLabel(label))
        le = QLineEdit()
        le.setText(preset)
        lay.addWidget(le)
        row = QHBoxLayout()
        ok = QPushButton("OK")
        cancel = QPushButton("Abbrechen")
        row.addStretch(1)
        row.addWidget(ok)
        row.addWidget(cancel)
        lay.addLayout(row)

        ret = {"ok": False}
        ok.clicked.connect(lambda: (ret.update({"ok": True}), dlg.accept()))
        cancel.clicked.connect(dlg.reject)

        if dlg.exec() == QDialog.Accepted and ret["ok"]:
            return le.text().strip(), True
        return "", False
