"""
Budget-Erfassungs-Dialog
========================
Dialog zum Erfassen und Bearbeiten von Budget-Einträgen.

Version: 2.0.41 - Mit integrierter Kategorien-Erstellung und sprachneutralen Modi
- Neue Kategorien können direkt beim Budget-Erfassen erstellt werden
- Wahlweise als Hauptkategorie oder Unterkategorie
- Kategorien-Eigenschaften (Fixkosten, Wiederkehrend) direkt setzen
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QLabel, QSpinBox, QComboBox,
    QLineEdit, QCheckBox, QPushButton, QVBoxLayout, QMessageBox,
    QGroupBox, QFrame
)

def _get_months():
    """Gibt die lokalisierten Monatskurzbezeichnungen zurück."""
    return [tr(f"month_short.{i}") for i in range(1, 13)]

from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from model.budget_modes import BUDGET_MODE_MONTH, BUDGET_MODE_ALL, BUDGET_MODE_RANGE, normalize_budget_mode
from model.category_forecast_mode import FORECAST_MODE_AUTO, FORECAST_MODE_INCREMENTAL, FORECAST_MODE_NORMAL, FORECAST_MODE_POT
from utils.money import parse_money, currency_header
from views.ui_colors import ui_colors

import logging
from utils.i18n import tr, trf, display_typ, db_typ_from_display
logger = logging.getLogger(__name__)

def parse_amount(text: str) -> float:
    return parse_money(text, empty_is_zero=False)

@dataclass(frozen=True)
class BudgetEntryRequest:
    year: int
    typ: str
    category: str
    amount: float
    mode: str              # internal: "month", "all", "range"
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
    forecast_mode: str = FORECAST_MODE_AUTO


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
        self.setWindowTitle(tr("dlg.budget_entry"))
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
        self.typ.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.typ.addItem(tr("kpi.income"), TYP_INCOME)
        self.typ.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        _idx = self.typ.findData(default_typ)
        if _idx >= 0:
            self.typ.setCurrentIndex(_idx)

        self.category = QComboBox()
        self.category.setEditable(True)
        # Autofilter/Completer deaktivieren - nur manuelle Auswahl
        self.category.setCompleter(None)
        self._set_categories(categories)

        self.amount = QLineEdit()
        self.amount.setPlaceholderText(tr('auto.views_budget_entry_dialog.102_z_b_1200_00_d7c96b70'))

        self.mode = QComboBox()
        self.mode.addItem(tr('auto.views_budget_entry_dialog.105_monat_069d7526'), BUDGET_MODE_MONTH)
        self.mode.addItem(tr('typ.Alle'), BUDGET_MODE_ALL)
        self.mode.addItem(tr('auto.views_budget_entry_dialog.105_bereich_1f8db464'), BUDGET_MODE_RANGE)

        self.month = QComboBox()
        self.month.addItems(_get_months())

        self.from_month = QComboBox()
        self.from_month.addItems(_get_months())

        self.to_month = QComboBox()
        self.to_month.addItems(_get_months())

        self.only_if_empty = QCheckBox(tr("dlg.nur_ueberschreiben_wenn_zelle"))
        self.only_if_empty.setChecked(False)

        # --- Neue Kategorie Sektion ---
        self.new_category_group = QGroupBox(tr('auto.views_budget_entry_dialog.120_neue_kategorie_erstellen_2cbb61c0'))
        self.new_category_group.setCheckable(True)
        self.new_category_group.setChecked(False)
        self.new_category_group.setVisible(False)
        
        new_cat_layout = QVBoxLayout(self.new_category_group)
        
        # Info-Label
        self.new_cat_info = QLabel()
        self.new_cat_info.setWordWrap(True)
        self.new_cat_info.setStyleSheet(f"color: {ui_colors(self).info_text}; font-style: italic;")
        new_cat_layout.addWidget(self.new_cat_info)
        
        # Mutterkategorie-Auswahl
        parent_layout = QHBoxLayout()
        parent_layout.addWidget(QLabel(tr("dlg.uebergeordnet")))
        
        self.parent_category = QComboBox()
        self.parent_category.addItem(tr("dlg.keine_hauptkategorie"), None)
        parent_layout.addWidget(self.parent_category, 1)
        new_cat_layout.addLayout(parent_layout)
        
        # Kategorie-Flags
        flags_layout = QHBoxLayout()
        self.chk_is_fix = QCheckBox(tr("tracking.title.fixcosts"))
        self.chk_is_fix.setToolTip(tr("help.tip.fixcost"))
        self.chk_is_recurring = QCheckBox(tr("lbl.recurring"))
        self.chk_is_recurring.setToolTip(tr("help.tip.recurring"))
        flags_layout.addWidget(self.chk_is_fix)
        flags_layout.addWidget(self.chk_is_recurring)
        flags_layout.addStretch()
        new_cat_layout.addLayout(flags_layout)

        forecast_layout = QHBoxLayout()
        forecast_layout.addWidget(QLabel(tr("forecast.mode.label")))
        self.forecast_mode = QComboBox()
        self.forecast_mode.addItem(tr("forecast.mode.auto"), FORECAST_MODE_AUTO)
        self.forecast_mode.addItem(tr("forecast.mode.pot"), FORECAST_MODE_POT)
        self.forecast_mode.addItem(tr("forecast.mode.incremental"), FORECAST_MODE_INCREMENTAL)
        self.forecast_mode.addItem(tr("forecast.mode.normal"), FORECAST_MODE_NORMAL)
        self.forecast_mode.setToolTip(tr("forecast.mode.tooltip"))
        forecast_layout.addWidget(self.forecast_mode, 1)
        new_cat_layout.addLayout(forecast_layout)
        
        # Fälligkeitstag
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel(tr("dlg.faelligkeitstag_1")))
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
        self.btn_ok = QPushButton(tr("dlg.uebernehmen"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        # --- Layout ---
        form = QFormLayout()
        form.addRow(tr("lbl.year"), self.year)
        form.addRow(tr("header.type"), self.typ)
        form.addRow(tr("header.category"), self.category)
        form.addRow(trf("lbl.amount_with_currency", currency=currency_header()), self.amount)
        form.addRow(tr("lbl.mode"), self.mode)
        form.addRow(tr("lbl.month"), self.month)
        form.addRow(tr("lbl.from"), self.from_month)
        form.addRow(tr("lbl.to"), self.to_month)
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
        self.mode.currentIndexChanged.connect(lambda _: self._mode_changed())
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        # Kategorie-Änderungen überwachen
        self.category.currentTextChanged.connect(self._check_category_exists)
        self.category.editTextChanged.connect(self._check_category_exists)
        
        # Typ-Änderung aktualisiert Parent-Dropdown und Kategorien-Liste
        self.typ.currentIndexChanged.connect(
            lambda _: self._on_typ_changed(self.typ.currentData() or self.typ.currentText())
        )

        self._mode_changed()

        if preset:
            self._apply_preset(preset)
        
        # Initial Parent-Kategorien laden
        self._update_parent_categories(self.typ.currentData() or self.typ.currentText())

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
        self._update_parent_categories(self.typ.currentData() or self.typ.currentText())

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
            logger.warning(trf("msg.fehler_beim_aktualisieren_der", e=str(e)))

    def _update_parent_categories(self, typ: str):
        """Aktualisiert das Parent-Kategorie-Dropdown basierend auf dem Typ."""
        self.parent_category.clear()
        self.parent_category.addItem(tr("dlg.keine_hauptkategorie"), None)
        self._parent_categories.clear()
        
        if not self.category_model:
            return
        
        try:
            # Hole alle Kategorien des ausgewählten Typs
            categories = self.category_model.list(typ)
            
            # Nur Hauptkategorien (ohne parent_id) als mögliche Parents anbieten
            for cat in categories:
                if cat.parent_id is None:
                    self.parent_category.addItem(trf('auto.views_budget_entry_dialog.290_value_0_b601d60d', value_0=(cat.name)), cat.id)
                    self._parent_categories.append((cat.id, cat.name))
                    self._category_ids[cat.name.lower()] = cat.id
                else:
                    self._category_ids[cat.name.lower()] = cat.id
                    
            # Auch existierende Kategorien-Namen aktualisieren
            self._existing_categories.clear()
            for cat in categories:
                self._existing_categories.add(cat.name.strip().lower())
                
        except Exception as e:
            logger.warning(trf("msg.fehler_beim_laden_der_1", e=str(e)))

    def _selected_category(self) -> str:
        from views.category_picker import resolve_combo_category

        return resolve_combo_category(self.category).strip()

    def _check_category_exists(self, text: str = None):
        """Prüft ob die eingegebene Kategorie existiert und zeigt ggf. die Erstellungs-Option."""
        # Bei editierbaren Combos kann currentData() veraltet sein. Für die
        # Sichtbarkeitsprüfung deshalb immer den sichtbaren/getippten Text
        # bereinigen, inklusive Baum-Pfad und Favoritenstern.
        if text is None:
            text = self._selected_category()
        else:
            from views.category_picker import _clean_category_label

            text = _clean_category_label(str(text))

        if not text:
            self.new_category_group.setVisible(False)
            return

        # Prüfe ob Kategorie bereits existiert
        exists = text.lower() in self._existing_categories

        if not exists and len(text) >= 2:
            self.new_category_group.setVisible(True)
            self.new_cat_info.setText(
                trf('auto.views_budget_entry_dialog.324_die_kategorie_value_0_existiert_noc_66c8701f', value_0=(text))
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
            self._set_mode(preset["mode"])
        if "from_month" in preset and preset["from_month"]:
            self.from_month.setCurrentIndex(int(preset["from_month"]) - 1)
        if "to_month" in preset and preset["to_month"]:
            self.to_month.setCurrentIndex(int(preset["to_month"]) - 1)
        if "only_if_empty" in preset:
            self.only_if_empty.setChecked(bool(preset["only_if_empty"]))

    def _current_mode(self) -> str:
        return normalize_budget_mode(self.mode.currentData() or self.mode.currentText())

    def _set_mode(self, value: object) -> None:
        mode = normalize_budget_mode(value)
        idx = self.mode.findData(mode)
        if idx >= 0:
            self.mode.setCurrentIndex(idx)

    def _mode_changed(self) -> None:
        mode = self._current_mode()
        is_month = mode == BUDGET_MODE_MONTH
        is_range = mode == BUDGET_MODE_RANGE
        self.month.setEnabled(is_month)
        self.from_month.setEnabled(is_range)
        self.to_month.setEnabled(is_range)

    def _validate_and_accept(self) -> None:
        cat = self._selected_category()

        if not cat:
            QMessageBox.warning(self, tr('auto.views_budget_entry_dialog.376_fehlt_e088971c'), tr("dlg.bitte_kategorie_auswaehleneingeben"))
            return
        
        try:
            amt = parse_amount(self.amount.text())
        except Exception:
            QMessageBox.warning(self, tr('dlg.hinweis'), tr("dlg.betrag_ist_ungueltig"))
            return

        # Ausgaben: negative Zahlen verhindern
        typ_data = self.typ.currentData() or self.typ.currentText()
        if typ_data == TYP_EXPENSES and amt < 0:
            QMessageBox.warning(self, tr("dlg.nicht_erlaubt"), tr("dlg.bei_ausgaben_sind_negative"))
            return
        
        # Prüfe ob Kategorie existiert oder erstellt werden soll
        cat_lower = cat.lower()
        if cat_lower not in self._existing_categories:
            if not self.new_category_group.isChecked():
                # Benutzer muss bestätigen, dass neue Kategorie erstellt werden soll
                result = QMessageBox.question(
                    self, 
                    tr('btn.new_category'),
                    trf("budget_entry.msg.category_missing_create", category=cat),
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.Yes
                )
                if result != QMessageBox.Yes:
                    return
                # Setze automatisch auf "Neue Kategorie erstellen"
                self.new_category_group.setChecked(True)

        self.accept()

    def get_request(self) -> BudgetEntryRequest:
        mode = self._current_mode()
        month = self.month.currentIndex() + 1
        fm = self.from_month.currentIndex() + 1
        tm = self.to_month.currentIndex() + 1
        amt = parse_amount(self.amount.text())
        
        cat = self._selected_category()

        cat_lower = cat.lower()
        
        # Neue Kategorie erstellen?
        create_new = self.new_category_group.isChecked() and cat_lower not in self._existing_categories
        parent_id = self.parent_category.currentData() if create_new else None
        is_fix = self.chk_is_fix.isChecked() if create_new else False
        is_recurring = self.chk_is_recurring.isChecked() if create_new else False
        recurring_day = self.spin_recurring_day.value() if create_new else 1
        forecast_mode = str(self.forecast_mode.currentData() or FORECAST_MODE_AUTO) if create_new else FORECAST_MODE_AUTO

        return BudgetEntryRequest(
            year=int(self.year.value()),
            typ=str(self.typ.currentData() or self.typ.currentText()),
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
            forecast_mode=forecast_mode,
        )
