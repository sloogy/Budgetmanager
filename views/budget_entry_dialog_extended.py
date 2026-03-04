"""
Budget-Entry-Dialog mit integrierter Kategorie-Verwaltung.

Funktionen:
- Neue Kategorien direkt erstellen (als Hauptkategorie oder Unterkategorie)
- Parent-Kategorie per Dropdown wählbar
- Kategorie-Flags (Fixkosten, Wiederkehrend, Tag) direkt setzen
- Kategorien umbenennen und löschen
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QSpinBox, QComboBox, QLineEdit, QCheckBox, QPushButton,
    QMessageBox, QGroupBox, QWidget, QToolButton, QMenu, QInputDialog,
    QDialogButtonBox, QFrame
)

from model.category_model import CategoryModel, Category
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from utils.icons import get_icon

def _get_months():
    """Gibt die lokalisierten Monatskurzbezeichnungen zurück."""
    return [tr(f"month_short.{i}") for i in range(1, 13)]

from utils.money import parse_money, currency_header
from utils.i18n import tr, trf, display_typ, db_typ_from_display

def parse_amount(text: str) -> float:
    return parse_money(text)


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
    # NEU: Kategorie-Erstellungsdaten
    category_created: bool = False
    parent_category_id: int | None = None


class NewCategoryDialog(QDialog):
    """Dialog zum Erstellen einer neuen Kategorie."""
    
    def __init__(self, parent=None, *, typ: str, category_name: str, 
                 cat_model: CategoryModel, existing_categories: list[Category]):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.category_create"))
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self.cat_model = cat_model
        self.typ = typ
        self.existing_categories = existing_categories
        self._created_id: int | None = None
        
        # === Haupt-Layout ===
        layout = QVBoxLayout(self)
        
        # Info-Label
        info = QLabel(trf("msg.kategorie_existiert_nicht_html", category_name=category_name))
        info.setWordWrap(True)
        layout.addWidget(info)
        
        # === Kategorie-Details ===
        group = QGroupBox("Kategorie-Details")
        form = QFormLayout(group)
        
        # Name
        self.name_edit = QLineEdit(category_name)
        form.addRow("Name:", self.name_edit)
        
        # Typ (read-only anzeigen)
        typ_label = QLabel(f"<b>{typ}</b>")
        form.addRow("Typ:", typ_label)
        
        # Parent-Kategorie
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("— Hauptkategorie (kein Parent) —", None)
        
        # Nur Kategorien des gleichen Typs als mögliche Parents
        for cat in existing_categories:
            indent = ""
            # Hierarchie-Einrückung berechnen
            if cat.parent_id:
                indent = "  "
            self.parent_combo.addItem(f"{indent}{cat.name}", cat.id)
        
        form.addRow("Parent-Kategorie:", self.parent_combo)
        
        layout.addWidget(group)
        
        # === Flags ===
        flags_group = QGroupBox("Eigenschaften")
        flags_layout = QGridLayout(flags_group)
        
        self.chk_fix = QCheckBox(tr("tracking.title.fixcosts"))
        self.chk_fix.setToolTip(tr("dlg.diese_kategorie_enthaelt_feste"))
        flags_layout.addWidget(self.chk_fix, 0, 0)
        
        self.chk_recurring = QCheckBox(tr("lbl.recurring"))
        self.chk_recurring.setToolTip(tr("dlg.diese_kategorie_hat_regelmaessige"))
        flags_layout.addWidget(self.chk_recurring, 0, 1)
        
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel(tr("dlg.faelligkeitstag_1")))
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(1)
        self.day_spin.setEnabled(False)
        day_layout.addWidget(self.day_spin)
        day_layout.addStretch()
        flags_layout.addLayout(day_layout, 1, 0, 1, 2)
        
        layout.addWidget(flags_group)
        
        # Verbindungen
        self.chk_recurring.toggled.connect(self.day_spin.setEnabled)
        
        # === Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_create = QPushButton("Kategorie erstellen")
        self.btn_create.setDefault(True)
        btn_layout.addWidget(self.btn_create)
        
        self.btn_cancel = QPushButton(tr("btn.cancel"))
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # Signale
        self.btn_create.clicked.connect(self._create_category)
        self.btn_cancel.clicked.connect(self.reject)
    
    def _create_category(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Hinweis", tr("account.bitte_einen_namen_eingeben"))
            return
        
        # Prüfen ob Name bereits existiert
        for cat in self.existing_categories:
            if cat.name.lower() == name.lower():
                QMessageBox.warning(
                    self, "Fehler", 
                    f"Eine Kategorie mit dem Namen '{name}' existiert bereits."
                )
                return
        
        parent_id = self.parent_combo.currentData()
        is_fix = self.chk_fix.isChecked()
        is_recurring = self.chk_recurring.isChecked()
        recurring_day = self.day_spin.value() if is_recurring else 1
        
        try:
            self._created_id = self.cat_model.create(
                typ=self.typ,
                name=name,
                is_fix=is_fix,
                is_recurring=is_recurring,
                recurring_day=recurring_day,
                parent_id=parent_id
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Konnte Kategorie nicht erstellen:\n{e}")
    
    def get_created_name(self) -> str:
        return self.name_edit.text().strip()
    
    def get_created_id(self) -> int | None:
        return self._created_id


class CategoryManagementWidget(QWidget):
    """Widget für Kategorie-Verwaltung im Budget-Dialog."""
    
    category_changed = Signal()  # Signalisiert Änderungen
    
    def __init__(self, parent=None, *, conn: sqlite3.Connection, typ: str):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self.typ = typ
        
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Kategorie-ComboBox
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setMinimumWidth(200)
        self.category_combo.setPlaceholderText(tr("dlg.kategorie_eingeben_oder_auswaehlen"))
        # Autofilter/Completer deaktivieren - nur manuelle Auswahl
        self.category_combo.setCompleter(None)
        layout.addWidget(self.category_combo, 1)
        
        # Management-Button mit Menü
        self.btn_manage = QToolButton()
        self.btn_manage.setText("")
        self.btn_manage.setIcon(get_icon("⚙️"))
        self.btn_manage.setToolTip("Kategorie-Optionen")
        self.btn_manage.setPopupMode(QToolButton.InstantPopup)
        
        menu = QMenu(self.btn_manage)
        self.act_new = menu.addAction(tr("budget.ctx.new_category"))
        self.act_new_sub = menu.addAction("Neue Unterkategorie…")
        self.act_new_sub.setIcon(get_icon("📂"))
        menu.addSeparator()
        self.act_rename = menu.addAction(tr("budget.ctx.rename"))
        self.act_delete = menu.addAction(tr("btn.loeschen_2"))
        menu.addSeparator()
        self.act_toggle_fix = menu.addAction("Fixkosten umschalten")
        self.act_toggle_fix.setIcon(get_icon("📌"))
        self.act_toggle_rec = menu.addAction("Wiederkehrend umschalten")
        self.act_toggle_rec.setIcon(get_icon("🔁"))
        self.act_set_day = menu.addAction(tr("dlg.faelligkeitstag_setzen_1"))
        
        self.btn_manage.setMenu(menu)
        layout.addWidget(self.btn_manage)
        
        # Signale verbinden
        self.act_new.triggered.connect(self._new_category)
        self.act_new_sub.triggered.connect(self._new_subcategory)
        self.act_rename.triggered.connect(self._rename_category)
        self.act_delete.triggered.connect(self._delete_category)
        self.act_toggle_fix.triggered.connect(self._toggle_fix)
        self.act_toggle_rec.triggered.connect(self._toggle_recurring)
        self.act_set_day.triggered.connect(self._set_day)
        
        self._refresh_categories()
    
    def set_typ(self, typ: str) -> None:
        """Ändert den Typ und lädt Kategorien neu."""
        self.typ = typ
        self._refresh_categories()
    
    def _refresh_categories(self) -> None:
        """Lädt die Kategorien-Liste neu."""
        current_text = self.category_combo.currentText()
        self.category_combo.clear()
        
        cats = self.cat_model.list(self.typ)
        # Hierarchische Darstellung
        nodes = self.cat_model.build_tree(cats)
        
        def add_items(children: list[dict], depth: int = 0):
            for node in children:
                cat: Category = node["cat"]
                prefix = "  " * depth
                marker = "▸ " if node["children"] else "• "
                display = f"{prefix}{marker}{cat.name}"
                self.category_combo.addItem(display, cat.name)
                add_items(node["children"], depth + 1)
        
        add_items(nodes)
        
        # Vorherige Auswahl wiederherstellen
        if current_text:
            idx = self.category_combo.findData(current_text)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setEditText(current_text)
    
    def get_category(self) -> str:
        """Gibt den aktuell ausgewählten/eingegebenen Kategorie-Namen zurück."""
        data = self.category_combo.currentData()
        if data:
            return str(data)
        return self.category_combo.currentText().strip().lstrip("▸• ").strip()
    
    def set_category(self, name: str) -> None:
        """Setzt die ausgewählte Kategorie."""
        idx = self.category_combo.findData(name)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setEditText(name)
    
    def _get_selected_category(self) -> Category | None:
        """Gibt die aktuell ausgewählte Kategorie als Category-Objekt zurück."""
        name = self.get_category()
        if not name:
            return None
        
        for cat in self.cat_model.list(self.typ):
            if cat.name == name:
                return cat
        return None
    
    def _new_category(self) -> None:
        """Erstellt eine neue Hauptkategorie."""
        name, ok = QInputDialog.getText(
            self, "Neue Kategorie", 
            f"Name der neuen Kategorie ({self.typ}):"
        )
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        try:
            self.cat_model.create(
                typ=self.typ,
                name=name,
                is_fix=False,
                is_recurring=False,
                parent_id=None
            )
            self._refresh_categories()
            self.set_category(name)
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Konnte Kategorie nicht erstellen:\n{e}")
    
    def _new_subcategory(self) -> None:
        """Erstellt eine neue Unterkategorie."""
        parent_cat = self._get_selected_category()
        
        # Parent-Auswahl Dialog
        cats = self.cat_model.list(self.typ)
        if not cats:
            QMessageBox.information(
                self, tr("msg.info"),
                tr("budget.msg.no_categories_create_main")
            )
            return
        
        # Auswahl der Parent-Kategorie
        items = [cat.name for cat in cats]
        default_idx = 0
        if parent_cat:
            try:
                default_idx = items.index(parent_cat.name)
            except ValueError as e:
                logger.debug("default_idx = items.index(parent_cat.name): %s", e)
        
        parent_name, ok = QInputDialog.getItem(
            self, "Parent-Kategorie",
            tr("dlg.unter_welcher_kategorie_soll"),
            items, default_idx, False
        )
        if not ok:
            return
        
        # Parent-ID finden
        parent_id = None
        for cat in cats:
            if cat.name == parent_name:
                parent_id = cat.id
                break
        
        # Name der neuen Unterkategorie
        name, ok = QInputDialog.getText(
            self, tr("budget.title.new_subcategory"),
            f"Name der neuen Unterkategorie unter '{parent_name}':"
        )
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        try:
            self.cat_model.create(
                typ=self.typ,
                name=name,
                is_fix=False,
                is_recurring=False,
                parent_id=parent_id
            )
            self._refresh_categories()
            self.set_category(name)
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Konnte Unterkategorie nicht erstellen:\n{e}")
    
    def _rename_category(self) -> None:
        """Benennt die ausgewählte Kategorie um."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie"))
            return
        
        new_name, ok = QInputDialog.getText(
            self, "Umbenennen",
            f"Neuer Name für '{cat.name}':",
            text=cat.name
        )
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        if new_name == cat.name:
            return
        
        try:
            self.cat_model.rename_and_cascade(
                cat.id, typ=self.typ, 
                old_name=cat.name, new_name=new_name
            )
            self._refresh_categories()
            self.set_category(new_name)
            self.category_changed.emit()
            QMessageBox.information(
                self, "OK", 
                f"Kategorie umbenannt: '{cat.name}' → '{new_name}'\n"
                "Alle Budget- und Tracking-Einträge wurden aktualisiert."
            )
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Umbenennen fehlgeschlagen:\n{e}")
    
    def _delete_category(self) -> None:
        """Löscht die ausgewählte Kategorie."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie"))
            return
        
        # Prüfen ob Unterkategorien vorhanden
        all_cats = self.cat_model.list(self.typ)
        has_children = any(c.parent_id == cat.id for c in all_cats)
        
        msg = f"Kategorie '{cat.name}' wirklich löschen?"
        if has_children:
            msg += "\n\n⚠️ WARNUNG: Diese Kategorie hat Unterkategorien, die ebenfalls gelöscht werden!"
        
        if QMessageBox.question(self, tr("btn.loeschen_bestaetigen"), msg) != QMessageBox.Yes:
            return
        
        try:
            # IDs zum Löschen sammeln (inkl. Kinder)
            ids_to_delete = [cat.id]
            
            def collect_children(parent_id: int):
                for c in all_cats:
                    if c.parent_id == parent_id:
                        ids_to_delete.append(c.id)
                        collect_children(c.id)
            
            collect_children(cat.id)
            
            self.cat_model.delete_by_ids(ids_to_delete)
            self._refresh_categories()
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.delete_failed", e=e))
    
    def _toggle_fix(self) -> None:
        """Fixkosten-Flag umschalten."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie"))
            return
        
        try:
            self.cat_model.update_flags(cat.id, is_fix=not cat.is_fix)
            status = "aktiviert" if not cat.is_fix else "deaktiviert"
            QMessageBox.information(self, tr("msg.info"), trf("msg.fixcost_status_changed", cat_name=cat.name, status=status))
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))
    
    def _toggle_recurring(self) -> None:
        """Wiederkehrend-Flag umschalten."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie"))
            return
        
        try:
            self.cat_model.update_flags(cat.id, is_recurring=not cat.is_recurring)
            status = "aktiviert" if not cat.is_recurring else "deaktiviert"
            QMessageBox.information(self, tr("msg.info"), trf("msg.recurring_status_changed", cat_name=cat.name, status=status))
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))
    
    def _set_day(self) -> None:
        """Fälligkeitstag setzen."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie"))
            return
        
        day, ok = QInputDialog.getInt(
            self, tr("dlg.faelligkeitstag"),
            f"Tag im Monat für '{cat.name}' (1-31):",
            cat.recurring_day, 1, 31
        )
        if not ok:
            return
        
        try:
            self.cat_model.update_flags(cat.id, is_recurring=True, recurring_day=day)
            QMessageBox.information(
                self, "OK", 
                f"Fälligkeitstag für '{cat.name}' auf {day}. gesetzt.\n"
                "(Wiederkehrend wurde automatisch aktiviert)"
            )
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))
    
    def check_and_create_if_needed(self) -> bool:
        """
        Prüft ob die eingegebene Kategorie existiert.
        Falls nicht, wird ein Dialog zum Erstellen angeboten.
        
        Returns: True wenn Kategorie existiert oder erstellt wurde, False bei Abbruch
        """
        name = self.get_category()
        if not name:
            return False
        
        # Prüfen ob Kategorie existiert
        existing = self.cat_model.list(self.typ)
        for cat in existing:
            if cat.name.lower() == name.lower():
                return True
        
        # Kategorie existiert nicht -> Dialog anbieten
        reply = QMessageBox.question(
            self,
            tr("dlg.kategorie_nicht_gefunden"),
            f"Die Kategorie '{name}' existiert noch nicht.\n\n" +
            tr("btn.moechtest_du_sie_jetzt"),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
        )
        
        if reply == QMessageBox.Cancel:
            return False
        
        if reply == QMessageBox.No:
            return True  # Trotzdem fortfahren (User-Entscheidung)
        
        # Dialog zum Erstellen öffnen
        dlg = NewCategoryDialog(
            self,
            typ=self.typ,
            category_name=name,
            cat_model=self.cat_model,
            existing_categories=existing
        )
        
        if dlg.exec() == QDialog.Accepted:
            created_name = dlg.get_created_name()
            self._refresh_categories()
            self.set_category(created_name)
            self.category_changed.emit()
            return True
        
        return False


class BudgetEntryDialogExtended(QDialog):
    """
    Erweiterter Budget-Entry-Dialog mit integrierter Kategorie-Verwaltung.
    
    Features:
    - Kategorie-ComboBox mit Management-Button
    - Automatische Erkennung neuer Kategorien
    - Inline-Erstellung von Kategorien mit Parent-Auswahl
    - Kategorie-Flags direkt setzen
    """
    
    def __init__(self, parent=None, *, conn: sqlite3.Connection, 
                 default_year: int, default_typ: str, 
                 preset: Optional[dict] = None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.budget_entry"))
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        
        # === Jahr und Typ ===
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

        # === Kategorie-Management-Widget ===
        self.category_widget = CategoryManagementWidget(
            self, conn=conn, typ=default_typ
        )
        
        # === Betrag ===
        self.amount = QLineEdit()
        self.amount.setPlaceholderText("z.B. 1200.00")
        
        # === Modus ===
        self.mode = QComboBox()
        self.mode.addItems(["Monat", "Alle", "Bereich"])
        
        self.month = QComboBox()
        self.month.addItems(_get_months())
        
        self.from_month = QComboBox()
        self.from_month.addItems(_get_months())
        
        self.to_month = QComboBox()
        self.to_month.addItems(_get_months())
        
        self.only_if_empty = QCheckBox(tr("dlg.nur_ueberschreiben_wenn_zelle"))
        self.only_if_empty.setChecked(False)
        
        # === Buttons ===
        self.btn_ok = QPushButton(tr("dlg.uebernehmen"))
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton(tr("btn.cancel"))
        
        # === Layout ===
        form = QFormLayout()
        form.addRow("Jahr:", self.year)
        form.addRow("Typ:", self.typ)
        form.addRow(tr("lbl.category"), self.category_widget)
        form.addRow(f"Betrag ({currency_header()}):", self.amount)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        form.addRow(line)
        
        form.addRow("Modus:", self.mode)
        form.addRow("Monat:", self.month)
        form.addRow("Von:", self.from_month)
        form.addRow("Bis:", self.to_month)
        form.addRow("", self.only_if_empty)
        
        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)
        
        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)
        
        # === Signale ===
        self.mode.currentTextChanged.connect(self._mode_changed)
        self.typ.currentIndexChanged.connect(
            lambda _: self._typ_changed(self.typ.currentData() or self.typ.currentText())
        )
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)
        
        self._mode_changed(self.mode.currentText())
        
        if preset:
            self._apply_preset(preset)
    
    def _typ_changed(self, typ: str) -> None:
        """Aktualisiert die Kategorie-Liste bei Typwechsel."""
        self.category_widget.set_typ(typ)
    
    def _mode_changed(self, mode: str) -> None:
        is_month = mode == "Monat"
        is_range = mode == "Bereich"
        self.month.setEnabled(is_month)
        self.from_month.setEnabled(is_range)
        self.to_month.setEnabled(is_range)
    
    def _apply_preset(self, preset: dict) -> None:
        if "category" in preset and preset["category"]:
            self.category_widget.set_category(str(preset["category"]))
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
    
    def _validate_and_accept(self) -> None:
        # Kategorie prüfen/erstellen
        if not self.category_widget.check_and_create_if_needed():
            return
        
        cat = self.category_widget.get_category()
        if not cat:
            QMessageBox.warning(self, "Fehlt", tr("dlg.bitte_kategorie_auswaehleneingeben"))
            return
        
        try:
            amt = parse_amount(self.amount.text())
        except Exception:
            QMessageBox.warning(self, "Hinweis", tr("dlg.betrag_ist_ungueltig"))
            return
        
        # Ausgaben: negative Zahlen verhindern
        typ_data = self.typ.currentData() or self.typ.currentText()
        if typ_data == TYP_EXPENSES and amt < 0:
            QMessageBox.warning(
                self, tr("dlg.nicht_erlaubt"), 
                tr("dlg.bei_ausgaben_sind_negative")
            )
            return
        
        self.accept()
    
    def get_request(self) -> BudgetEntryRequest:
        mode = self.mode.currentText()
        month = self.month.currentIndex() + 1
        fm = self.from_month.currentIndex() + 1
        tm = self.to_month.currentIndex() + 1
        amt = parse_amount(self.amount.text())
        
        return BudgetEntryRequest(
            year=int(self.year.value()),
            typ=str(self.typ.currentData() or self.typ.currentText()),
            category=str(self.category_widget.get_category()),
            amount=float(amt),
            mode=str(mode),
            month=int(month),
            from_month=int(fm),
            to_month=int(tm),
            only_if_empty=bool(self.only_if_empty.isChecked()),
        )
