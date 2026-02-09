from __future__ import annotations
from dataclasses import dataclass
from datetime import date

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QPushButton, QDateEdit, QVBoxLayout
from PySide6.QtCore import Qt

@dataclass(frozen=True)
class FixcostRequest:
    d: date

class FixcostDialog(QDialog):
    def __init__(self, parent=None, *, default_date: date):
        super().__init__(parent)
        self.setWindowTitle("Fixkosten / Wiederkehrende Buchungen")
        self.setModal(True)

        self.ed_date = QDateEdit()
        self.ed_date.setCalendarPopup(True)
        self.ed_date.setDate(default_date)

        self.btn_ok = QPushButton("Einfügen")
        self.btn_cancel = QPushButton("Abbrechen")

        form = QFormLayout()
        form.addRow("Monat", self.ed_date)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def get_request(self) -> FixcostRequest:
        return FixcostRequest(self.ed_date.date().toPython())
