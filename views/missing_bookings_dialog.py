from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QAbstractItemView,
)


def _fmt_chf(amount: float) -> str:
    s = f"{amount:,.2f}"
    return s.replace(",", "X").replace(".", ".").replace("X", "'")


@dataclass(frozen=True)
class PendingBooking:
    d: date
    typ: str
    category: str
    amount: float
    details: str


class MissingBookingsDialog(QDialog):
    """Liste mit fehlenden Fixkosten/Wiederkehrenden Buchungen.

    User kann auswählen, was tatsächlich gebucht werden soll.
    """

    def __init__(self, parent=None, *, items: list[PendingBooking], title: str = "Fehlende Buchungen"):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        self._items = items

        self.lbl = QLabel(
            "Folgende Buchungen sind in diesem Monat noch nicht vorhanden. "
            "Wähle aus, was eingefügt werden soll:"
        )
        self.lbl.setWordWrap(True)

        self.table = QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["Buchen", "Datum", "Typ", "Kategorie", "CHF"])
        self.table.setAlternatingRowColors(True)
        # PySide6: Enums hängen an QAbstractItemView, nicht an der Instanz
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

        self.btn_all = QPushButton("Alle")
        self.btn_none = QPushButton("Keine")
        self.btn_ok = QPushButton("Buchen")
        self.btn_cancel = QPushButton("Abbrechen")

        top_btns = QHBoxLayout()
        top_btns.addWidget(self.btn_all)
        top_btns.addWidget(self.btn_none)
        top_btns.addStretch(1)
        top_btns.addWidget(self.btn_ok)
        top_btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addWidget(self.lbl)
        root.addWidget(self.table)
        root.addLayout(top_btns)
        self.setLayout(root)

        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._fill()

    def _fill(self):
        self.table.setRowCount(0)
        for it in self._items:
            r = self.table.rowCount()
            self.table.insertRow(r)

            chk = QTableWidgetItem("✓")
            chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
            chk.setCheckState(Qt.Checked)
            chk.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(r, 0, chk)

            self.table.setItem(r, 1, QTableWidgetItem(it.d.strftime("%d.%m.%Y")))
            self.table.setItem(r, 2, QTableWidgetItem(it.typ))
            self.table.setItem(r, 3, QTableWidgetItem(it.category))

            amt = QTableWidgetItem(_fmt_chf(float(it.amount)))
            amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(r, 4, amt)

        self.table.resizeColumnsToContents()

    def _set_all(self, checked: bool):
        state = Qt.Checked if checked else Qt.Unchecked
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it is not None:
                it.setCheckState(state)

    def selected_items(self) -> list[PendingBooking]:
        out: list[PendingBooking] = []
        for r, it in enumerate(self._items):
            chk = self.table.item(r, 0)
            if chk is not None and chk.checkState() == Qt.Checked:
                out.append(it)
        return out
