from __future__ import annotations

import sqlite3
from datetime import date

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from model.income_specials import DEFAULT_13TH_SALARY_CATEGORY, ThirteenthSalaryPlan
from model.typ_constants import TYP_INCOME
from utils.i18n import tr, trf
from utils.money import format_money, get_symbol


def _month_names() -> list[str]:
    return [tr(f"month.{i}") for i in range(1, 13)]


class ThirteenthSalaryDialog(QDialog):
    """Kleiner Dialog für den 13. Monatslohn."""

    def __init__(
        self, parent=None, *, conn: sqlite3.Connection, default_year: int | None = None
    ):
        super().__init__(parent)
        self.conn = conn
        self.setWindowTitle(tr("income13.title"))
        self.setModal(True)
        self.setMinimumWidth(420)

        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(int(default_year or date.today().year))

        self.month = QComboBox()
        for idx, label in enumerate(_month_names(), start=1):
            self.month.addItem(label, idx)
        self.month.setCurrentIndex(10)  # November als Schweizer Default nahe Auszahlung

        self.amount = QDoubleSpinBox()
        self.amount.setRange(0.01, 999999.0)
        self.amount.setDecimals(2)
        self.amount.setSingleStep(100.0)
        self.amount.setSuffix(f" {get_symbol()}")

        self.category = QComboBox()
        self.category.setEditable(True)
        self._load_income_categories()

        info = QLabel(tr("income13.description"))
        info.setWordWrap(True)

        form = QFormLayout()
        form.addRow(tr("lbl.year"), self.year)
        form.addRow(tr("income13.payout_month"), self.month)
        form.addRow(tr("income13.amount"), self.amount)
        form.addRow(tr("income13.category"), self.category)

        self.btn_ok = QPushButton(tr("income13.apply"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))
        self.btn_ok.setDefault(True)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout(self)
        root.addWidget(info)
        root.addLayout(form)
        root.addLayout(btns)

    def _load_income_categories(self) -> None:
        cats = []
        try:
            rows = self.conn.execute(
                "SELECT name FROM categories WHERE typ=? ORDER BY name COLLATE NOCASE",
                (TYP_INCOME,),
            ).fetchall()
            cats = [str(r["name"]) for r in rows]
        except Exception:
            cats = []
        preferred = tr("income13.default_category")
        legacy = DEFAULT_13TH_SALARY_CATEGORY
        ordered = [preferred] + [c for c in cats if c not in {preferred, legacy}]
        if legacy != preferred and legacy in cats:
            ordered.append(legacy)
        for c in ordered:
            self.category.addItem(c)
        self.category.setCurrentText(preferred)

    def get_plan(self) -> ThirteenthSalaryPlan:
        return ThirteenthSalaryPlan(
            year=int(self.year.value()),
            payout_month=int(self.month.currentData() or 11),
            amount=float(self.amount.value()),
            category=str(
                self.category.currentText() or tr("income13.default_category")
            ).strip()
            or tr("income13.default_category"),
        )

    def success_text(self) -> str:
        plan = self.get_plan()
        return trf(
            "income13.done",
            amount=format_money(plan.amount),
            category=plan.category,
            month=self.month.currentText(),
            year=plan.year,
        )
