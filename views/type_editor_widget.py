from __future__ import annotations

import sqlite3
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QTableWidget, QTableWidgetItem,
    QPushButton, QAbstractItemView, QMessageBox, QComboBox, QInputDialog,
    QColorDialog
)

from model.account_type_model import AccountTypeModel


KIND_LABELS = {
    "expense": "Ausgabe",
    "income": "Einkommen",
    "savings": "Ersparnis",
}

LABEL_TO_KIND = {v: k for k, v in KIND_LABELS.items()}


class TypeEditorWidget(QWidget):
    """Editor für Konti/Typen.

    - Neue Typen hinzufügen (inkl. Art: Ausgabe/Einkommen/Ersparnis)
    - Umbenennen (Cascade in Kategorien/Budget/Tracking)
    - Löschen (nur wenn nicht genutzt und nicht gesperrt)
    - Farbe (für spätere Visualisierung)

    Der Widget feuert bei Änderungen ein Signal via callback, damit Tabs ihre
    Typ-Comboboxen neu laden können.
    """

    COL_NAME = 0
    COL_KIND = 1
    COL_COLOR = 2

    ROLE_ID = int(Qt.UserRole)
    ROLE_LOCKED = int(Qt.UserRole) + 1
    ROLE_OLD_NAME = int(Qt.UserRole) + 2

    def __init__(self, conn: sqlite3.Connection, *, on_changed=None, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.model = AccountTypeModel(conn)
        self.on_changed = on_changed
        self._loading = False

        title = QLabel("Typen / Konti")
        title.setStyleSheet("font-weight: bold;")

        self.btn_add = QPushButton("+ Neu")
        self.btn_rename = QPushButton("Umbenennen")
        self.btn_del = QPushButton("Entfernen")

        btns = QHBoxLayout()
        btns.addWidget(self.btn_add)
        btns.addWidget(self.btn_rename)
        btns.addWidget(self.btn_del)
        btns.addStretch(1)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Name", "Art", "Farbe"])

        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.DoubleClicked)
        self.table.setAlternatingRowColors(True)

        hint = QLabel(
            "Hinweis: Löschen geht nur, wenn der Typ nicht in Kategorien/Budget/Tracking verwendet wird."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray; font-size: 10px;")

        layout = QVBoxLayout()
        layout.addWidget(title)
        layout.addLayout(btns)
        layout.addWidget(self.table, 1)
        layout.addWidget(hint)
        self.setLayout(layout)

        self.btn_add.clicked.connect(self.add_type)
        self.btn_rename.clicked.connect(self.rename_type)
        self.btn_del.clicked.connect(self.delete_type)

        self.refresh()

    def _emit_changed(self):
        if callable(self.on_changed):
            try:
                self.on_changed()
            except Exception:
                pass

    def refresh(self):
        self._loading = True
        try:
            self.table.setRowCount(0)
            for t in self.model.list():
                r = self.table.rowCount()
                self.table.insertRow(r)

                it_name = QTableWidgetItem(t.name)
                it_name.setData(self.ROLE_ID, t.id)
                it_name.setData(self.ROLE_LOCKED, bool(t.is_locked))
                it_name.setData(self.ROLE_OLD_NAME, t.name)
                flags = Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEnabled
                # Umbenennen nur über Button (safer)
                it_name.setFlags(flags)
                self.table.setItem(r, self.COL_NAME, it_name)

                cmb_kind = QComboBox()
                cmb_kind.addItems(["Ausgabe", "Einkommen", "Ersparnis"])
                # current
                lbl = KIND_LABELS.get(t.kind, "Ausgabe")
                cmb_kind.setCurrentText(lbl)
                cmb_kind.currentTextChanged.connect(lambda _=None, row=r: self._on_kind_changed(row))
                self.table.setCellWidget(r, self.COL_KIND, cmb_kind)

                btn_color = QPushButton(" ")
                btn_color.setToolTip("Farbe wählen")
                btn_color.setFixedWidth(46)
                col = t.color or ""
                if col:
                    btn_color.setStyleSheet(f"background-color: {col};")
                btn_color.clicked.connect(lambda _=None, row=r: self._pick_color(row))
                self.table.setCellWidget(r, self.COL_COLOR, btn_color)

            self.table.resizeColumnsToContents()
        finally:
            self._loading = False

    def _selected_row(self) -> Optional[int]:
        sel = self.table.selectionModel().selectedRows()
        if not sel:
            return None
        return int(sel[0].row())

    def add_type(self):
        name, ok = QInputDialog.getText(self, "Neuer Typ", "Name des Typs:")
        if not ok:
            return
        name = (name or "").strip()
        if not name:
            return

        kind_label, ok2 = QInputDialog.getItem(
            self,
            "Art",
            "Welche Art ist dieser Typ?",
            ["Ausgabe", "Einkommen", "Ersparnis"],
            0,
            False,
        )
        if not ok2:
            return
        kind = LABEL_TO_KIND.get(kind_label, "expense")

        try:
            self.model.create(name, kind, "")
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Schon vorhanden", "Diesen Typ gibt es bereits.")
            return
        except Exception as e:
            QMessageBox.warning(self, "Fehler", str(e))
            return

        self.refresh()
        self._emit_changed()

    def rename_type(self):
        r = self._selected_row()
        if r is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst einen Typ auswählen.")
            return
        it = self.table.item(r, self.COL_NAME)
        if not it:
            return
        old = (it.data(self.ROLE_OLD_NAME) or it.text() or "").strip()
        new, ok = QInputDialog.getText(self, "Umbenennen", "Neuer Name:", text=old)
        if not ok:
            return
        new = (new or "").strip()
        if not new or new == old:
            return
        try:
            self.model.rename_and_cascade(old, new)
        except sqlite3.IntegrityError:
            QMessageBox.warning(self, "Konflikt", "Ein Typ mit diesem Namen existiert bereits.")
            return
        except Exception as e:
            QMessageBox.warning(self, "Fehler", str(e))
            return
        self.refresh()
        self._emit_changed()

    def delete_type(self):
        r = self._selected_row()
        if r is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst einen Typ auswählen.")
            return
        it = self.table.item(r, self.COL_NAME)
        if not it:
            return
        name = (it.text() or "").strip()
        locked = bool(it.data(self.ROLE_LOCKED))
        if locked:
            QMessageBox.warning(self, "Gesperrt", "Dieser Typ kann nicht gelöscht werden (mind. 3 Typen bleiben immer).")
            return

        if QMessageBox.question(self, "Löschen", f"Typ '{name}' wirklich löschen?", QMessageBox.Yes | QMessageBox.No) != QMessageBox.Yes:
            return
        try:
            self.model.delete(name)
        except Exception as e:
            QMessageBox.warning(self, "Nicht möglich", str(e))
            return
        self.refresh()
        self._emit_changed()

    def _on_kind_changed(self, row: int):
        if self._loading:
            return
        it = self.table.item(row, self.COL_NAME)
        if not it:
            return
        type_id = int(it.data(self.ROLE_ID) or 0)
        cmb = self.table.cellWidget(row, self.COL_KIND)
        if not isinstance(cmb, QComboBox):
            return
        kind = LABEL_TO_KIND.get(cmb.currentText(), "expense")
        try:
            self.model.update(type_id, kind=kind)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", str(e))
            self.refresh()
            return
        self._emit_changed()

    def _pick_color(self, row: int):
        it = self.table.item(row, self.COL_NAME)
        if not it:
            return
        type_id = int(it.data(self.ROLE_ID) or 0)
        btn = self.table.cellWidget(row, self.COL_COLOR)
        current = ""
        if isinstance(btn, QPushButton):
            # extract from style
            current = ""

        col = QColorDialog.getColor(QColor("#0078d4"), self, "Farbe wählen")
        if not col.isValid():
            return
        hexcol = col.name()
        try:
            self.model.update(type_id, color=hexcol)
        except Exception as e:
            QMessageBox.warning(self, "Fehler", str(e))
            return
        if isinstance(btn, QPushButton):
            btn.setStyleSheet(f"background-color: {hexcol};")
        self._emit_changed()
