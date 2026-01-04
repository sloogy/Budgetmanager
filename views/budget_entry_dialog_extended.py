"""
Budget-Entry-Dialog mit integrierter Kategorie-Verwaltung.

Funktionen:
- Neue Kategorien direkt erstellen (als Hauptkategorie oder Unterkategorie)
- Parent-Kategorie per Dropdown wählbar
- Kategorie-Flags (Fixkosten, Wiederkehrend, Tag) direkt setzen
- Kategorien umbenennen und löschen
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QVBoxLayout, QGridLayout,
    QLabel, QSpinBox, QComboBox, QLineEdit, QCheckBox, QPushButton,
    QMessageBox, QGroupBox, QWidget, QToolButton, QMenu, QInputDialog,
    QDialogButtonBox, QFrame
)
from PySide6.QtGui import QIcon

from model.category_model import CategoryModel, Category

MONTHS = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]


def parse_amount(text: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    s = s.replace("CHF", "").strip()
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
    # NEU: Kategorie-Erstellungsdaten
    category_created: bool = False
    parent_category_id: int | None = None


class NewCategoryDialog(QDialog):
    """Dialog zum Erstellen einer neuen Kategorie."""
    
    def __init__(self, parent=None, *, typ: str, category_name: str, 
                 cat_model: CategoryModel, existing_categories: list[Category]):
        super().__init__(parent)
        self.setWindowTitle("Neue Kategorie erstellen")
        self.setModal(True)
        self.setMinimumWidth(450)
        
        self.cat_model = cat_model
        self.typ = typ
        self.existing_categories = existing_categories
        self._created_id: int | None = None
        
        # === Haupt-Layout ===
        layout = QVBoxLayout(self)
        
        # Info-Label
        info = QLabel(f"Die Kategorie <b>'{category_name}'</b> existiert noch nicht.")
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
        
        self.chk_fix = QCheckBox("Fixkosten")
        self.chk_fix.setToolTip("Diese Kategorie enthält feste monatliche Ausgaben")
        flags_layout.addWidget(self.chk_fix, 0, 0)
        
        self.chk_recurring = QCheckBox("Wiederkehrend")
        self.chk_recurring.setToolTip("Diese Kategorie hat regelmäßige Buchungen")
        flags_layout.addWidget(self.chk_recurring, 0, 1)
        
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("Fälligkeitstag:"))
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
        
        self.btn_cancel = QPushButton("Abbrechen")
        btn_layout.addWidget(self.btn_cancel)
        
        layout.addLayout(btn_layout)
        
        # Signale
        self.btn_create.clicked.connect(self._create_category)
        self.btn_cancel.clicked.connect(self.reject)
    
    def _create_category(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Fehler", "Bitte einen Namen eingeben.")
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
            QMessageBox.critical(self, "Fehler", f"Konnte Kategorie nicht erstellen:\n{e}")
    
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
        self.category_combo.setPlaceholderText("Kategorie eingeben oder auswählen...")
        # Autofilter/Completer deaktivieren - nur manuelle Auswahl
        self.category_combo.setCompleter(None)
        layout.addWidget(self.category_combo, 1)
        
        # Management-Button mit Menü
        self.btn_manage = QToolButton()
        self.btn_manage.setText("⚙")
        self.btn_manage.setToolTip("Kategorie-Optionen")
        self.btn_manage.setPopupMode(QToolButton.InstantPopup)
        
        menu = QMenu(self.btn_manage)
        self.act_new = menu.addAction("➕ Neue Kategorie erstellen...")
        self.act_new_sub = menu.addAction("📂 Neue Unterkategorie...")
        menu.addSeparator()
        self.act_rename = menu.addAction("✏️ Umbenennen...")
        self.act_delete = menu.addAction("🗑️ Löschen...")
        menu.addSeparator()
        self.act_toggle_fix = menu.addAction("Fixkosten umschalten")
        self.act_toggle_rec = menu.addAction("Wiederkehrend umschalten")
        self.act_set_day = menu.addAction("Fälligkeitstag setzen...")
        
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
            QMessageBox.critical(self, "Fehler", f"Konnte Kategorie nicht erstellen:\n{e}")
    
    def _new_subcategory(self) -> None:
        """Erstellt eine neue Unterkategorie."""
        parent_cat = self._get_selected_category()
        
        # Parent-Auswahl Dialog
        cats = self.cat_model.list(self.typ)
        if not cats:
            QMessageBox.information(
                self, "Hinweis", 
                "Es gibt noch keine Kategorien. Bitte erst eine Hauptkategorie erstellen."
            )
            return
        
        # Auswahl der Parent-Kategorie
        items = [cat.name for cat in cats]
        default_idx = 0
        if parent_cat:
            try:
                default_idx = items.index(parent_cat.name)
            except ValueError:
                pass
        
        parent_name, ok = QInputDialog.getItem(
            self, "Parent-Kategorie",
            "Unter welcher Kategorie soll die neue erstellt werden?",
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
            self, "Neue Unterkategorie",
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
            QMessageBox.critical(self, "Fehler", f"Konnte Unterkategorie nicht erstellen:\n{e}")
    
    def _rename_category(self) -> None:
        """Benennt die ausgewählte Kategorie um."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Kategorie auswählen.")
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
            QMessageBox.critical(self, "Fehler", f"Umbenennen fehlgeschlagen:\n{e}")
    
    def _delete_category(self) -> None:
        """Löscht die ausgewählte Kategorie."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Kategorie auswählen.")
            return
        
        # Prüfen ob Unterkategorien vorhanden
        all_cats = self.cat_model.list(self.typ)
        has_children = any(c.parent_id == cat.id for c in all_cats)
        
        msg = f"Kategorie '{cat.name}' wirklich löschen?"
        if has_children:
            msg += "\n\n⚠️ WARNUNG: Diese Kategorie hat Unterkategorien, die ebenfalls gelöscht werden!"
        
        if QMessageBox.question(self, "Löschen bestätigen", msg) != QMessageBox.Yes:
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
            QMessageBox.critical(self, "Fehler", f"Löschen fehlgeschlagen:\n{e}")
    
    def _toggle_fix(self) -> None:
        """Fixkosten-Flag umschalten."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Kategorie auswählen.")
            return
        
        try:
            self.cat_model.update_flags(cat.id, is_fix=not cat.is_fix)
            status = "aktiviert" if not cat.is_fix else "deaktiviert"
            QMessageBox.information(self, "OK", f"Fixkosten für '{cat.name}' {status}.")
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Änderung fehlgeschlagen:\n{e}")
    
    def _toggle_recurring(self) -> None:
        """Wiederkehrend-Flag umschalten."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Kategorie auswählen.")
            return
        
        try:
            self.cat_model.update_flags(cat.id, is_recurring=not cat.is_recurring)
            status = "aktiviert" if not cat.is_recurring else "deaktiviert"
            QMessageBox.information(self, "OK", f"Wiederkehrend für '{cat.name}' {status}.")
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Änderung fehlgeschlagen:\n{e}")
    
    def _set_day(self) -> None:
        """Fälligkeitstag setzen."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Kategorie auswählen.")
            return
        
        day, ok = QInputDialog.getInt(
            self, "Fälligkeitstag",
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
            QMessageBox.critical(self, "Fehler", f"Änderung fehlgeschlagen:\n{e}")
    
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
            "Kategorie nicht gefunden",
            f"Die Kategorie '{name}' existiert noch nicht.\n\n"
            "Möchtest du sie jetzt erstellen?",
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
        self.setWindowTitle("Budget erfassen / bearbeiten")
        self.setModal(True)
        self.setMinimumWidth(500)
        
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        
        # === Jahr und Typ ===
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(default_year)
        
        self.typ = QComboBox()
        self.typ.addItems(["Ausgaben", "Einkommen", "Ersparnisse"])
        self.typ.setCurrentText(default_typ)
        
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
        self.month.addItems(MONTHS)
        
        self.from_month = QComboBox()
        self.from_month.addItems(MONTHS)
        
        self.to_month = QComboBox()
        self.to_month.addItems(MONTHS)
        
        self.only_if_empty = QCheckBox("Nur überschreiben, wenn Zelle leer ist")
        self.only_if_empty.setChecked(False)
        
        # === Buttons ===
        self.btn_ok = QPushButton("Übernehmen")
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton("Abbrechen")
        
        # === Layout ===
        form = QFormLayout()
        form.addRow("Jahr:", self.year)
        form.addRow("Typ:", self.typ)
        form.addRow("Kategorie:", self.category_widget)
        form.addRow("Betrag (CHF):", self.amount)
        
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
        self.typ.currentTextChanged.connect(self._typ_changed)
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
            QMessageBox.warning(self, "Fehlt", "Bitte Kategorie auswählen/eingeben.")
            return
        
        try:
            amt = parse_amount(self.amount.text())
        except Exception:
            QMessageBox.warning(self, "Fehler", "Betrag ist ungültig.")
            return
        
        # Ausgaben: negative Zahlen verhindern
        if self.typ.currentText() == "Ausgaben" and amt < 0:
            QMessageBox.warning(
                self, "Nicht erlaubt", 
                "Bei Ausgaben sind negative Beträge nicht erlaubt."
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
            typ=str(self.typ.currentText()),
            category=str(self.category_widget.get_category()),
            amount=float(amt),
            mode=str(mode),
            month=int(month),
            from_month=int(fm),
            to_month=int(tm),
            only_if_empty=bool(self.only_if_empty.isChecked()),
        )
