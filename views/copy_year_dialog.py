from __future__ import annotations
import logging
logger = logging.getLogger(__name__)

from dataclasses import dataclass

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QPushButton, QSpinBox, QCheckBox, QComboBox, QVBoxLayout
)

from utils.i18n import tr, trf, display_typ, db_typ_from_display

@dataclass(frozen=True)
class CopyYearRequest:
    src_year: int
    dst_year: int
    carry_amounts: bool
    scope_typ: str  # "Alle", tr("kpi.expenses"), tr("kpi.income"), tr("typ.Ersparnisse")

class CopyYearDialog(QDialog):
    def __init__(self, parent=None, *, default_src: int, known_years: list[int] | None = None):
        super().__init__(parent)
        self.setMinimumSize(400, 250)
        self.setWindowTitle(tr("dlg.copy_year"))
        self.setModal(True)

        self.src = QSpinBox()
        self.src.setRange(2000, 2100)
        self.src.setValue(default_src)

        self.dst = QSpinBox()
        self.dst.setRange(2000, 2100)
        self.dst.setValue(default_src + 1)

        self.scope = QComboBox()
        self.scope.addItems(["Alle", tr("kpi.expenses"), tr("kpi.income"), tr("typ.Ersparnisse")])

        self.carry = QCheckBox(tr("chk.copy_amounts"))
        self.carry.setChecked(True)

        self.btn_ok = QPushButton(tr("btn.copy"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))
        
        # Stelle sicher, dass der OK-Button als Standard-Button funktioniert
        self.btn_ok.setDefault(True)
        self.btn_cancel.setDefault(False)

        form = QFormLayout()
        form.addRow("Quelljahr", self.src)
        form.addRow("Zieljahr", self.dst)
        form.addRow("Bereich", self.scope)
        form.addRow("", self.carry)

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

    def get_request(self) -> CopyYearRequest:
        return CopyYearRequest(
            src_year=int(self.src.value()),
            dst_year=int(self.dst.value()),
            carry_amounts=bool(self.carry.isChecked()),
            scope_typ=str(self.scope.currentText()),
        )
