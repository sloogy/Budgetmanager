from __future__ import annotations

import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QComboBox,
    QTableWidget,
    QTableWidgetItem,
    QPushButton,
    QAbstractItemView,
    QMessageBox,
    QLabel,
)

from model.category_model import CategoryModel


class CategoriesTab(QWidget):
    """Kategorien-Verwaltung (Inline-Editing).

    Wunsch des Users:
    - Häkchen direkt in der Tabelle (Fixkosten / Wiederkehrend)
    - Werte direkt in der Tabelle editieren (Kategorie-Name / Tag)
    """

    COL_NAME = 0
    COL_FIX = 1
    COL_REC = 2
    COL_DAY = 3

    ROLE_ID = int(Qt.UserRole)
    ROLE_OLD_NAME = int(Qt.UserRole) + 1

    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn = conn
        self.model = CategoryModel(conn)
        self._loading = False

        self.typ_cb = QComboBox()
        self.typ_cb.addItems(["Alle", "Ausgaben", "Einkommen", "Ersparnisse"])

        self.btn_add = QPushButton("Neue Kategorie")
        self.btn_del = QPushButton("Entfernen")
        self.btn_bulk_edit = QPushButton("Mehrfach bearbeiten...")

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Kategorie", "Fixkosten", "Wiederkehrend", "Tag"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)  # Mehrfachauswahl
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.SelectedClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
        )

        top = QHBoxLayout()
        top.addWidget(QLabel("Typ"))
        top.addWidget(self.typ_cb)
        top.addStretch(1)
        top.addWidget(QLabel("Tipp: Doppelklick zum Bearbeiten, Klick auf Häkchen zum Umschalten"))
        top.addStretch(1)
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_del)
        top.addWidget(self.btn_bulk_edit)

        root = QVBoxLayout()
        root.addLayout(top)
        root.addWidget(self.table)
        self.setLayout(root)

        self.typ_cb.currentTextChanged.connect(lambda _: self.refresh(clear_selection=True))
        self.btn_add.clicked.connect(self.add_row)
        self.btn_del.clicked.connect(self.delete_selected)
        self.btn_bulk_edit.clicked.connect(self.bulk_edit_dialog)
        self.table.itemChanged.connect(self._on_item_changed)

        self.refresh(clear_selection=True)

    # -----------------
    # UI Helpers
    # -----------------
    def _mk_check_item(self, checked: bool, cat_id: int | None) -> QTableWidgetItem:
        it = QTableWidgetItem("")
        it.setFlags(
            Qt.ItemFlag.ItemIsEnabled
            | Qt.ItemFlag.ItemIsSelectable
            | Qt.ItemFlag.ItemIsUserCheckable
        )
        it.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        it.setData(self.ROLE_ID, cat_id)
        it.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
        return it

    def _mk_text_item(self, text: str, *, editable: bool, cat_id: int | None) -> QTableWidgetItem:
        it = QTableWidgetItem(text)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if editable:
            flags |= Qt.ItemFlag.ItemIsEditable
        it.setFlags(flags)
        it.setData(self.ROLE_ID, cat_id)
        return it

    def _set_loading(self, state: bool) -> None:
        self._loading = state

    def _safe_int_day(self, s: str, fallback: int = 1) -> int:
        try:
            v = int(str(s).strip())
        except Exception:
            return fallback
        return max(1, min(31, v))

    def _set_day_cell_enabled(self, row: int, enabled: bool, value: int | None = None) -> None:
        day_item = self.table.item(row, self.COL_DAY)
        if not day_item:
            return
        self._set_loading(True)
        try:
            if enabled:
                if value is not None:
                    day_item.setText(str(int(value)))
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable
                day_item.setFlags(flags)
            else:
                day_item.setText("")
                flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
                day_item.setFlags(flags)
        finally:
            self._set_loading(False)

    def _select_by_id(self, cat_id: int) -> None:
        for r in range(self.table.rowCount()):
            it = self.table.item(r, self.COL_NAME)
            if it and int(it.data(self.ROLE_ID) or 0) == int(cat_id):
                self.table.setCurrentCell(r, self.COL_NAME)
                return

    # -----------------
    # Public
    # -----------------
    def refresh(self, clear_selection: bool = False) -> None:
        typ = self.typ_cb.currentText()
        
        # Wenn "Alle" gewählt: alle Typen laden
        if typ == "Alle":
            types = ["Ausgaben", "Einkommen", "Ersparnisse"]
        else:
            types = [typ]

        self._set_loading(True)
        try:
            self.table.setRowCount(0)
            
            for t in types:
                rows = self.model.list(t)
                
                # Typ-Header einfügen wenn "Alle"
                if typ == "Alle" and rows:
                    r = self.table.rowCount()
                    self.table.insertRow(r)
                    header_item = QTableWidgetItem(f"═══ {t} ═══")
                    header_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                    font = header_item.font()
                    font.setBold(True)
                    header_item.setFont(font)
                    self.table.setItem(r, self.COL_NAME, header_item)
                    for col in range(1, 4):
                        empty = QTableWidgetItem("")
                        empty.setFlags(Qt.ItemFlag.ItemIsEnabled)
                        self.table.setItem(r, col, empty)
                
                for c in rows:
                    r = self.table.rowCount()
                    self.table.insertRow(r)

                    it_name = self._mk_text_item(c.name if typ != "Alle" else f"  {c.name}", editable=True, cat_id=c.id)
                    it_name.setData(self.ROLE_OLD_NAME, c.name)
                    it_name.setData(Qt.UserRole + 10, t)  # Typ speichern
                    self.table.setItem(r, self.COL_NAME, it_name)

                    fix_item = self._mk_check_item(bool(c.is_fix), c.id)
                    fix_item.setData(Qt.UserRole + 10, t)
                    self.table.setItem(r, self.COL_FIX, fix_item)
                    
                    rec_item = self._mk_check_item(bool(c.is_recurring), c.id)
                    rec_item.setData(Qt.UserRole + 10, t)
                    self.table.setItem(r, self.COL_REC, rec_item)

                    day_txt = str(int(c.recurring_day or 1)) if c.is_recurring else ""
                    it_day = self._mk_text_item(day_txt, editable=bool(c.is_recurring), cat_id=c.id)
                    it_day.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                    it_day.setData(Qt.UserRole + 10, t)
                    self.table.setItem(r, self.COL_DAY, it_day)

            self.table.resizeColumnsToContents()
        finally:
            self._set_loading(False)

        if clear_selection:
            self.table.clearSelection()

    def add_row(self) -> None:
        """Fügt eine neue, leere Zeile hinzu. Speichern passiert, sobald ein Name eingegeben wird."""
        r = self.table.rowCount()

        self._set_loading(True)
        try:
            self.table.insertRow(r)

            it_name = self._mk_text_item("", editable=True, cat_id=None)
            it_name.setData(self.ROLE_OLD_NAME, "")
            self.table.setItem(r, self.COL_NAME, it_name)

            self.table.setItem(r, self.COL_FIX, self._mk_check_item(False, None))
            self.table.setItem(r, self.COL_REC, self._mk_check_item(False, None))

            it_day = self._mk_text_item("", editable=False, cat_id=None)
            it_day.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            self.table.setItem(r, self.COL_DAY, it_day)
        finally:
            self._set_loading(False)

        self.table.setCurrentCell(r, self.COL_NAME)
        self.table.editItem(self.table.item(r, self.COL_NAME))

    def delete_selected(self) -> None:
        rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        if not rows:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst Kategorien auswählen.")
            return

        # Kategorien sammeln
        to_delete = []
        for row in rows:
            name_item = self.table.item(row, self.COL_NAME)
            if not name_item:
                continue
            cat_id = name_item.data(self.ROLE_ID)
            if not cat_id:  # Header oder ungespeicherte Zeile
                continue
            name = (name_item.text() if name_item else "").strip().lstrip()
            typ = name_item.data(Qt.UserRole + 10)
            to_delete.append((typ, name, cat_id, row))

        if not to_delete:
            # Nur Header oder leere Zeilen ausgewählt
            for row in rows:
                name_item = self.table.item(row, self.COL_NAME)
                if name_item and not name_item.data(self.ROLE_ID):
                    self.table.removeRow(row)
            return

        msg = f"Folgende {len(to_delete)} Kategorie(n) wirklich löschen?\n\n"
        msg += "\n".join([f"• {t} / {n}" for t, n, _, _ in to_delete[:10]])
        if len(to_delete) > 10:
            msg += f"\n... und {len(to_delete)-10} weitere"

        if QMessageBox.question(self, "Löschen", msg) != QMessageBox.Yes:
            return

        for typ, name, _, _ in to_delete:
            self.model.delete(typ, name)

        self.refresh(clear_selection=True)

    # -----------------
    # Inline Saving
    # -----------------
    def _on_item_changed(self, item: QTableWidgetItem) -> None:
        if self._loading:
            return

        row = item.row()
        col = item.column()
        typ = self.typ_cb.currentText()

        name_item = self.table.item(row, self.COL_NAME)
        if not name_item:
            return

        cat_id = name_item.data(self.ROLE_ID)

        # ---- Name geändert / neue Zeile speichern ----
        if col == self.COL_NAME:
            new_name = (name_item.text() or "").strip()
            old_name = (name_item.data(self.ROLE_OLD_NAME) or "").strip()

            if not new_name:
                # bestehende Kategorie darf nicht leer werden
                if cat_id:
                    self._set_loading(True)
                    try:
                        name_item.setText(old_name)
                    finally:
                        self._set_loading(False)
                    QMessageBox.warning(self, "Ungültig", "Der Kategoriename darf nicht leer sein.")
                return

            # neue Kategorie anlegen
            if not cat_id:
                fix_state = self.table.item(row, self.COL_FIX).checkState() == Qt.CheckState.Checked
                rec_state = self.table.item(row, self.COL_REC).checkState() == Qt.CheckState.Checked
                day_val = self._safe_int_day(self.table.item(row, self.COL_DAY).text(), 1) if rec_state else 1

                try:
                    new_id = self.model.create(typ, new_name, fix_state, rec_state, day_val)
                except sqlite3.IntegrityError:
                    QMessageBox.warning(self, "Schon vorhanden", f"Die Kategorie '{new_name}' existiert bereits.")
                    self._set_loading(True)
                    try:
                        name_item.setText("")
                    finally:
                        self._set_loading(False)
                    return

                # ID in alle Zellen dieser Zeile schreiben
                self._set_loading(True)
                try:
                    for c in range(4):
                        it = self.table.item(row, c)
                        if it:
                            it.setData(self.ROLE_ID, int(new_id))
                    name_item.setData(self.ROLE_OLD_NAME, new_name)
                finally:
                    self._set_loading(False)

                # Tag-Feld UI passend setzen
                self._set_day_cell_enabled(row, rec_state, day_val if rec_state else None)
                return

            # bestehende Kategorie umbenennen
            if new_name != old_name:
                try:
                    self.model.rename_and_cascade(int(cat_id), typ=typ, old_name=old_name, new_name=new_name)
                except sqlite3.IntegrityError:
                    QMessageBox.warning(self, "Konflikt", f"Die Kategorie '{new_name}' existiert bereits.")
                    self._set_loading(True)
                    try:
                        name_item.setText(old_name)
                    finally:
                        self._set_loading(False)
                    return

                # zur Sicherheit neu laden (Sortierung/Dropdowns)
                self.refresh(clear_selection=False)
                self._select_by_id(int(cat_id))
            return

        # Ohne ID noch nichts in DB schreiben (wird beim Name-Speichern erledigt)
        if not cat_id:
            # UI bei Rec-Umschalter trotzdem anpassen
            if col == self.COL_REC:
                rec_state = item.checkState() == Qt.CheckState.Checked
                self._set_day_cell_enabled(row, rec_state, 1 if rec_state else None)
            return

        # ---- Fixkosten ----
        if col == self.COL_FIX:
            is_fix = item.checkState() == Qt.CheckState.Checked
            self.model.update_flags(int(cat_id), is_fix=is_fix)
            return

        # ---- Wiederkehrend ----
        if col == self.COL_REC:
            is_rec = item.checkState() == Qt.CheckState.Checked
            if is_rec:
                day_item = self.table.item(row, self.COL_DAY)
                day_val = self._safe_int_day(day_item.text() if day_item else "", 1)
                self._set_day_cell_enabled(row, True, day_val)
                self.model.update_flags(int(cat_id), is_recurring=True, recurring_day=day_val)
            else:
                self._set_day_cell_enabled(row, False)
                self.model.update_flags(int(cat_id), is_recurring=False)
            return

        # ---- Tag ----
        if col == self.COL_DAY:
            # nur wenn Wiederkehrend aktiv
            rec_state = self.table.item(row, self.COL_REC).checkState() == Qt.CheckState.Checked
            if not rec_state:
                return
            day_val = self._safe_int_day(item.text(), 1)
            # clamp sichtbar machen
            if (item.text() or "").strip() != str(day_val):
                self._set_loading(True)
                try:
                    item.setText(str(day_val))
                finally:
                    self._set_loading(False)
            self.model.update_flags(int(cat_id), recurring_day=day_val)
            return

    def bulk_edit_dialog(self) -> None:
        """Dialog zum Bearbeiten mehrerer Kategorien gleichzeitig"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QCheckBox, QSpinBox, QDialogButtonBox
        
        rows = sorted(set(item.row() for item in self.table.selectedItems()))
        if not rows:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst Kategorien auswählen.")
            return

        # Kategorien sammeln
        categories = []
        for row in rows:
            name_item = self.table.item(row, self.COL_NAME)
            if not name_item:
                continue
            cat_id = name_item.data(self.ROLE_ID)
            if not cat_id:  # Header oder ungespeicherte Zeile
                continue
            typ = name_item.data(Qt.UserRole + 10)
            name = name_item.text().strip().lstrip()
            categories.append((cat_id, typ, name))

        if not categories:
            QMessageBox.information(self, "Hinweis", "Keine gültigen Kategorien ausgewählt.")
            return

        # Dialog erstellen
        dlg = QDialog(self)
        dlg.setWindowTitle(f"Mehrfachbearbeitung ({len(categories)} Kategorien)")
        dlg.setModal(True)

        layout = QVBoxLayout()
        
        # Info
        info_label = QLabel(f"Änderungen werden auf {len(categories)} Kategorie(n) angewendet:")
        layout.addWidget(info_label)
        
        # Liste der Kategorien
        cat_list = QLabel("\n".join([f"• {t} / {n}" for _, t, n in categories[:10]]))
        if len(categories) > 10:
            cat_list.setText(cat_list.text() + f"\n... und {len(categories)-10} weitere")
        layout.addWidget(cat_list)
        
        layout.addSpacing(20)
        
        # Optionen
        chk_set_fix = QCheckBox("Fixkosten setzen")
        layout.addWidget(chk_set_fix)
        
        chk_set_rec = QCheckBox("Wiederkehrend setzen")
        layout.addWidget(chk_set_rec)
        
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel("Tag:"))
        day_spin = QSpinBox()
        day_spin.setRange(1, 31)
        day_spin.setValue(1)
        day_spin.setEnabled(False)
        day_layout.addWidget(day_spin)
        day_layout.addStretch()
        layout.addLayout(day_layout)
        
        chk_set_rec.toggled.connect(lambda checked: day_spin.setEnabled(checked))
        
        layout.addSpacing(20)
        
        # Buttons
        btn_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btn_box.accepted.connect(dlg.accept)
        btn_box.rejected.connect(dlg.reject)
        layout.addWidget(btn_box)
        
        dlg.setLayout(layout)
        
        if dlg.exec() != QDialog.Accepted:
            return
        
        # Änderungen anwenden
        for cat_id, typ, name in categories:
            if chk_set_fix.isChecked():
                self.model.update_flags(int(cat_id), is_fix=True)
            if chk_set_rec.isChecked():
                self.model.update_flags(int(cat_id), is_recurring=True, recurring_day=day_spin.value())
        
        self.refresh(clear_selection=False)
        QMessageBox.information(self, "Erfolg", f"{len(categories)} Kategorien wurden aktualisiert.")
