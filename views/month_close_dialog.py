"""Monatsabschluss-Assistent (v2.2.0).

Führt in einem Fenster durch den Monatsabschluss:
1. Zusammenfassung: Einnahmen − Ausgaben − Ersparnisse = frei verfügbar.
2. Überschuss: auf Wunsch in eine Ersparnis-Kategorie buchen (Vorschlag:
   aktivstes Sparziel; Betrag und Ziel änderbar).
3. Defizit: auf Wunsch aus einer Ersparnis mit Guthaben decken; zusätzlich
   reine INFO, welche variablen Budgets im Folgemonat Spielraum bieten –
   Fixkosten/wiederkehrende Kategorien werden nie genannt.

Es wird nichts automatisch gebucht; jede Aktion braucht einen Klick.
"""
from __future__ import annotations

import logging
import sqlite3

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QDoubleSpinBox,
    QPushButton,
    QGroupBox,
    QMessageBox,
    QCheckBox,
)

from model.month_close_model import MonthCloseModel
from model.month_status import compute_month_status
from utils.i18n import tr, trf
from model.typ_constants import TYP_EXPENSES, TYP_SAVINGS
from utils.money import format_money
from views.ui_colors import ui_colors

logger = logging.getLogger(__name__)


class MonthCloseDialog(QDialog):
    """DAU-freundlicher Monatsabschluss – erklärt, schlägt vor, bucht nur auf Klick."""

    def __init__(self, conn: sqlite3.Connection, year: int, month: int, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.year = int(year)
        self.month = int(month)
        self.model = MonthCloseModel(conn)
        self._booked_something = False

        self.setWindowTitle(trf("month_close.title", month=tr(f"month.{self.month}"), year=self.year))
        self.setMinimumWidth(560)
        self.setToolTip(tr("help.month_close"))
        self._build_ui()
        self._reload()

    # ── UI ───────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        lay = QVBoxLayout(self)

        self.lbl_status = QLabel("")
        self.lbl_status.setStyleSheet("font-size: 16px; font-weight: 600;")
        lay.addWidget(self.lbl_status)

        # Zusammenfassung
        sum_box = QGroupBox(tr("month_close.summary"))
        sum_box.setToolTip(tr("help.month_close"))
        form = QFormLayout(sum_box)
        self.lbl_income = QLabel("–")
        self.lbl_expenses = QLabel("–")
        self.lbl_savings = QLabel("–")
        self.lbl_savings.setToolTip(tr("help.savings"))
        self.lbl_balance = QLabel("–")
        form.addRow(tr("kpi.income") + ":", self.lbl_income)
        form.addRow(tr("kpi.expenses") + ":", self.lbl_expenses)
        form.addRow(tr("kpi.savings") + ":", self.lbl_savings)
        bal_lbl = QLabel(tr("month_close.free_amount") + ":")
        bal_lbl.setToolTip(tr("month_close.free_amount_tip"))
        form.addRow(bal_lbl, self.lbl_balance)
        lay.addWidget(sum_box)

        # Überschuss-Sektion
        self.surplus_box = QGroupBox(tr("month_close.surplus_title"))
        s_lay = QVBoxLayout(self.surplus_box)
        self.lbl_surplus_info = QLabel("")
        self.lbl_surplus_info.setWordWrap(True)
        s_lay.addWidget(self.lbl_surplus_info)
        s_form = QFormLayout()
        self.cmb_surplus_target = QComboBox()
        self.cmb_surplus_target.setToolTip(tr("help.savings"))
        self.spn_surplus_amount = QDoubleSpinBox()
        self.spn_surplus_amount.setRange(0.01, 10_000_000.0)
        self.spn_surplus_amount.setDecimals(2)
        s_form.addRow(tr("month_close.surplus_target"), self.cmb_surplus_target)
        s_form.addRow(tr("month_close.amount"), self.spn_surplus_amount)
        s_lay.addLayout(s_form)
        self.btn_book_surplus = QPushButton(tr("month_close.book_surplus"))
        self.btn_book_surplus.clicked.connect(self._on_book_surplus)
        s_lay.addWidget(self.btn_book_surplus)
        lay.addWidget(self.surplus_box)

        # Defizit-Sektion
        self.deficit_box = QGroupBox(tr("month_close.deficit_title"))
        d_lay = QVBoxLayout(self.deficit_box)
        self.lbl_deficit_info = QLabel("")
        self.lbl_deficit_info.setWordWrap(True)
        d_lay.addWidget(self.lbl_deficit_info)
        d_form = QFormLayout()
        self.cmb_deficit_source = QComboBox()
        self.cmb_deficit_source.setToolTip(tr("month_close.deficit_source_tip"))
        self.spn_deficit_amount = QDoubleSpinBox()
        self.spn_deficit_amount.setRange(0.01, 10_000_000.0)
        self.spn_deficit_amount.setDecimals(2)
        d_form.addRow(tr("month_close.deficit_source"), self.cmb_deficit_source)
        d_form.addRow(tr("month_close.amount"), self.spn_deficit_amount)
        d_lay.addLayout(d_form)
        self.btn_cover_deficit = QPushButton(tr("month_close.cover_deficit"))
        self.btn_cover_deficit.clicked.connect(self._on_cover_deficit)
        d_lay.addWidget(self.btn_cover_deficit)
        self.lbl_reduction_hints = QLabel("")
        self.lbl_reduction_hints.setWordWrap(True)
        self.lbl_reduction_hints.setToolTip(tr("month_close.no_fix_cut_tip"))
        d_lay.addWidget(self.lbl_reduction_hints)
        lay.addWidget(self.deficit_box)

        # Abschluss
        bottom = QHBoxLayout()
        self.cb_mark_closed = QCheckBox(tr("month_close.mark_closed"))
        self.cb_mark_closed.setToolTip(tr("month_close.mark_closed_tip"))
        self.cb_mark_closed.setChecked(True)
        bottom.addWidget(self.cb_mark_closed)
        bottom.addStretch(1)
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self._on_close_clicked)
        bottom.addWidget(self.btn_close)
        lay.addLayout(bottom)

    # ── Daten ────────────────────────────────────────────────────
    def _reload(self) -> None:
        info = self.model.compute(self.year, self.month)
        self._info = info
        c = ui_colors(self)

        # Ampel + frei verfügbar
        try:
            from model.budget_overview_model import BudgetOverviewModel

            exp_budget = BudgetOverviewModel(self.conn).budget_sum(
                self.year, self.month, TYP_EXPENSES
            )
        except Exception:
            exp_budget = 0.0
        status = compute_month_status(
            info.income_actual, info.expense_actual, exp_budget, info.savings_actual
        )
        closed_suffix = f"  ({tr('month_close.already_closed')})" if info.already_closed else ""
        self.lbl_status.setText(f"{status.icon} {tr(status.text_key)}{closed_suffix}")

        self.lbl_income.setText(format_money(info.income_actual))
        self.lbl_expenses.setText(format_money(info.expense_actual))
        self.lbl_savings.setText(format_money(info.savings_actual))
        self.lbl_balance.setText(format_money(info.balance))
        self.lbl_balance.setStyleSheet(
            f"font-weight: 700; color: {c.amount_color(info.balance)};"
        )

        surplus = info.balance > 0.005
        deficit = info.balance < -0.005
        self.surplus_box.setVisible(surplus)
        self.deficit_box.setVisible(deficit)

        if surplus:
            self.lbl_surplus_info.setText(
                trf("month_close.surplus_info", amount=format_money(info.balance))
            )
            self.cmb_surplus_target.clear()
            rows = self.conn.execute(
                "SELECT name FROM categories WHERE typ = ? ORDER BY sort_order, name",
                (TYP_SAVINGS,),
            ).fetchall()
            for r in rows:
                self.cmb_surplus_target.addItem(str(r[0]), str(r[0]))
            if info.surplus_target:
                idx = self.cmb_surplus_target.findData(info.surplus_target)
                if idx >= 0:
                    self.cmb_surplus_target.setCurrentIndex(idx)
            self.spn_surplus_amount.setValue(round(info.balance, 2))

        if deficit:
            need = abs(info.balance)
            self.lbl_deficit_info.setText(
                trf("month_close.deficit_info", amount=format_money(need))
            )
            self.cmb_deficit_source.clear()
            for cat, saldo in info.savings_with_funds:
                self.cmb_deficit_source.addItem(
                    f"{cat} ({trf('month_close.available', amount=format_money(saldo))})", cat
                )
            self.spn_deficit_amount.setValue(round(need, 2))
            self.btn_cover_deficit.setEnabled(bool(info.savings_with_funds))
            if not info.savings_with_funds:
                self.lbl_deficit_info.setText(
                    self.lbl_deficit_info.text() + "\n" + tr("month_close.no_savings_available")
                )
            if info.reduction_hints:
                lines = [tr("month_close.reduction_intro")]
                for cat, budget, avg in info.reduction_hints:
                    lines.append(
                        trf(
                            "month_close.reduction_line",
                            cat=cat,
                            budget=format_money(budget),
                            avg=format_money(avg),
                        )
                    )
                lines.append(tr("month_close.no_fix_cut_tip"))
                self.lbl_reduction_hints.setText("\n".join(lines))
            else:
                self.lbl_reduction_hints.setText("")

        if not surplus and not deficit:
            self.lbl_status.setText(
                self.lbl_status.text() + "  –  " + tr("month_close.balanced")
            )

    # ── Aktionen ─────────────────────────────────────────────────
    def _on_book_surplus(self) -> None:
        cat = self.cmb_surplus_target.currentData() or self.cmb_surplus_target.currentText()
        amount = float(self.spn_surplus_amount.value())
        if not cat or amount <= 0:
            return
        details = trf("month_close.booking_details", month=tr(f"month.{self.month}"), year=self.year)
        try:
            self.model.book_surplus(self.year, self.month, amount, str(cat), details)
            self._booked_something = True
            QMessageBox.information(self, tr("month_close.title_short"), tr("month_close.booked_ok"))
            self._reload()
        except Exception as e:
            logger.warning("book_surplus: %s", e)
            QMessageBox.warning(self, tr("month_close.title_short"), str(e))

    def _on_cover_deficit(self) -> None:
        cat = self.cmb_deficit_source.currentData()
        amount = float(self.spn_deficit_amount.value())
        if not cat or amount <= 0:
            return
        details = trf("month_close.booking_details", month=tr(f"month.{self.month}"), year=self.year)
        try:
            self.model.cover_deficit_from_savings(self.year, self.month, amount, str(cat), details)
            self._booked_something = True
            QMessageBox.information(self, tr("month_close.title_short"), tr("month_close.booked_ok"))
            self._reload()
        except Exception as e:
            logger.warning("cover_deficit: %s", e)
            QMessageBox.warning(self, tr("month_close.title_short"), str(e))

    def _on_close_clicked(self) -> None:
        marked_closed = False
        if self.cb_mark_closed.isChecked():
            try:
                self.model.mark_closed(self.year, self.month)
                marked_closed = True
            except Exception as e:
                logger.debug("mark_closed: %s", e)
        self.accept() if (self._booked_something or marked_closed) else self.reject()
