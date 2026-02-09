"""
Kategorie-Eigenschaften-Dialog für schnelle Bearbeitung.

Features:
- Einfache Bearbeitung von Name, Fixkosten, Wiederkehrend, Tag
- Parent-Kategorie ändern
- Bulk-Edit für mehrere Kategorien
"""
from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QGridLayout,
    QLabel, QLineEdit, QCheckBox, QSpinBox, QComboBox, QPushButton,
    QGroupBox, QMessageBox, QDialogButtonBox, QListWidget, QListWidgetItem,
    QWidget, QFrame
)

from model.category_model import CategoryModel, Category


class CategoryPropertiesDialog(QDialog):
    """Dialog zum Bearbeiten einer einzelnen Kategorie."""
    
    category_updated = Signal()  # Wird ausgelöst wenn Änderungen gespeichert wurden
    
    def __init__(self, parent=None, *, conn: sqlite3.Connection, 
                 category_name: str, typ: str):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self.typ = typ
        self.original_name = category_name
        
        # Kategorie laden
        self.category = self._find_category(category_name)
        if not self.category:
            QMessageBox.warning(self, "Fehler", f"Kategorie '{category_name}' nicht gefunden.")
            self.reject()
            return
        
        self.setWindowTitle(f"Kategorie bearbeiten: {category_name}")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self._build_ui()
        self._load_data()
    
    def _find_category(self, name: str) -> Category | None:
        for cat in self.cat_model.list(self.typ):
            if cat.name == name:
                return cat
        return None
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # === Basis-Eigenschaften ===
        basic_group = QGroupBox("Basis-Eigenschaften")
        form = QFormLayout(basic_group)
        
        self.name_edit = QLineEdit()
        form.addRow("Name:", self.name_edit)
        
        self.typ_label = QLabel(f"<b>{self.typ}</b>")
        form.addRow("Typ:", self.typ_label)
        
        # Parent-Kategorie
        self.parent_combo = QComboBox()
        self.parent_combo.addItem("— Keine (Hauptkategorie) —", None)
        for cat in self.cat_model.list(self.typ):
            if cat.id != self.category.id:  # Sich selbst nicht als Parent erlauben
                indent = "  " if cat.parent_id else ""
                self.parent_combo.addItem(f"{indent}{cat.name}", cat.id)
        form.addRow("Parent:", self.parent_combo)
        
        layout.addWidget(basic_group)
        
        # === Flags ===
        flags_group = QGroupBox("Eigenschaften für Fixkosten & Wiederkehrende")
        flags_layout = QGridLayout(flags_group)
        
        self.chk_fix = QCheckBox("Fixkosten")
        self.chk_fix.setToolTip(
            "Markiert diese Kategorie als Fixkosten.\n"
            "Fixkosten werden in der Übersicht separat ausgewiesen."
        )
        flags_layout.addWidget(self.chk_fix, 0, 0)
        
        self.chk_recurring = QCheckBox("Wiederkehrend")
        self.chk_recurring.setToolTip(
            "Markiert diese Kategorie als wiederkehrende Ausgabe.\n"
            "Wiederkehrende Kategorien können automatisch gebucht werden."
        )
        flags_layout.addWidget(self.chk_recurring, 0, 1)
        
        # Tag im Monat
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("Fälligkeitstag:"))
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setSuffix(". des Monats")
        self.day_spin.setToolTip("An welchem Tag im Monat ist diese Ausgabe fällig?")
        day_layout.addWidget(self.day_spin)
        day_layout.addStretch()
        flags_layout.addLayout(day_layout, 1, 0, 1, 2)
        
        # Hinweis
        hint = QLabel(
            "<small><i>Tipp: Wenn du einen Fälligkeitstag setzt, wird "
            "'Wiederkehrend' automatisch aktiviert.</i></small>"
        )
        hint.setWordWrap(True)
        flags_layout.addWidget(hint, 2, 0, 1, 2)
        
        layout.addWidget(flags_group)
        
        # === Buttons ===
        btn_layout = QHBoxLayout()
        
        self.btn_delete = QPushButton("🗑️ Löschen")
        self.btn_delete.setStyleSheet("color: #c0392b;")
        btn_layout.addWidget(self.btn_delete)
        
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Abbrechen")
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_save = QPushButton("💾 Speichern")
        self.btn_save.setDefault(True)
        btn_layout.addWidget(self.btn_save)
        
        layout.addLayout(btn_layout)
        
        # Signale
        self.chk_recurring.toggled.connect(self._on_recurring_toggled)
        self.day_spin.valueChanged.connect(self._on_day_changed)
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_delete.clicked.connect(self._delete)
    
    def _load_data(self) -> None:
        self.name_edit.setText(self.category.name)
        
        # Parent setzen
        if self.category.parent_id:
            idx = self.parent_combo.findData(self.category.parent_id)
            if idx >= 0:
                self.parent_combo.setCurrentIndex(idx)
        
        self.chk_fix.setChecked(self.category.is_fix)
        self.chk_recurring.setChecked(self.category.is_recurring)
        self.day_spin.setValue(self.category.recurring_day)
        self.day_spin.setEnabled(self.category.is_recurring)
    
    def _on_recurring_toggled(self, checked: bool) -> None:
        self.day_spin.setEnabled(checked)
    
    def _on_day_changed(self, value: int) -> None:
        # Wenn Tag geändert wird, Wiederkehrend automatisch aktivieren
        if value > 0 and not self.chk_recurring.isChecked():
            self.chk_recurring.setChecked(True)
    
    def _save(self) -> None:
        new_name = self.name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Fehler", "Bitte einen Namen eingeben.")
            return
        
        # Prüfen ob neuer Name bereits existiert (wenn umbenannt)
        if new_name != self.category.name:
            for cat in self.cat_model.list(self.typ):
                if cat.name.lower() == new_name.lower() and cat.id != self.category.id:
                    QMessageBox.warning(
                        self, "Fehler",
                        f"Eine Kategorie mit dem Namen '{new_name}' existiert bereits."
                    )
                    return
        
        try:
            # Name ändern (mit Cascade zu Budget/Tracking)
            if new_name != self.category.name:
                self.cat_model.rename_and_cascade(
                    self.category.id,
                    typ=self.typ,
                    old_name=self.category.name,
                    new_name=new_name
                )
            
            # Parent ändern
            new_parent_id = self.parent_combo.currentData()
            if new_parent_id != self.category.parent_id:
                self.cat_model.update_parent(self.category.id, new_parent_id)
            
            # Flags speichern
            is_fix = self.chk_fix.isChecked()
            is_recurring = self.chk_recurring.isChecked()
            recurring_day = self.day_spin.value() if is_recurring else 1
            
            self.cat_model.update_flags(
                self.category.id,
                is_fix=is_fix,
                is_recurring=is_recurring,
                recurring_day=recurring_day
            )
            
            self.category_updated.emit()
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Speichern fehlgeschlagen:\n{e}")
    
    def _delete(self) -> None:
        # Prüfen ob Unterkategorien vorhanden
        all_cats = self.cat_model.list(self.typ)
        children = [c for c in all_cats if c.parent_id == self.category.id]
        
        msg = f"Kategorie '{self.category.name}' wirklich löschen?"
        if children:
            child_names = ", ".join(c.name for c in children[:5])
            if len(children) > 5:
                child_names += f" und {len(children) - 5} weitere"
            msg += f"\n\n⚠️ WARNUNG: {len(children)} Unterkategorie(n) werden ebenfalls gelöscht:\n{child_names}"
        
        if QMessageBox.question(self, "Löschen bestätigen", msg) != QMessageBox.Yes:
            return
        
        try:
            # IDs zum Löschen sammeln (inkl. Kinder)
            ids_to_delete = [self.category.id]
            
            def collect_children(parent_id: int):
                for c in all_cats:
                    if c.parent_id == parent_id:
                        ids_to_delete.append(c.id)
                        collect_children(c.id)
            
            collect_children(self.category.id)
            
            self.cat_model.delete_by_ids(ids_to_delete)
            self.category_updated.emit()
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Löschen fehlgeschlagen:\n{e}")


class BulkCategoryEditDialog(QDialog):
    """Dialog zum Bearbeiten mehrerer Kategorien gleichzeitig."""
    
    categories_updated = Signal()
    
    def __init__(self, parent=None, *, conn: sqlite3.Connection,
                 categories: list[tuple[str, str]]):  # List of (name, typ)
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self.categories = categories  # [(name, typ), ...]
        
        self.setWindowTitle(f"Massenbearbeitung ({len(categories)} Kategorien)")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self._build_ui()
    
    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        
        # Info
        info = QLabel(f"<b>{len(self.categories)}</b> Kategorien ausgewählt:")
        layout.addWidget(info)
        
        # Liste der ausgewählten Kategorien
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(100)
        for name, typ in self.categories:
            self.list_widget.addItem(f"{name} ({typ})")
        layout.addWidget(self.list_widget)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)
        
        # === Änderungen ===
        changes_group = QGroupBox("Änderungen anwenden")
        form = QFormLayout(changes_group)
        
        # Fixkosten
        self.fix_combo = QComboBox()
        self.fix_combo.addItems(["— Nicht ändern —", "✓ Aktivieren", "✗ Deaktivieren"])
        form.addRow("Fixkosten:", self.fix_combo)
        
        # Wiederkehrend
        self.rec_combo = QComboBox()
        self.rec_combo.addItems(["— Nicht ändern —", "✓ Aktivieren", "✗ Deaktivieren"])
        form.addRow("Wiederkehrend:", self.rec_combo)
        
        # Tag
        day_layout = QHBoxLayout()
        self.day_check = QCheckBox("Fälligkeitstag setzen:")
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setSuffix(". des Monats")
        self.day_spin.setEnabled(False)
        day_layout.addWidget(self.day_check)
        day_layout.addWidget(self.day_spin)
        day_layout.addStretch()
        form.addRow("", day_layout)
        
        layout.addWidget(changes_group)
        
        # Hinweis
        hint = QLabel(
            "<small><i>Hinweis: Wenn du einen Fälligkeitstag setzt, wird "
            "'Wiederkehrend' automatisch aktiviert.</i></small>"
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        
        # === Buttons ===
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        
        # Signale
        self.day_check.toggled.connect(self.day_spin.setEnabled)
    
    def _apply(self) -> None:
        fix_choice = self.fix_combo.currentIndex()
        rec_choice = self.rec_combo.currentIndex()
        set_day = self.day_check.isChecked()
        day_val = self.day_spin.value()
        
        if fix_choice == 0 and rec_choice == 0 and not set_day:
            QMessageBox.information(
                self, "Hinweis", 
                "Keine Änderungen ausgewählt."
            )
            return
        
        changed = 0
        errors = []
        
        for name, typ in self.categories:
            cat = None
            for c in self.cat_model.list(typ):
                if c.name == name:
                    cat = c
                    break
            
            if not cat:
                errors.append(f"{name} ({typ})")
                continue
            
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
                    self.cat_model.update_flags(cat.id, **kwargs)
                    changed += 1
                    
            except Exception as e:
                errors.append(f"{name}: {e}")
        
        msg = f"{changed} Kategorie(n) aktualisiert."
        if errors:
            msg += f"\n\nFehler bei:\n" + "\n".join(errors[:10])
        
        QMessageBox.information(self, "Ergebnis", msg)
        
        if changed > 0:
            self.categories_updated.emit()
        
        self.accept()


class QuickCategoryDialog(QDialog):
    """Schneller Dialog zum Erstellen einer neuen Kategorie."""
    
    category_created = Signal(str, str)  # name, typ
    
    def __init__(self, parent=None, *, conn: sqlite3.Connection,
                 default_typ: str = "Ausgaben", default_name: str = ""):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        
        self.setWindowTitle("Neue Kategorie erstellen")
        self.setModal(True)
        self.setMinimumWidth(400)
        
        self._build_ui(default_typ, default_name)
    
    def _build_ui(self, default_typ: str, default_name: str) -> None:
        layout = QVBoxLayout(self)
        
        form = QFormLayout()
        
        # Name
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setPlaceholderText("z.B. Versicherung, Streaming, ...")
        form.addRow("Name:", self.name_edit)
        
        # Typ
        self.typ_combo = QComboBox()
        self.typ_combo.addItems(["Ausgaben", "Einkommen", "Ersparnisse"])
        self.typ_combo.setCurrentText(default_typ)
        form.addRow("Typ:", self.typ_combo)
        
        # Parent (dynamisch basierend auf Typ)
        self.parent_combo = QComboBox()
        form.addRow("Parent:", self.parent_combo)
        
        layout.addLayout(form)
        
        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)
        
        # Quick-Flags
        flags_layout = QHBoxLayout()
        self.chk_fix = QCheckBox("Fixkosten")
        self.chk_recurring = QCheckBox("Wiederkehrend")
        flags_layout.addWidget(self.chk_fix)
        flags_layout.addWidget(self.chk_recurring)
        flags_layout.addStretch()
        layout.addLayout(flags_layout)
        
        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        
        self.btn_cancel = QPushButton("Abbrechen")
        btn_layout.addWidget(self.btn_cancel)
        
        self.btn_create = QPushButton("✓ Erstellen")
        self.btn_create.setDefault(True)
        btn_layout.addWidget(self.btn_create)
        
        layout.addLayout(btn_layout)
        
        # Signale
        self.typ_combo.currentTextChanged.connect(self._update_parents)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_create.clicked.connect(self._create)
        
        # Initial parents laden
        self._update_parents(default_typ)
    
    def _update_parents(self, typ: str) -> None:
        self.parent_combo.clear()
        self.parent_combo.addItem("— Hauptkategorie (kein Parent) —", None)
        
        for cat in self.cat_model.list(typ):
            indent = "  " if cat.parent_id else ""
            self.parent_combo.addItem(f"{indent}{cat.name}", cat.id)
    
    def _create(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Bitte einen Namen eingeben.")
            return
        
        typ = self.typ_combo.currentText()
        
        # Prüfen ob Name bereits existiert
        for cat in self.cat_model.list(typ):
            if cat.name.lower() == name.lower():
                QMessageBox.warning(
                    self, "Fehler",
                    f"Eine Kategorie mit dem Namen '{name}' existiert bereits."
                )
                return
        
        try:
            parent_id = self.parent_combo.currentData()
            is_fix = self.chk_fix.isChecked()
            is_recurring = self.chk_recurring.isChecked()
            
            self.cat_model.create(
                typ=typ,
                name=name,
                is_fix=is_fix,
                is_recurring=is_recurring,
                parent_id=parent_id
            )
            
            self.category_created.emit(name, typ)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Erstellen fehlgeschlagen:\n{e}")
    
    def get_created_name(self) -> str:
        return self.name_edit.text().strip()
    
    def get_created_typ(self) -> str:
        return self.typ_combo.currentText()
