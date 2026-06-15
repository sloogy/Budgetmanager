from __future__ import annotations
import logging
logger = logging.getLogger(__name__)
from dataclasses import dataclass
from datetime import date

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QPushButton, QDateEdit, QVBoxLayout
from utils.i18n import tr, trf, display_typ, db_typ_from_display

@dataclass(frozen=True)
class FixcostRequest:
    d: date

class FixcostDialog(QDialog):
    def __init__(self, parent=None, *, default_date: date):
        super().__init__(parent)
        self.setMinimumSize(500, 350)
        self.setWindowTitle(tr("dlg.recurring_manager"))
        self.setModal(True)

        self.ed_date = QDateEdit()
        self.ed_date.setCalendarPopup(True)
        self.ed_date.setDate(default_date)

        self.btn_ok = QPushButton(tr("btn.ok"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        form = QFormLayout()
        form.addRow(tr("lbl.month").rstrip(":"), self.ed_date)

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
