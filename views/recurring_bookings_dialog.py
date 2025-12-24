from __future__ import annotations

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

from views.missing_bookings_dialog import PendingBooking


def _fmt_chf(amount: float) -> str:
    s = f"{amount:,.2f}"
    return s.replace(",", "X").replace(".", ".").replace("X", "'")


def _parse_chf(text: str) -> float:
    s = (text or "").strip().replace("'", "").replace(" ", "")
    # allow comma as decimal
    s = s.replace(",", ".")
    try:
        return float(s)
    except Exception:
        return 0.0


class RecurringBookingsDialog(QDialog):
    """Dialog für Fixkosten + wiederkehrende (variable) Buchungen.

    - Fixkosten: Betrag nicht editierbar
    - Wiederkehrend (ohne Fixkosten): Betrag editierbar (Vorschlag = Budget)

    Buttons:
    - Nur Fixkosten: bucht nur Fixkosten
    - Buchen: bucht alle selektierten Positionen
    """

    def __init__(
        self,
        parent=None,
        *,
        fix_items: list[PendingBooking],
        recurring_items: list[PendingBooking],
        title: str = "Fixkosten & Wiederkehrende buchen",
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)

        self._fix = list(fix_items)
        self._rec = list(recurring_items)

        self.lbl = QLabel(
            "Fixkosten sind fix und nicht editierbar. \
Wiederkehrende (ohne Fixkosten) sind variabel: Betrag anpassen und auswählen, was gebucht werden soll."
        )
        self.lbl.setWordWrap(True)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Buchen",
            "Art",
            "Datum",
            "Typ",
            "Kategorie",
            "CHF",
            "Bemerkung",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

        # Buttons
        self.btn_all = QPushButton("Alle")
        self.btn_none = QPushButton("Keine")
        self.btn_fix_only = QPushButton("Nur Fixkosten")
        self.btn_ok = QPushButton("Buchen")
        self.btn_cancel = QPushButton("Abbrechen")

        row_btns = QHBoxLayout()
        row_btns.addWidget(self.btn_all)
        row_btns.addWidget(self.btn_none)
        row_btns.addStretch(1)
        row_btns.addWidget(self.btn_fix_only)
        row_btns.addWidget(self.btn_ok)
        row_btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addWidget(self.lbl)
        root.addWidget(self.table)
        root.addLayout(row_btns)
        self.setLayout(root)

        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_fix_only.clicked.connect(self._accept_fix_only)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._fill()

    def _fill(self) -> None:
        self.table.setRowCount(0)

        # Reihenfolge: Fixkosten zuerst, dann Wiederkehrend
        for it in self._fix:
            self._add_row(it, kind="Fix", editable_amount=False)
        for it in self._rec:
            self._add_row(it, kind="Wiederkehrend", editable_amount=True)

        self.table.resizeColumnsToContents()
        # Bemerkung etwas breiter
        self.table.setColumnWidth(6, max(self.table.columnWidth(6), 260))

    def _add_row(self, it: PendingBooking, *, kind: str, editable_amount: bool) -> None:
        r = self.table.rowCount()
        self.table.insertRow(r)

        chk = QTableWidgetItem("✓")
        chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        chk.setCheckState(Qt.Checked)
        chk.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, 0, chk)

        self.table.setItem(r, 1, QTableWidgetItem(kind))
        self.table.setItem(r, 2, QTableWidgetItem(it.d.strftime("%d.%m.%Y")))
        self.table.setItem(r, 3, QTableWidgetItem(it.typ))
        self.table.setItem(r, 4, QTableWidgetItem(it.category))

        amt = QTableWidgetItem(_fmt_chf(float(it.amount)))
        amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if editable_amount:
            amt.setFlags(amt.flags() | Qt.ItemIsEditable)
        else:
            amt.setFlags(amt.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(r, 5, amt)

        det = QTableWidgetItem(it.details or "")
        # Bemerkung darf der User optional anpassen
        det.setFlags(det.flags() | Qt.ItemIsEditable)
        self.table.setItem(r, 6, det)

    def _set_all(self, checked: bool) -> None:
        state = Qt.Checked if checked else Qt.Unchecked
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it is not None:
                it.setCheckState(state)

    def _accept_fix_only(self) -> None:
        """Uncheck alle wiederkehrenden (variablen) Zeilen und accept."""
        fix_rows = len(self._fix)
        for r in range(fix_rows, self.table.rowCount()):
            it = self.table.item(r, 0)
            if it is not None:
                it.setCheckState(Qt.Unchecked)
        self.accept()

    def selected_items(self) -> list[PendingBooking]:
        out: list[PendingBooking] = []

        # mapping: row -> PendingBooking Basisobjekt
        all_items: list[PendingBooking] = [*self._fix, *self._rec]
        for r, base in enumerate(all_items):
            chk = self.table.item(r, 0)
            if chk is None or chk.checkState() != Qt.Checked:
                continue

            # Amount/Details ggf. vom UI übernehmen
            amt_item = self.table.item(r, 5)
            det_item = self.table.item(r, 6)
            amt = _parse_chf(amt_item.text() if amt_item else "")
            det = det_item.text() if det_item else (base.details or "")

            out.append(
                PendingBooking(
                    d=base.d,
                    typ=base.typ,
                    category=base.category,
                    amount=float(amt),
                    details=str(det or ""),
                )
            )
        return out
