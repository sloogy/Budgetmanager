"""
Kategorien-Manager-Dialog für einfache Verwaltung aller Kategorien.

Features:
- Alle Kategorien auf einen Blick (gruppiert nach Typ)
- Schnelles Bearbeiten von Fixkosten, Wiederkehrend, Fälligkeitstag
- Mehrfachauswahl für Bulk-Operationen
- Direktes Erstellen/Umbenennen/Löschen
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush
from views.ui_colors import ui_colors
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QLineEdit, QCheckBox, QSpinBox, QComboBox, QPushButton,
    QGroupBox, QMessageBox, QDialogButtonBox, QTreeWidget, QTreeWidgetItem,
    QWidget, QFrame, QSplitter, QMenu, QInputDialog, QHeaderView,
    QAbstractItemView
)

from model.category_model import CategoryModel, Category
from utils.icons import get_icon
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


class CategoryManagerDialog(QDialog):
    """
    Umfassender Kategorien-Manager-Dialog.
    
    Ermöglicht schnelles und einfaches Verwalten aller Kategorien
    mit Mehrfachauswahl und Inline-Bearbeitung.
    """
    
    categories_changed = Signal()
    
    def __init__(self, parent=None, *, conn: sqlite3.Connection):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        
        self.setWindowTitle(tr("dlg.category_manager"))
        self.setModal(False)  # Nicht-modal für bessere UX
        self.setMinimumSize(900, 600)
        
        self._build_ui()
        self._load_categories()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # === Toolbar ===
        toolbar = QHBoxLayout()
        
        self.btn_add = QPushButton("Neue Kategorie")
        self.btn_add.setIcon(get_icon("➕"))
        self.btn_add.clicked.connect(self._add_category)
        toolbar.addWidget(self.btn_add)
        
        self.btn_add_sub = QPushButton("Unterkategorie")
        self.btn_add_sub.setIcon(get_icon("📂"))
        self.btn_add_sub.clicked.connect(self._add_subcategory)
        toolbar.addWidget(self.btn_add_sub)
        
        toolbar.addSpacing(20)
        
        self.btn_rename = QPushButton("Umbenennen")
        self.btn_rename.setIcon(get_icon("✏️"))
        self.btn_rename.clicked.connect(self._rename_category)
        toolbar.addWidget(self.btn_rename)
        
        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_delete.setStyleSheet("")  # Theme handles button colors
        self.btn_delete.clicked.connect(self._delete_categories)
        toolbar.addWidget(self.btn_delete)
        
        toolbar.addStretch()
        
        # Filter
        toolbar.addWidget(QLabel(tr("lbl.filter_lbl")))
        self.filter_combo = QComboBox()
        self.filter_combo.addItems(["Alle", tr("kpi.expenses"), tr("kpi.income"), tr("typ.Ersparnisse"), 
                                     "Nur Fixkosten", "Nur Wiederkehrend"])
        self.filter_combo.currentTextChanged.connect(self._apply_filter)
        toolbar.addWidget(self.filter_combo)
        
        layout.addLayout(toolbar)
        
        # === Hauptbereich: Splitter mit Tree und Details ===
        splitter = QSplitter(Qt.Horizontal)
        
        # Kategorie-Baum
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels([tr("header.category"), "Typ", "Fix", "Wdh.", "Tag"])
        self.tree.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.tree.setContextMenuPolicy(Qt.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self._show_context_menu)
        self.tree.itemSelectionChanged.connect(self._on_selection_changed)
        self.tree.itemDoubleClicked.connect(self._on_double_click)
        
        # Spaltenbreiten
        header = self.tree.header()
        header.setSectionResizeMode(0, QHeaderView.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeToContents)
        
        splitter.addWidget(self.tree)
        
        # Details-Panel
        details_widget = QWidget()
        details_layout = QVBoxLayout(details_widget)
        
        # Auswahl-Info
        self.selection_label = QLabel(tr("dlg.keine_auswahl"))
        self.selection_label.setStyleSheet("font-weight: bold; font-size: 14px;")
        details_layout.addWidget(self.selection_label)
        
        # Eigenschaften-Editor
        props_group = QGroupBox(tr("lbl.edit_props"))
        props_layout = QGridLayout(props_group)
        
        # Fixkosten
        props_layout.addWidget(QLabel(tr("lbl.fixed_costs")), 0, 0)
        self.fix_combo = QComboBox()
        self.fix_combo.addItems([tr("dlg.nicht_aendern"), "✓ Aktivieren", "✗ Deaktivieren"])
        props_layout.addWidget(self.fix_combo, 0, 1)
        
        # Wiederkehrend
        props_layout.addWidget(QLabel(tr("lbl.recurring")), 1, 0)
        self.rec_combo = QComboBox()
        self.rec_combo.addItems([tr("dlg.nicht_aendern"), "✓ Aktivieren", "✗ Deaktivieren"])
        props_layout.addWidget(self.rec_combo, 1, 1)
        
        # Fälligkeitstag
        props_layout.addWidget(QLabel(tr("dlg.faelligkeitstag_1")), 2, 0)
        day_layout = QHBoxLayout()
        self.day_check = QCheckBox(tr("lbl.set_to"))
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setSuffix(". des Monats")
        self.day_spin.setEnabled(False)
        self.day_check.toggled.connect(self.day_spin.setEnabled)
        day_layout.addWidget(self.day_check)
        day_layout.addWidget(self.day_spin)
        day_layout.addStretch()
        props_layout.addLayout(day_layout, 2, 1)
        
        # Anwenden-Button
        self.btn_apply = QPushButton(tr("dlg.aenderungen_anwenden_1"))
        self.btn_apply.clicked.connect(self._apply_changes)
        self.btn_apply.setEnabled(False)
        props_layout.addWidget(self.btn_apply, 3, 0, 1, 2)
        
        details_layout.addWidget(props_group)
        
        # Schnellaktionen
        quick_group = QGroupBox(tr("lbl.quick_actions"))
        quick_layout = QVBoxLayout(quick_group)
        
        self.btn_all_fix = QPushButton(tr("ctx.set_all_fix_on"))
        self.btn_all_fix.clicked.connect(lambda: self._quick_set_flag("is_fix", True))
        quick_layout.addWidget(self.btn_all_fix)
        
        self.btn_all_rec = QPushButton(tr("ctx.set_all_recurring_on"))
        self.btn_all_rec.clicked.connect(lambda: self._quick_set_flag("is_recurring", True))
        quick_layout.addWidget(self.btn_all_rec)
        
        self.btn_no_fix = QPushButton(tr("ctx.set_all_fix_off"))
        self.btn_no_fix.clicked.connect(lambda: self._quick_set_flag("is_fix", False))
        quick_layout.addWidget(self.btn_no_fix)
        
        self.btn_no_rec = QPushButton(tr("ctx.set_all_recurring_off"))
        self.btn_no_rec.clicked.connect(lambda: self._quick_set_flag("is_recurring", False))
        quick_layout.addWidget(self.btn_no_rec)
        
        details_layout.addWidget(quick_group)
        details_layout.addStretch()
        
        splitter.addWidget(details_widget)
        splitter.setSizes([600, 300])
        
        layout.addWidget(splitter)
        
        # === Footer ===
        footer = QHBoxLayout()
        
        self.status_label = QLabel("")
        footer.addWidget(self.status_label)
        footer.addStretch()
        
        self.btn_refresh = QPushButton("Aktualisieren")
        self.btn_refresh.setIcon(get_icon("🔄"))
        self.btn_refresh.clicked.connect(self._load_categories)
        footer.addWidget(self.btn_refresh)
        
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self.accept)
        footer.addWidget(self.btn_close)
        
        layout.addLayout(footer)
    
    def _load_categories(self) -> None:
        """Lädt alle Kategorien in den Baum."""
        self.tree.clear()
        
        c = ui_colors(self)
        type_colors = {
            tr("kpi.expenses"): QColor(c.type_color(tr("kpi.expenses"))),
            tr("kpi.income"): QColor(c.type_color(tr("kpi.income"))),
            tr("typ.Ersparnisse"): QColor(c.type_color(tr("typ.Ersparnisse")))
        }
        
        total_count = 0
        
        for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
            cats = self.cat_model.list(typ)
            if not cats:
                continue
            
            # Typ als Root-Item
            type_item = QTreeWidgetItem(self.tree)
            type_item.setText(0, f"{typ} ({len(cats)})")
            type_item.setData(0, Qt.UserRole, {"type": "header", "typ": typ})
            type_item.setExpanded(True)
            
            # Styling für Typ-Header
            font = type_item.font(0)
            font.setBold(True)
            type_item.setFont(0, font)
            type_item.setForeground(0, QBrush(type_colors.get(typ, QColor(c.text))))
            
            # Kategorien nach Parent gruppieren
            root_cats = [cat for cat in cats if not cat.parent_id]
            child_map = {}
            for cat in cats:
                if cat.parent_id:
                    if cat.parent_id not in child_map:
                        child_map[cat.parent_id] = []
                    child_map[cat.parent_id].append(cat)
            
            def add_category(cat: Category, parent_item: QTreeWidgetItem):
                item = QTreeWidgetItem(parent_item)
                item.setText(0, cat.name)
                item.setText(1, typ)
                item.setText(2, "✓" if cat.is_fix else "")
                item.setText(3, "✓" if cat.is_recurring else "")
                item.setText(4, str(cat.recurring_day) if cat.is_recurring else "")
                
                item.setData(0, Qt.UserRole, {
                    "type": "category",
                    "id": cat.id,
                    "name": cat.name,
                    "typ": typ,
                    "is_fix": cat.is_fix,
                    "is_recurring": cat.is_recurring,
                    "recurring_day": cat.recurring_day,
                    "parent_id": cat.parent_id
                })
                
                # Farbkodierung
                if cat.is_fix and cat.is_recurring:
                    item.setBackground(0, QBrush(QColor(c.warning_bg)))  # Fix + Recurring
                elif cat.is_fix:
                    item.setBackground(0, QBrush(QColor(c.error_bg)))  # Nur Fix
                elif cat.is_recurring:
                    item.setBackground(0, QBrush(QColor(c.success_bg)))  # Nur Recurring
                
                # Kinder hinzufügen
                if cat.id in child_map:
                    for child in child_map[cat.id]:
                        add_category(child, item)
            
            for cat in root_cats:
                add_category(cat, type_item)
                total_count += 1
            
            # Kinder zählen
            total_count += len(cats) - len(root_cats)
        
        self.status_label.setText(f"{total_count} Kategorien geladen")
        self._apply_filter(self.filter_combo.currentText())
    
    def _apply_filter(self, filter_text: str) -> None:
        """Wendet Filter auf die Kategorien an."""
        for i in range(self.tree.topLevelItemCount()):
            type_item = self.tree.topLevelItem(i)
            data = type_item.data(0, Qt.UserRole) or {}
            typ = data.get("typ", "")
            
            # Typ-Filter
            show_type = (filter_text == "Alle" or 
                        filter_text == typ or
                        filter_text in ["Nur Fixkosten", "Nur Wiederkehrend"])
            type_item.setHidden(not show_type)
            
            if show_type:
                visible_children = 0
                for j in range(type_item.childCount()):
                    child = type_item.child(j)
                    child_data = child.data(0, Qt.UserRole) or {}
                    
                    show_child = True
                    if filter_text == "Nur Fixkosten":
                        show_child = child_data.get("is_fix", False)
                    elif filter_text == "Nur Wiederkehrend":
                        show_child = child_data.get("is_recurring", False)
                    
                    child.setHidden(not show_child)
                    if show_child:
                        visible_children += 1
                
                # Typ verstecken wenn keine sichtbaren Kinder
                if filter_text in ["Nur Fixkosten", "Nur Wiederkehrend"] and visible_children == 0:
                    type_item.setHidden(True)
    
    def _get_selected_categories(self) -> list[dict]:
        """Gibt die ausgewählten Kategorien zurück."""
        selected = []
        for item in self.tree.selectedItems():
            data = item.data(0, Qt.UserRole)
            if data and data.get("type") == "category":
                selected.append(data)
        return selected
    
    def _on_selection_changed(self) -> None:
        """Reagiert auf Auswahl-Änderungen."""
        selected = self._get_selected_categories()
        count = len(selected)
        
        if count == 0:
            self.selection_label.setText(tr("dlg.keine_auswahl"))
            self.btn_apply.setEnabled(False)
        elif count == 1:
            cat = selected[0]
            self.selection_label.setText(trf("lbl.selected_category", name=cat['name'], typ=cat['typ']))
            self.btn_apply.setEnabled(True)
            
            # Felder vorbelegen
            self.fix_combo.setCurrentIndex(1 if cat["is_fix"] else 2)
            self.rec_combo.setCurrentIndex(1 if cat["is_recurring"] else 2)
            if cat["is_recurring"]:
                self.day_check.setChecked(True)
                self.day_spin.setValue(cat["recurring_day"])
            else:
                self.day_check.setChecked(False)
        else:
            self.selection_label.setText(trf("dlg.count_kategorien_ausgewaehlt"))
            self.btn_apply.setEnabled(True)
            # Reset Combos für Mehrfachauswahl
            self.fix_combo.setCurrentIndex(0)
            self.rec_combo.setCurrentIndex(0)
            self.day_check.setChecked(False)
    
    def _on_double_click(self, item: QTreeWidgetItem, column: int) -> None:
        """Doppelklick öffnet Umbenennen."""
        data = item.data(0, Qt.UserRole)
        if data and data.get("type") == "category":
            self._rename_category()
    
    def _show_context_menu(self, pos) -> None:
        """Zeigt Kontextmenü."""
        item = self.tree.itemAt(pos)
        if not item:
            return
        
        data = item.data(0, Qt.UserRole)
        if not data or data.get("type") != "category":
            return
        
        menu = QMenu(self)
        
        act_rename = menu.addAction("Umbenennen", self._rename_category)
        act_rename.setIcon(get_icon("✏️"))
        menu.addAction(tr("btn.unterkategorie_hinzufuegen"), self._add_subcategory)
        menu.addSeparator()
        
        cat = data
        fix_text = tr("budget.ctx.fix_disable") if cat["is_fix"] else tr("budget.ctx.fix_enable")
        menu.addAction(fix_text, lambda: self._toggle_single_flag(cat["id"], "is_fix", not cat["is_fix"]))
        
        rec_text = tr("budget.ctx.rec_disable") if cat["is_recurring"] else tr("budget.ctx.rec_enable")
        menu.addAction(rec_text, lambda: self._toggle_single_flag(cat["id"], "is_recurring", not cat["is_recurring"]))
        
        act_set_day = menu.addAction(f"Fälligkeitstag setzen… ({cat['recurring_day']}.)",
                                     lambda: self._set_single_day(cat["id"]))
        act_set_day.setIcon(get_icon("📅"))
        
        menu.addSeparator()
        menu.addAction(tr("btn.loeschen_1"), self._delete_categories)
        
        menu.exec(self.tree.viewport().mapToGlobal(pos))
    
    def _toggle_single_flag(self, cat_id: int, flag: str, value: bool) -> None:
        """Schaltet ein einzelnes Flag um."""
        try:
            self.cat_model.update_flags(cat_id, **{flag: value})
            self._load_categories()
            self.categories_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))
    
    def _set_single_day(self, cat_id: int) -> None:
        """Setzt den Fälligkeitstag für eine einzelne Kategorie."""
        day, ok = QInputDialog.getInt(
            self, tr("dlg.faelligkeitstag"),
            "Tag im Monat (1-31):",
            1, 1, 31
        )
        if ok:
            try:
                self.cat_model.update_flags(cat_id, is_recurring=True, recurring_day=day)
                self._load_categories()
                self.categories_changed.emit()
            except Exception as e:
                QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))
    
    def _apply_changes(self) -> None:
        """Wendet die Änderungen auf alle ausgewählten Kategorien an."""
        selected = self._get_selected_categories()
        if not selected:
            return
        
        fix_choice = self.fix_combo.currentIndex()
        rec_choice = self.rec_combo.currentIndex()
        set_day = self.day_check.isChecked()
        day_val = self.day_spin.value()
        
        if fix_choice == 0 and rec_choice == 0 and not set_day:
            QMessageBox.information(self, tr("msg.info"), tr("msg.no_changes_selected"))
            return
        
        changed = 0
        errors = []
        
        for cat in selected:
            try:
                kwargs = {}
                
                if fix_choice == 1:
                    kwargs["is_fix"] = True
                elif fix_choice == 2:
                    kwargs["is_fix"] = False
                
                if rec_choice == 1:
                    kwargs["is_recurring"] = True
                elif rec_choice == 2:
                    kwargs["is_recurring"] = False
                
                if set_day:
                    kwargs["is_recurring"] = True
                    kwargs["recurring_day"] = day_val
                
                if kwargs:
                    self.cat_model.update_flags(cat["id"], **kwargs)
                    changed += 1
                    
            except Exception as e:
                errors.append(f"{cat['name']}: {e}")
        
        if changed > 0:
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(f"{changed} Kategorie(n) aktualisiert")
        
        if errors:
            QMessageBox.warning(
                self, "Teilweise fehlgeschlagen",
                "Fehler bei:\n" + "\n".join(errors[:10])
            )
    
    def _quick_set_flag(self, flag: str, value: bool) -> None:
        """Setzt ein Flag für alle ausgewählten Kategorien."""
        selected = self._get_selected_categories()
        if not selected:
            QMessageBox.information(self, tr("msg.info"), tr("msg.no_categories_selected"))
            return
        
        changed = 0
        for cat in selected:
            try:
                self.cat_model.update_flags(cat["id"], **{flag: value})
                changed += 1
            except Exception as e:
                logger.debug("self.cat_model.update_flags(cat['id'], **{flag: va: %s", e)
        
        if changed > 0:
            self._load_categories()
            self.categories_changed.emit()
            flag_name = tr("tracking.title.fixcosts") if flag == "is_fix" else tr("lbl.recurring")
            status = "aktiviert" if value else "deaktiviert"
            self.status_label.setText(trf("dlg.flag_name_fuer_changed_kategorien"))
    
    def _add_category(self) -> None:
        """Fügt eine neue Kategorie hinzu."""
        # Typ auswählen
        typ, ok = QInputDialog.getItem(
            self, "Neue Kategorie",
            "Typ:",
            [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS],
            0, False
        )
        if not ok:
            return
        
        name, ok = QInputDialog.getText(
            self, "Neue Kategorie",
            f"Name der neuen {typ}-Kategorie:"
        )
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # Prüfen ob existiert
        for cat in self.cat_model.list(typ):
            if cat.name.lower() == name.lower():
                QMessageBox.warning(
                    self, "Fehler",
                    f"Eine Kategorie '{name}' existiert bereits."
                )
                return
        
        try:
            self.cat_model.create(typ=typ, name=name)
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(f"Kategorie '{name}' erstellt")
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Erstellen fehlgeschlagen:\n{e}")
    
    def _add_subcategory(self) -> None:
        """Fügt eine Unterkategorie zur ausgewählten Kategorie hinzu."""
        selected = self._get_selected_categories()
        if len(selected) != 1:
            QMessageBox.information(
                self, "Hinweis",
                "Bitte genau eine Kategorie als Parent auswählen."
            )
            return
        
        parent = selected[0]
        
        name, ok = QInputDialog.getText(
            self, tr("budget.title.new_subcategory"),
            f"Name der neuen Unterkategorie unter '{parent['name']}':"
        )
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        try:
            self.cat_model.create(
                typ=parent["typ"],
                name=name,
                parent_id=parent["id"]
            )
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(f"Unterkategorie '{name}' erstellt")
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Erstellen fehlgeschlagen:\n{e}")
    
    def _rename_category(self) -> None:
        """Benennt die ausgewählte Kategorie um."""
        selected = self._get_selected_categories()
        if len(selected) != 1:
            QMessageBox.information(
                self, "Hinweis",
                "Bitte genau eine Kategorie zum Umbenennen auswählen."
            )
            return
        
        cat = selected[0]
        
        new_name, ok = QInputDialog.getText(
            self, tr("budget.title.rename_category"),
            f"Neuer Name für '{cat['name']}':",
            text=cat["name"]
        )
        if not ok or not new_name.strip():
            return
        
        new_name = new_name.strip()
        if new_name == cat["name"]:
            return
        
        # Prüfen ob existiert
        for c in self.cat_model.list(cat["typ"]):
            if c.name.lower() == new_name.lower() and c.id != cat["id"]:
                QMessageBox.warning(
                    self, "Fehler",
                    f"Eine Kategorie '{new_name}' existiert bereits."
                )
                return
        
        try:
            self.cat_model.rename_and_cascade(
                cat["id"],
                typ=cat["typ"],
                old_name=cat["name"],
                new_name=new_name
            )
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(f"Kategorie umbenannt: '{cat['name']}' → '{new_name}'")
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), f"Umbenennen fehlgeschlagen:\n{e}")
    
    def _delete_categories(self) -> None:
        """Löscht die ausgewählten Kategorien."""
        selected = self._get_selected_categories()
        if not selected:
            QMessageBox.information(self, tr("msg.info"), tr("msg.no_categories_selected"))
            return
        
        names = [c["name"] for c in selected[:10]]
        if len(selected) > 10:
            names.append(trf("dlg.und_lenselected_10_weitere"))
        
        msg = f"{len(selected)} Kategorie(n) wirklich löschen?\n\n"
        msg += "\n".join(f"  • {n}" for n in names)
        msg += "\n\n⚠️ WARNUNG: Alle zugehörigen Budget- und Tracking-Einträge werden ebenfalls gelöscht!"
        
        if QMessageBox.question(self, tr("btn.loeschen_bestaetigen"), msg) != QMessageBox.Yes:
            return
        
        deleted = 0
        errors = []
        
        for cat in selected:
            try:
                # Alle Kinder sammeln
                all_cats = self.cat_model.list(cat["typ"])
                ids_to_delete = [cat["id"]]
                
                def collect_children(parent_id: int):
                    for c in all_cats:
                        if c.parent_id == parent_id:
                            ids_to_delete.append(c.id)
                            collect_children(c.id)
                
                collect_children(cat["id"])
                
                self.cat_model.delete_by_ids(ids_to_delete)
                deleted += 1
            except Exception as e:
                errors.append(f"{cat['name']}: {e}")
        
        if deleted > 0:
            self._load_categories()
            self.categories_changed.emit()
            self.status_label.setText(trf("dlg.deleted_kategorien_geloescht"))
        
        if errors:
            QMessageBox.warning(
                self, "Teilweise fehlgeschlagen",
                "Fehler bei:\n" + "\n".join(errors[:10])
            )
