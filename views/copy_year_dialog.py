from __future__ import annotations

from dataclasses import dataclass
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QPushButton, QSpinBox, QCheckBox, QComboBox, QVBoxLayout
)

@dataclass(frozen=True)
class CopyYearRequest:
    src_year: int
    dst_year: int
    carry_amounts: bool
    scope_typ: str  # "Alle", "Ausgaben", "Einkommen", "Ersparnisse"

class CopyYearDialog(QDialog):
    def __init__(self, parent=None, *, default_src: int, known_years: list[int] | None = None):
        super().__init__(parent)
        self.setWindowTitle("Budget-Jahr kopieren")
        self.setModal(True)

        self.src = QSpinBox()
        self.src.setRange(2000, 2100)
        self.src.setValue(default_src)

        self.dst = QSpinBox()
        self.dst.setRange(2000, 2100)
        self.dst.setValue(default_src + 1)

        self.scope = QComboBox()
        self.scope.addItems(["Alle", "Ausgaben", "Einkommen", "Ersparnisse"])

        self.carry = QCheckBox("Beträge übernehmen")
        self.carry.setChecked(True)

        self.btn_ok = QPushButton("Kopieren")
        self.btn_cancel = QPushButton("Abbrechen")

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
