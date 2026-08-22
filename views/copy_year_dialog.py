from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from model.category_forecast_mode import FORECAST_MODE_INCREMENTAL, FORECAST_MODE_POT
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from model.year_copy_rules import YearCopyOverride, list_year_copy_review_rows
from utils.i18n import display_typ, tr
from utils.money import format_money

logger = logging.getLogger(__name__)


def _localized_flags(row) -> str:
    parts: list[str] = []
    if row.is_fix:
        parts.append(tr("copy.flag_fix"))
    if row.is_recurring:
        parts.append(tr("copy.flag_recurring"))
    if row.forecast_mode == FORECAST_MODE_POT:
        parts.append(tr("forecast.mode.pot"))
    elif row.forecast_mode == FORECAST_MODE_INCREMENTAL:
        parts.append(tr("forecast.mode.incremental"))
    return ", ".join(parts) if parts else tr("forecast.mode.normal")


@dataclass(frozen=True)
class CopyYearRequest:
    src_year: int
    dst_year: int
    carry_amounts: bool
    scope_typ: str  # DB type; empty string = all
    use_previous_year_pattern: bool = False
    review_overrides: tuple[YearCopyOverride, ...] = ()


class CopyYearDialog(QDialog):
    def __init__(
        self,
        parent=None,
        *,
        default_src: int,
        known_years: list[int] | None = None,
        conn: sqlite3.Connection | None = None,
    ):
        super().__init__(parent)
        self.conn = conn
        self._review_rows = []
        self.setMinimumSize(760, 520)
        self.setWindowTitle(tr("dlg.copy_year"))
        self.setModal(True)

        self.src = QSpinBox()
        self.src.setRange(2000, 2100)
        self.src.setValue(default_src)

        self.dst = QSpinBox()
        self.dst.setRange(2000, 2100)
        self.dst.setValue(default_src + 1)

        self.scope = QComboBox()
        self.scope.addItem(tr("typ.Alle"), "")
        self.scope.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.scope.addItem(tr("kpi.income"), TYP_INCOME)
        self.scope.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)

        self.carry = QCheckBox(tr("chk.copy_amounts"))
        self.carry.setChecked(True)

        self.use_pattern = QCheckBox(tr("copy.use_previous_pattern"))
        self.use_pattern.setToolTip(tr("copy.use_previous_pattern_tip"))
        self.use_pattern.setChecked(True)
        self.use_pattern.setEnabled(conn is not None)

        info = QLabel(tr("copy.review_info"))
        info.setWordWrap(True)

        self.review = QTableWidget()
        self.review.setColumnCount(7)
        self.review.setHorizontalHeaderLabels(
            [
                tr("copy.include"),
                tr("lbl.type"),
                tr("header.designation"),
                tr("copy.flags"),
                tr("copy.src_budget_total"),
                tr("copy.src_actual_total"),
                tr("copy.dst_annual_amount"),
            ]
        )
        self.review.setAlternatingRowColors(True)
        self.review.verticalHeader().setVisible(False)
        self.review.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.review.horizontalHeader().setSectionResizeMode(
            6, QHeaderView.ResizeToContents
        )

        self.btn_ok = QPushButton(tr("btn.copy"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        self.btn_ok.setDefault(True)
        self.btn_cancel.setDefault(False)

        form = QFormLayout()
        form.addRow(tr("copy.src_year"), self.src)
        form.addRow(tr("copy.dst_year"), self.dst)
        form.addRow(tr("copy.scope"), self.scope)
        form.addRow("", self.carry)
        form.addRow("", self.use_pattern)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        self.learning_info = QLabel("")
        self.learning_info.setWordWrap(True)
        self.learning_info.setVisible(False)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addWidget(info)
        root.addWidget(self.review)
        root.addWidget(self.learning_info)
        root.addLayout(btns)
        self.setLayout(root)

        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)
        self.src.valueChanged.connect(self._refresh_review)
        self.scope.currentIndexChanged.connect(self._refresh_review)
        self._refresh_review()

    def _refresh_review(self) -> None:
        self.review.setRowCount(0)
        self._review_rows = []
        if self.conn is None:
            return
        typ = str(self.scope.currentData() or "") or None
        try:
            self._review_rows = list_year_copy_review_rows(
                self.conn, int(self.src.value()), typ=typ
            )
        except Exception as exc:
            logger.warning(
                "Jahreswechsel-Prüfliste konnte nicht geladen werden: %s", exc
            )
            self._review_rows = []

        try:
            from model.budget_overview_model import BudgetOverviewModel

            learning = BudgetOverviewModel(self.conn).get_year_end_learning_suggestions(
                int(self.src.value()),
                types=([typ] if typ else None),
            )
            if learning:
                cats = ", ".join(s.category for s in learning[:8])
                if len(learning) > 8:
                    cats += " …"
                self.learning_info.setText(
                    tr("copy.learning_year_end_hint").format(
                        count=len(learning),
                        cats=cats,
                    )
                )
                self.learning_info.setVisible(True)
            else:
                self.learning_info.setVisible(False)
        except Exception as exc:
            logger.debug("Lernmodus-Jahresauswertung: %s", exc)
            self.learning_info.setVisible(False)

        self.review.setRowCount(len(self._review_rows))
        for row_idx, row in enumerate(self._review_rows):
            include = QTableWidgetItem("")
            include.setFlags(
                Qt.ItemIsUserCheckable | Qt.ItemIsEnabled | Qt.ItemIsSelectable
            )
            include.setCheckState(Qt.Checked)
            self.review.setItem(row_idx, 0, include)

            readonly_values = [
                display_typ(row.typ),
                row.category,
                _localized_flags(row),
                format_money(row.budget_total),
                format_money(row.actual_total),
            ]
            for col, value in enumerate(readonly_values, start=1):
                item = QTableWidgetItem(str(value))
                item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
                self.review.setItem(row_idx, col, item)

            amount = QDoubleSpinBox()
            amount.setRange(0.0, 9999999.0)
            amount.setDecimals(2)
            amount.setSingleStep(100.0)
            amount.setValue(float(row.budget_total or row.actual_total or 0.0))
            self.review.setCellWidget(row_idx, 6, amount)
        self.review.resizeColumnsToContents()

    def get_request(self) -> CopyYearRequest:
        overrides: list[YearCopyOverride] = []
        for row_idx, row in enumerate(self._review_rows):
            include_item = self.review.item(row_idx, 0)
            include = include_item.checkState() == Qt.Checked if include_item else True
            spin = self.review.cellWidget(row_idx, 6)
            annual = (
                float(spin.value())
                if isinstance(spin, QDoubleSpinBox)
                else row.budget_total
            )
            overrides.append(
                YearCopyOverride(
                    typ=row.typ,
                    category=row.category,
                    annual_amount=annual,
                    include=include,
                )
            )

        return CopyYearRequest(
            src_year=int(self.src.value()),
            dst_year=int(self.dst.value()),
            carry_amounts=bool(self.carry.isChecked()),
            scope_typ=str(self.scope.currentData() or ""),
            use_previous_year_pattern=bool(self.use_pattern.isChecked()),
            review_overrides=tuple(overrides),
        )
