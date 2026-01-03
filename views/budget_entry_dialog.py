"""
Budget-Erfassungs-Dialog
========================
Dialog zum Erfassen und Bearbeiten von Budget-Einträgen.

Version: 2.2.0 - Mit integrierter Kategorien-Erstellung
- Neue Kategorien können direkt beim Budget-Erfassen erstellt werden
- Wahlweise als Hauptkategorie oder Unterkategorie
- Kategorien-Eigenschaften (Fixkosten, Wiederkehrend) direkt setzen
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QMessageBox,
    QGroupBox, QFrame
)
from PySide6.QtGui import QColor

MONTHS = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

def parse_amount(text: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    s = s.replace("CHF","").strip()
    s = s.replace("'", "").replace(" ", "").replace(",", ".")
    return float(s)

@dataclass(frozen=True)
class BudgetEntryRequest:
    year: int
    typ: str
    category: str
    amount: float
    mode: str              # "Monat", "Alle", "Bereich"
    month: int             # 1..12 (für Mode Monat)
    from_month: int        # 1..12 (für Bereich)
    to_month: int          # 1..12 (für Bereich)
    only_if_empty: bool
    # Neue Felder für Kategorie-Erstellung
    create_new_category: bool = False
    parent_category_id: Optional[int] = None
    is_fix: bool = False
    is_recurring: bool = False
    recurring_day: int = 1


class BudgetEntryDialog(QDialog):
    """
    Dialog zum Erfassen/Bearbeiten von Budget-Einträgen.
    
    Neu in v2.2: Integrierte Kategorien-Erstellung
    - Wenn eine nicht existierende Kategorie eingegeben wird, kann diese direkt erstellt werden
    - Wahlweise als Hauptkategorie oder als Unterkategorie einer bestehenden Kategorie
    """
    
    # Signal für neue Kategorien (typ, name, parent_id, is_fix, is_recurring, day)
    category_created = Signal(str, str, object, bool, bool, int)
    
    def __init__(self, parent=None, *, default_year: int, default_typ: str, categories, 
                 preset: Optional[dict]=None, category_model=None):
        super().__init__(parent)
        self.setWindowTitle("Budget erfassen / bearbeiten")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        # Speichere Kategorie-Model für Validierung
        self.category_model = category_model
        self._existing_categories = set()
        self._parent_categories = []  # Liste von (id, name) Tupeln
        self._category_ids = {}  # name -> id Mapping
        
        # --- Basis-Eingabefelder ---
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(default_year)

        self.typ = QComboBox()
        self.typ.addItems(["Ausgaben","Einkommen","Ersparnisse"])
        self.typ.setCurrentText(default_typ)

        self.category = QComboBox()
        self.category.setEditable(True)
        self._set_categories(categories)

        self.amount = QLineEdit()
        self.amount.setPlaceholderText("z.B. 1200.00")

        self.mode = QComboBox()
        self.mode.addItems(["Monat", "Alle", "Bereich"])

        self.month = QComboBox()
        self.month.addItems(MONTHS)

        self.from_month = QComboBox()
        self.from_month.addItems(MONTHS)

        self.to_month = QComboBox()
        self.to_month.addItems(MONTHS)

        self.only_if_empty = QCheckBox("Nur überschreiben, wenn Zelle leer ist")
        self.only_if_empty.setChecked(False)

        # --- Neue Kategorie Sektion ---
        self.new_category_group = QGroupBox("📁 Neue Kategorie erstellen")
        self.new_category_group.setCheckable(True)
        self.new_category_group.setChecked(False)
        self.new_category_group.setVisible(False)
        
        new_cat_layout = QVBoxLayout(self.new_category_group)
        
        # Info-Label
        self.new_cat_info = QLabel()
        self.new_cat_info.setWordWrap(True)
        self.new_cat_info.setStyleSheet("color: #2196F3; font-style: italic;")
        new_cat_layout.addWidget(self.new_cat_info)
        
        # Mutterkategorie-Auswahl
        parent_layout = QHBoxLayout()
        parent_layout.addWidget(QLabel("Übergeordnet:"))
        
        self.parent_category = QComboBox()
        self.parent_category.addItem("— Keine (Hauptkategorie) —", None)
        parent_layout.addWidget(self.parent_category, 1)
        new_cat_layout.addLayout(parent_layout)
        
        # Kategorie-Flags
        flags_layout = QHBoxLayout()
        self.chk_is_fix = QCheckBox("Fixkosten")
        self.chk_is_fix.setToolTip("Diese Kategorie ist eine monatlich feste Ausgabe")
        self.chk_is_recurring = QCheckBox("Wiederkehrend")
        self.chk_is_recurring.setToolTip("Diese Kategorie ist eine regelmäßig wiederkehrende Buchung")
        flags_layout.addWidget(self.chk_is_fix)
        flags_layout.addWidget(self.chk_is_recurring)
        flags_layout.addStretch()
        new_cat_layout.addLayout(flags_layout)
        
        # Fälligkeitstag
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("Fälligkeitstag:"))
        self.spin_recurring_day = QSpinBox()
        self.spin_recurring_day.setRange(1, 31)
        self.spin_recurring_day.setValue(1)
        self.spin_recurring_day.setEnabled(False)
        day_layout.addWidget(self.spin_recurring_day)
        day_layout.addStretch()
        new_cat_layout.addLayout(day_layout)
        
        # Verbindung: Fälligkeitstag nur aktiv wenn "Wiederkehrend"
        self.chk_is_recurring.toggled.connect(self.spin_recurring_day.setEnabled)

        # --- Buttons ---
        self.btn_ok = QPushButton("Übernehmen")
        self.btn_cancel = QPushButton("Abbrechen")

        # --- Layout ---
        form = QFormLayout()
        form.addRow("Jahr", self.year)
        form.addRow("Typ", self.typ)
        form.addRow("Kategorie", self.category)
        form.addRow("Betrag (CHF)", self.amount)
        form.addRow("Modus", self.mode)
        form.addRow("Monat", self.month)
        form.addRow("Von", self.from_month)
        form.addRow("Bis", self.to_month)
        form.addRow("", self.only_if_empty)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addWidget(self.new_category_group)
        root.addLayout(btns)
        self.setLayout(root)

        # --- Signal-Verbindungen ---
        self.mode.currentTextChanged.connect(self._mode_changed)
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Kategorie-Änderungen überwachen
        self.category.currentTextChanged.connect(self._check_category_exists)
        self.category.editTextChanged.connect(self._check_category_exists)
        
        # Typ-Änderung aktualisiert Parent-Dropdown und Kategorien-Liste
        self.typ.currentTextChanged.connect(self._on_typ_changed)

        self._mode_changed(self.mode.currentText())

        if preset:
            self._apply_preset(preset)
        
        # Initial Parent-Kategorien laden
        self._update_parent_categories(self.typ.currentText())

    def _set_categories(self, cats) -> None:
        """Füllt die Kategorie-Combo und speichert existierende Namen."""
        self.category.clear()
        self._existing_categories.clear()
        self._category_ids.clear()
        
        if not cats:
            return
            
        # Tree-Paare
        if isinstance(cats[0], (tuple, list)) and len(cats[0]) == 2:
            for label, real in cats:
                self.category.addItem(str(label), str(real))
                self._existing_categories.add(str(real).strip().lower())
        else:
            for x in cats:
                self.category.addItem(str(x))
                self._existing_categories.add(str(x).strip().lower())

    def set_category_model(self, model):
        """Setzt das Kategorie-Model für dynamische Validierung."""
        self.category_model = model
        self._update_parent_categories(self.typ.currentText())

    def _on_typ_changed(self, typ: str):
        """Wird aufgerufen wenn der Typ geändert wird."""
        self._update_parent_categories(typ)
        self._update_categories_for_typ(typ)
        # Prüfe erneut ob aktuelle Kategorie existiert
        self._check_category_exists()

    def _update_categories_for_typ(self, typ: str):
        """Aktualisiert die Kategorien-ComboBox für den neuen Typ."""
        if not self.category_model:
            return
            
        try:
            # Speichere aktuellen Text
            current_text = self.category.currentText()
            
            # Hole Kategorien für den Typ
            cats = self.category_model.list_names_tree(typ) if hasattr(self.category_model, 'list_names_tree') else []
            if not cats:
                cats = self.category_model.list_names(typ) if hasattr(self.category_model, 'list_names') else []
            
            self._set_categories(cats)
            
            # Versuche den vorherigen Text wiederherzustellen
            if current_text:
                idx = self.category.findText(current_text)
                if idx >= 0:
                    self.category.setCurrentIndex(idx)
                else:
                    self.category.setEditText(current_text)
                    
        except Exception as e:
            print(f"Fehler beim Aktualisieren der Kategorien: {e}")

    def _update_parent_categories(self, typ: str):
        """Aktualisiert das Parent-Kategorie-Dropdown basierend auf dem Typ."""
        self.parent_category.clear()
        self.parent_category.addItem("— Keine (Hauptkategorie) —", None)
        self._parent_categories.clear()
        
        if not self.category_model:
            return
        
        try:
            # Hole alle Kategorien des ausgewählten Typs
            categories = self.category_model.list(typ)
            
            # Nur Hauptkategorien (ohne parent_id) als mögliche Parents anbieten
            for cat in categories:
                if cat.parent_id is None:
                    self.parent_category.addItem(f"  ↳ {cat.name}", cat.id)
                    self._parent_categories.append((cat.id, cat.name))
                    self._category_ids[cat.name.lower()] = cat.id
                else:
                    self._category_ids[cat.name.lower()] = cat.id
                    
            # Auch existierende Kategorien-Namen aktualisieren
            self._existing_categories.clear()
            for cat in categories:
                self._existing_categories.add(cat.name.strip().lower())
                
        except Exception as e:
            print(f"Fehler beim Laden der Parent-Kategorien: {e}")

    def _check_category_exists(self, text: str = None):
        """Prüft ob die eingegebene Kategorie existiert und zeigt ggf. die Erstellungs-Option."""
        if text is None:
            text = self.category.currentText()
        
        # Entferne Einrückungen von Tree-Darstellung
        text = text.strip()
        while text.startswith("  "):
            text = text[2:]
        
        if not text:
            self.new_category_group.setVisible(False)
            return
        
        # Prüfe ob Kategorie bereits existiert
        exists = text.lower() in self._existing_categories
        
        if not exists and len(text) >= 2:
            self.new_category_group.setVisible(True)
            self.new_cat_info.setText(
                f"💡 Die Kategorie \"{text}\" existiert noch nicht.\n"
                f"Aktiviere diese Option, um sie direkt zu erstellen."
            )
        else:
            self.new_category_group.setVisible(False)
            self.new_category_group.setChecked(False)

    def _set_combo_by_data(self, combo: QComboBox, value: str) -> None:
        if not value:
            return
        value = str(value)
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return
        # fallback
        for i in range(combo.count()):
            if combo.itemText(i).strip() == value:
                combo.setCurrentIndex(i)
                return

    def _apply_preset(self, preset: dict) -> None:
        if "category" in preset and preset["category"]:
            self._set_combo_by_data(self.category, str(preset["category"]))
        if "amount" in preset and preset["amount"] is not None:
            self.amount.setText(str(preset["amount"]))
        if "month" in preset and preset["month"]:
            self.month.setCurrentIndex(int(preset["month"]) - 1)
        if "mode" in preset and preset["mode"]:
            self.mode.setCurrentText(str(preset["mode"]))
        if "from_month" in preset and preset["from_month"]:
            self.from_month.setCurrentIndex(int(preset["from_month"]) - 1)
        if "to_month" in preset and preset["to_month"]:
            self.to_month.setCurrentIndex(int(preset["to_month"]) - 1)
        if "only_if_empty" in preset:
            self.only_if_empty.setChecked(bool(preset["only_if_empty"]))

    def _mode_changed(self, mode: str) -> None:
        is_month = mode == "Monat"
        is_range = mode == "Bereich"
        self.month.setEnabled(is_month)
        self.from_month.setEnabled(is_range)
        self.to_month.setEnabled(is_range)

    def _validate_and_accept(self) -> None:
        cat = (self.category.currentData() or self.category.currentText() or "").strip()
        
        # Entferne Einrückungen von Tree-Darstellung
        while cat.startswith("  "):
            cat = cat[2:]
        
        if not cat:
            QMessageBox.warning(self, "Fehlt", "Bitte Kategorie auswählen/eingeben.")
            return
        
        try:
            amt = parse_amount(self.amount.text())
        except Exception:
            QMessageBox.warning(self, "Fehler", "Betrag ist ungültig.")
            return

        # Ausgaben: negative Zahlen verhindern
        if self.typ.currentText() == "Ausgaben" and amt < 0:
            QMessageBox.warning(self, "Nicht erlaubt", "Bei Ausgaben sind negative Beträge nicht erlaubt.")
            return
        
        # Prüfe ob Kategorie existiert oder erstellt werden soll
        cat_lower = cat.lower()
        if cat_lower not in self._existing_categories:
            if not self.new_category_group.isChecked():
                # Benutzer muss bestätigen, dass neue Kategorie erstellt werden soll
                result = QMessageBox.question(
                    self, 
                    "Neue Kategorie",
                    f"Die Kategorie \"{cat}\" existiert noch nicht.\n\n"
                    f"Möchtest du sie jetzt erstellen?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if result != QMessageBox.Yes:
                    return
                # Setze automatisch auf "Neue Kategorie erstellen"
                self.new_category_group.setChecked(True)

        self.accept()

    def get_request(self) -> BudgetEntryRequest:
        mode = self.mode.currentText()
        month = self.month.currentIndex() + 1
        fm = self.from_month.currentIndex() + 1
        tm = self.to_month.currentIndex() + 1
        amt = parse_amount(self.amount.text())
        
        cat = (self.category.currentData() or self.category.currentText() or "").strip()
        
        # Entferne Einrückungen von Tree-Darstellung
        while cat.startswith("  "):
            cat = cat[2:]
        
        cat_lower = cat.lower()
        
        # Neue Kategorie erstellen?
        create_new = self.new_category_group.isChecked() and cat_lower not in self._existing_categories
        parent_id = self.parent_category.currentData() if create_new else None
        is_fix = self.chk_is_fix.isChecked() if create_new else False
        is_recurring = self.chk_is_recurring.isChecked() if create_new else False
        recurring_day = self.spin_recurring_day.value() if create_new else 1

        return BudgetEntryRequest(
            year=int(self.year.value()),
            typ=str(self.typ.currentText()),
            category=str(cat),
            amount=float(amt),
            mode=str(mode),
            month=int(month),
            from_month=int(fm),
            to_month=int(tm),
            only_if_empty=bool(self.only_if_empty.isChecked()),
            create_new_category=bool(create_new),
            parent_category_id=parent_id,
            is_fix=bool(is_fix),
            is_recurring=bool(is_recurring),
            recurring_day=int(recurring_day),
        )
