from __future__ import annotations

import csv
import logging
import sqlite3
from datetime import date, datetime
from pathlib import Path

from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
)

from model.budget_model import BudgetModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from utils.i18n import display_typ, tr, trf
from utils.icons import get_icon
from utils.notifications import show_info, show_warning

logger = logging.getLogger(__name__)


class ExportDialog(QDialog):
    """Export-Dialog für Daten (CSV, TXT, XLSX und PDF)."""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.budget = BudgetModel(conn)
        self.tracking = TrackingModel(conn)

        self.setWindowTitle(tr("dlg.export"))
        self.setMinimumWidth(500)

        layout = QVBoxLayout()

        # === FORMAT ===
        format_group = QGroupBox(
            tr("auto.views_export_dialog.37_export_format_46cddde9")
        )
        format_layout = QVBoxLayout()

        self.format_group = QButtonGroup(self)
        self.radio_csv = QRadioButton(tr("radio.export_csv"))
        self.radio_csv.setChecked(True)
        self.format_group.addButton(self.radio_csv, 0)
        format_layout.addWidget(self.radio_csv)

        self.radio_txt = QRadioButton(tr("radio.export_txt"))
        self.format_group.addButton(self.radio_txt, 1)
        format_layout.addWidget(self.radio_txt)

        self.radio_xlsx = QRadioButton(tr("radio.export_xlsx"))
        self.format_group.addButton(self.radio_xlsx, 2)
        format_layout.addWidget(self.radio_xlsx)

        self.radio_pdf = QRadioButton(tr("radio.export_pdf"))
        self.format_group.addButton(self.radio_pdf, 3)
        format_layout.addWidget(self.radio_pdf)

        format_group.setLayout(format_layout)
        layout.addWidget(format_group)

        # === DATENAUSWAHL ===
        data_group = QGroupBox(
            tr("auto.views_export_dialog.54_zu_exportierende_daten_263da15e")
        )
        data_layout = QVBoxLayout()

        self.chk_tracking = QCheckBox(
            tr("auto.views_export_dialog.57_tracking_daten_transaktionen_e754548e")
        )
        self.chk_tracking.setChecked(True)
        data_layout.addWidget(self.chk_tracking)

        self.chk_budget = QCheckBox(
            tr("auto.views_export_dialog.61_budget_daten_d0bbdcff")
        )
        self.chk_budget.setChecked(True)
        data_layout.addWidget(self.chk_budget)

        self.chk_categories = QCheckBox(tr("tab.categories"))
        data_layout.addWidget(self.chk_categories)

        data_group.setLayout(data_layout)
        layout.addWidget(data_group)

        # === ZEITRAUM ===
        period_group = QGroupBox(tr("auto.views_export_dialog.72_zeitraum_91c1e2b4"))
        period_layout = QVBoxLayout()

        year_row = QHBoxLayout()
        year_row.addWidget(QLabel(tr("lbl.year")))
        self.year_combo = QComboBox()
        self.year_combo.addItem(tr("lbl.all_years"), None)
        years = sorted(set(self.budget.years()) | set(self.tracking.years()))
        for y in years:
            self.year_combo.addItem(str(y), y)
        # Aktuelles Jahr vorauswählen
        current_year = str(date.today().year)
        idx = self.year_combo.findText(current_year)
        if idx >= 0:
            self.year_combo.setCurrentIndex(idx)
        year_row.addWidget(self.year_combo, 1)
        period_layout.addLayout(year_row)

        period_group.setLayout(period_layout)
        layout.addWidget(period_group)

        # === OPTIONEN ===
        options_group = QGroupBox(tr("auto.views_export_dialog.94_optionen_21208517"))
        options_layout = QVBoxLayout()

        self.chk_include_header = QCheckBox(tr("dlg.spaltenueberschriften_einfuegen"))
        self.chk_include_header.setChecked(True)
        options_layout.addWidget(self.chk_include_header)

        self.chk_utf8_bom = QCheckBox(tr("dlg.utf8_bom_fuer_excel"))
        self.chk_utf8_bom.setChecked(True)
        options_layout.addWidget(self.chk_utf8_bom)

        options_group.setLayout(options_layout)
        layout.addWidget(options_group)

        # === BUTTONS ===
        btn_layout = QHBoxLayout()

        self.btn_export = QPushButton(
            tr("auto.views_export_dialog.111_exportieren_f9fcfb6d")
        )
        self.btn_export.setIcon(get_icon("📤"))
        self.btn_export.clicked.connect(self._do_export)
        btn_layout.addWidget(self.btn_export)

        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

        self.setLayout(layout)

    def _do_export(self):
        """Führt den Export durch"""
        if not (
            self.chk_tracking.isChecked()
            or self.chk_budget.isChecked()
            or self.chk_categories.isChecked()
        ):
            show_warning(
                self, tr("dlg.hinweis"), tr("dlg.bitte_mindestens_einen_datentyp")
            )
            return

        # Dateiname vorschlagen
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        year_text = self.year_combo.currentText().replace(" ", "_")
        default_name = f"budgetmanager_export_{year_text}_{timestamp}"

        # Format bestimmen
        if self.radio_csv.isChecked():
            ext = "csv"
            filter_str = "CSV-Dateien (*.csv)"
        elif self.radio_txt.isChecked():
            ext = "txt"
            filter_str = "Text-Dateien (*.txt)"
        elif self.radio_xlsx.isChecked():
            ext = "xlsx"
            filter_str = "Excel-Arbeitsmappen (*.xlsx)"
        else:
            ext = "pdf"
            filter_str = "PDF-Berichte (*.pdf)"

        # Speicherort wählen
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            tr("auto.views_export_dialog.146_export_speichern_unter_7108d72d"),
            trf(
                "auto.views_export_dialog.147_value_0_value_1_3c09bb8d",
                value_0=(default_name),
                value_1=(ext),
            ),
            filter_str,
        )

        if not file_path:
            return

        try:
            self._export_to_file(file_path)
            show_info(
                self,
                tr("export.success_title"),
                trf("export.success_body", path=file_path),
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self, tr("export.error_title"), trf("export.error_body", err=str(e))
            )

    def _collect_sections(self, year_filter: int | None):
        """Sammelt die gewählten Daten einmal für alle Exportformate."""
        from model.category_model import CategoryModel
        from model.report_export import ReportSection

        sections = []
        if self.chk_tracking.isChecked():
            rows = self.tracking.list_filtered(year=year_filter)
            sections.append(
                ReportSection(
                    title=tr("tab.tracking"),
                    headers=(
                        tr("header.date"),
                        tr("header.type"),
                        tr("header.category"),
                        tr("header.amount"),
                        tr("header.details"),
                    ),
                    rows=tuple(
                        (
                            row.d.strftime("%d.%m.%Y"),
                            display_typ(row.typ),
                            row.category,
                            float(row.amount),
                            row.details,
                        )
                        for row in rows
                    ),
                )
            )

        if self.chk_budget.isChecked():
            budget_rows = []
            years = [year_filter] if year_filter else self.budget.years()
            for year in years:
                for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
                    matrix = self.budget.get_matrix(year, typ)
                    for category, months in matrix.items():
                        for month, amount in months.items():
                            if abs(float(amount)) > 0.01:
                                budget_rows.append(
                                    (
                                        int(year),
                                        int(month),
                                        display_typ(typ),
                                        category,
                                        float(amount),
                                    )
                                )
            sections.append(
                ReportSection(
                    title=tr("tab.budget"),
                    headers=(
                        tr("report.year"),
                        tr("report.month"),
                        tr("header.type"),
                        tr("header.category"),
                        tr("header.amount"),
                    ),
                    rows=tuple(budget_rows),
                )
            )

        if self.chk_categories.isChecked():
            category_rows = []
            cats = CategoryModel(self.conn)
            for typ in [TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS]:
                for root in cats.build_tree(cats.list(typ)):
                    rc = root["cat"]
                    category_rows.append(
                        (
                            display_typ(typ),
                            rc.name,
                            "",
                            int(rc.is_fix),
                            int(rc.is_recurring),
                            int(rc.recurring_day),
                        )
                    )
                    for child in root["children"]:
                        cc = child["cat"]
                        category_rows.append(
                            (
                                display_typ(typ),
                                rc.name,
                                cc.name,
                                int(cc.is_fix),
                                int(cc.is_recurring),
                                int(cc.recurring_day),
                            )
                        )
            sections.append(
                ReportSection(
                    title=tr("tab.categories"),
                    headers=(
                        tr("header.type"),
                        tr("report.main_category"),
                        tr("report.subcategory"),
                        tr("report.fixed_flag"),
                        tr("report.recurring_flag"),
                        tr("report.due_day"),
                    ),
                    rows=tuple(category_rows),
                )
            )
        return sections

    def _export_to_file(self, file_path: str):
        """Exportiert die Daten atomar im ausgewählten Format."""
        year_data = self.year_combo.currentData()
        year_filter = int(year_data) if year_data is not None else None
        sections = self._collect_sections(year_filter)

        if self.radio_xlsx.isChecked():
            from model.report_export import export_sections_xlsx

            export_sections_xlsx(
                sections,
                Path(file_path),
                include_headers=self.chk_include_header.isChecked(),
            )
            return
        if self.radio_pdf.isChecked():
            from model.report_export import export_sections_pdf

            period = str(year_filter) if year_filter else tr("lbl.all_years")
            export_sections_pdf(
                sections,
                Path(file_path),
                title=f"Budgetmanager – {tr('menu.export')}",
                subtitle=period,
                include_headers=self.chk_include_header.isChecked(),
                empty_label=tr("report.no_data"),
            )
            return

        delimiter = "," if self.radio_csv.isChecked() else "\t"
        encoding = "utf-8-sig" if self.chk_utf8_bom.isChecked() else "utf-8"
        out = Path(file_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_suffix(out.suffix + ".tmp")
        try:
            with tmp.open("w", newline="", encoding=encoding) as handle:
                writer = csv.writer(handle, delimiter=delimiter)
                for section in sections:
                    if self.chk_include_header.isChecked():
                        writer.writerow([f"=== {section.title.upper()} ==="])
                        writer.writerow(list(section.headers))
                    writer.writerows(section.rows)
                    writer.writerow([])
                handle.flush()
                import os

                os.fsync(handle.fileno())
            tmp.replace(out)
        finally:
            tmp.unlink(missing_ok=True)
