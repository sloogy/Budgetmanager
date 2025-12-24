from __future__ import annotations
import sqlite3
import math

from PySide6.QtCore import Qt, QEvent
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QComboBox, QTableWidget, QTableWidgetItem,
    QPushButton, QMessageBox, QLabel, QSpinBox, QAbstractItemView, QCheckBox, QDialog
)

from model.category_model import CategoryModel
from model.budget_model import BudgetModel
from views.copy_year_dialog import CopyYearDialog
from views.budget_entry_dialog import BudgetEntryDialog, BudgetEntryRequest

MONTHS = ["Jan","Feb","Mär","Apr","Mai","Jun","Jul","Aug","Sep","Okt","Nov","Dez"]

def parse_amount(text: str) -> float:
    s = (text or "").strip()
    if not s:
        return 0.0
    s = s.replace("CHF","").strip()
    s = s.replace("'", "").replace(" ", "").replace(",", ".")
    return float(s)

def fmt_amount(val: float) -> str:
    if abs(val) < 1e-9:
        return ""
    return f"{val:.2f}"

class BudgetTab(QWidget):
    def __init__(self, conn: sqlite3.Connection):
        super().__init__()
        self.conn=conn
        self.cats=CategoryModel(conn)
        self.budget=BudgetModel(conn)

        self._internal_change = False

        self.year_spin=QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(2024)

        self.typ_cb=QComboBox()
        self.typ_cb.addItems(["Alle", "Ausgaben","Einkommen","Ersparnisse"])

        self.btn_load=QPushButton("Laden")
        self.btn_save=QPushButton("Speichern")
        self.btn_seed=QPushButton("Zeilen aus Kategorien erzeugen")
        self.btn_copy=QPushButton("Jahr kopieren…")

        self.btn_entry=QPushButton("Budget erfassen…")
        self.btn_edit=QPushButton("Budget bearbeiten…")

        self.btn_remove_budgetrow = QPushButton("Budget-Zeile entfernen")
        self.btn_remove_category = QPushButton("Kategorie löschen (global)")

        self.chk_autosave = QCheckBox("Auto-Speichern")
        self.chk_autosave.setChecked(False)

        self.chk_ask_due = QCheckBox("Beim Tippen nach Fälligkeit fragen")
        self.chk_ask_due.setChecked(True)

        # Kategorie + 12 Monate + Total
        self.table=QTableWidget(0, 14)
        self.table.setHorizontalHeaderLabels(["Kategorie"] + MONTHS + ["Total"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectItems)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed | QAbstractItemView.SelectedClicked)

        # Events
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.installEventFilter(self)

        # Shortcuts
        self.sc_save = QShortcut(QKeySequence.Save, self)
        self.sc_save.activated.connect(self.save)

        top=QHBoxLayout()
        top.addWidget(QLabel("Jahr"))
        top.addWidget(self.year_spin)
        top.addWidget(QLabel("Typ"))
        top.addWidget(self.typ_cb)
        top.addWidget(self.btn_load)
        top.addWidget(self.btn_save)
        top.addWidget(self.chk_autosave)
        top.addWidget(self.chk_ask_due)
        top.addWidget(self.btn_seed)
        top.addStretch(1)
        top.addWidget(self.btn_entry)
        top.addWidget(self.btn_edit)
        top.addWidget(self.btn_remove_budgetrow)
        top.addWidget(self.btn_remove_category)
        top.addWidget(self.btn_copy)

        root=QVBoxLayout()
        root.addLayout(top)
        root.addWidget(self.table)
        self.setLayout(root)

        self.btn_load.clicked.connect(self.load)
        self.btn_save.clicked.connect(self.save)
        self.btn_copy.clicked.connect(self.copy_year_dialog)
        self.btn_seed.clicked.connect(self.seed_from_categories)
        self.typ_cb.currentTextChanged.connect(lambda _: self.load())
        self.btn_entry.clicked.connect(self.open_entry_dialog)
        self.btn_edit.clicked.connect(self.open_edit_dialog)
        self.btn_remove_budgetrow.clicked.connect(self.remove_budget_row)
        self.btn_remove_category.clicked.connect(self.delete_category_global)

        self.load()

    # --- Komfort: Enter -> nächste Zelle ---
    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.KeyPress:
            key = event.key()
            if key in (Qt.Key_Return, Qt.Key_Enter):
                r = self.table.currentRow()
                c = self.table.currentColumn()
                if r < 0 or c < 0:
                    return False
                if c == 0:
                    self.table.setCurrentCell(r, 1)
                else:
                    next_c = c + 1
                    next_r = r
                    if next_c >= 14:  # after Total -> next row
                        next_c = 1
                        next_r = r + 1
                    if next_r >= self.table.rowCount():
                        next_r = self.table.rowCount() - 1
                    self.table.setCurrentCell(next_r, next_c if next_c != 13 else 13)
                return True
        return super().eventFilter(obj, event)

    def seed_from_categories(self):
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        names=self.cats.list_names(typ)
        self.budget.seed_year_from_categories(year, typ, names, amount=0.0)
        QMessageBox.information(self, "OK", f"Budget-Zeilen für {typ} {year} erzeugt.")
        self.load()

    def load(self):
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        
        # Wenn "Alle" gewählt: alle Typen laden
        if typ == "Alle":
            types = ["Ausgaben", "Einkommen", "Ersparnisse"]
        else:
            types = [typ]

        self._internal_change = True
        try:
            self.table.setRowCount(0)
            
            for t in types:
                names=self.cats.list_names(t)
                matrix=self.budget.get_matrix(year, t)
                
                # Typ-Header einfügen wenn "Alle"
                if typ == "Alle" and names:
                    r=self.table.rowCount()
                    self.table.insertRow(r)
                    header_item = QTableWidgetItem(f"═══ {t} ═══")
                    header_item.setFlags(header_item.flags() & ~Qt.ItemIsEditable)
                    font = header_item.font()
                    font.setBold(True)
                    header_item.setFont(font)
                    self.table.setItem(r,0,header_item)
                    for m in range(1,14):
                        empty = QTableWidgetItem("")
                        empty.setFlags(empty.flags() & ~Qt.ItemIsEditable)
                        self.table.setItem(r,m,empty)

                for name in names:
                    r=self.table.rowCount()
                    self.table.insertRow(r)
                    cat_item = QTableWidgetItem(name if typ != "Alle" else f"  {name}")
                    cat_item.setFlags(cat_item.flags() & ~Qt.ItemIsEditable)
                    cat_item.setData(Qt.UserRole + 10, t)  # Typ speichern
                    self.table.setItem(r,0,cat_item)

                    row_total=0.0
                    for m in range(1,13):
                        val=matrix.get(name, {}).get(m, 0.0)
                        row_total += float(val)
                        it=QTableWidgetItem(fmt_amount(float(val)))
                        it.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                        it.setData(Qt.UserRole + 10, t)  # Typ speichern
                        self.table.setItem(r,m,it)

                    tot=QTableWidgetItem(fmt_amount(row_total))
                    tot.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                    self.table.setItem(r,13,tot)

            self._recalc_footer()
            self.table.resizeColumnsToContents()
        finally:
            self._internal_change = False

    def _recalc_footer(self):
        # remove existing footer row
        for r in range(self.table.rowCount()):
            it=self.table.item(r,0)
            if it and it.text() == "TOTAL":
                self.table.removeRow(r)
                break

        if self.table.rowCount() == 0:
            return

        footer=self.table.rowCount()
        self.table.insertRow(footer)

        title=QTableWidgetItem("TOTAL")
        title.setFlags(title.flags() & ~Qt.ItemIsEditable)
        self.table.setItem(footer,0,title)

        grand=0.0
        for m in range(1,13):
            col_sum=0.0
            for r in range(footer):
                it=self.table.item(r,m)
                col_sum += parse_amount(it.text() if it else "")
            grand += col_sum
            cell=QTableWidgetItem(fmt_amount(col_sum))
            cell.setFlags(cell.flags() & ~Qt.ItemIsEditable)
            cell.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.table.setItem(footer,m,cell)

        gcell=QTableWidgetItem(fmt_amount(grand))
        gcell.setFlags(gcell.flags() & ~Qt.ItemIsEditable)
        gcell.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        self.table.setItem(footer,13,gcell)

    def _row_count_data(self) -> int:
        for r in range(self.table.rowCount()):
            it=self.table.item(r,0)
            if it and it.text() == "TOTAL":
                return r
        return self.table.rowCount()

    def _persist_single_cell(self, r: int, month_col: int):
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        cat=self.table.item(r,0).text()
        it=self.table.item(r,month_col)
        amt=parse_amount(it.text() if it else "")
        if typ == "Ausgaben" and amt < 0:
            amt = abs(amt)
        self.budget.set_amount(year, month_col, typ, cat, amt)

    def _get_db_value(self, cat: str, month: int) -> float:
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        mat = self.budget.get_matrix(year, typ)
        return float(mat.get(cat, {}).get(month, 0.0))

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._internal_change:
            return

        r = item.row()
        c = item.column()

        # ignore footer row
        if self.table.item(r,0) and self.table.item(r,0).text() == "TOTAL":
            return
        # ignore category edits
        if c == 0:
            return

        typ = self.typ_cb.currentText()
        cat = self.table.item(r,0).text()

        # Feature #1: if user edits Total -> distribute across months
        if c == 13:
            try:
                total = parse_amount(item.text())
            except Exception:
                total = 0.0
            if typ == "Ausgaben" and total < 0:
                total = abs(total)
                QMessageBox.information(self, "Hinweis", "Bei Ausgaben sind negative Beträge nicht erlaubt – Wert wurde korrigiert.")

            # distribute with rounding, keep sum exact
            base = round(total / 12.0, 2)
            last = round(total - base * 11, 2)

            self._internal_change = True
            try:
                for m in range(1,12):
                    it = self.table.item(r,m)
                    if it is None:
                        it = QTableWidgetItem()
                        self.table.setItem(r,m,it)
                    it.setText(fmt_amount(base))
                    it.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                it12 = self.table.item(r,12)
                if it12 is None:
                    it12 = QTableWidgetItem()
                    self.table.setItem(r,12,it12)
                it12.setText(fmt_amount(last))
                it12.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
                item.setText(fmt_amount(total))
                item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            finally:
                self._internal_change = False

            self._recalc_row_total(r)
            self._recalc_footer()

            if self.chk_autosave.isChecked():
                for m in range(1,13):
                    self._persist_single_cell(r, m)
            return

        # month cell edit: c in 1..12
        if 1 <= c <= 12 and self.chk_ask_due.isChecked():
            # capture typed value
            try:
                typed = parse_amount(item.text())
            except Exception:
                typed = 0.0
            if typ == "Ausgaben" and typed < 0:
                typed = abs(typed)

            # revert to previous db value first (so cancel doesn't keep typed value)
            prev = self._get_db_value(cat, c)
            self._internal_change = True
            try:
                item.setText(fmt_amount(prev))
                item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            finally:
                self._internal_change = False

            # open dialog to ask due/recurring
            _, is_rec, _day = self.cats.get_flags(typ, cat)
            default_mode = "Alle" if is_rec else "Monat"
            dlg = BudgetEntryDialog(
                self,
                default_year=int(self.year_spin.value()),
                default_typ=typ,
                categories=self.cats.list_names(typ),
                preset={"category": cat, "amount": typed, "month": c, "mode": default_mode, "only_if_empty": False},
            )
            if dlg.exec() == QDialog.Accepted:
                self._apply_request(dlg.get_request())
            return

        # Normal direct edit: normalize + totals + optional autosave
        try:
            val = parse_amount(item.text())
        except Exception:
            val = 0.0

        if typ == "Ausgaben" and val < 0:
            val = abs(val)
            QMessageBox.information(self, "Hinweis", "Bei Ausgaben sind negative Beträge nicht erlaubt – Wert wurde korrigiert.")

        self._internal_change = True
        try:
            item.setText(fmt_amount(val))
            item.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        finally:
            self._internal_change = False

        self._recalc_row_total(r)
        self._recalc_footer()

        if self.chk_autosave.isChecked() and (1 <= c <= 12):
            self._persist_single_cell(r, c)

    def _recalc_row_total(self, r: int):
        data_rows = self._row_count_data()
        if r >= data_rows:
            return
        row_total = 0.0
        for m in range(1,13):
            it = self.table.item(r,m)
            row_total += parse_amount(it.text() if it else "")
        tot = self.table.item(r,13)
        if tot is None:
            tot = QTableWidgetItem()
            self.table.setItem(r,13,tot)
        self._internal_change = True
        try:
            tot.setText(fmt_amount(row_total))
            tot.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
        finally:
            self._internal_change = False

    def save(self):
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        data_rows = self._row_count_data()

        for r in range(data_rows):
            cat=self.table.item(r,0).text()
            for m in range(1,13):
                it=self.table.item(r,m)
                amt=parse_amount(it.text() if it else "")
                if typ == "Ausgaben" and amt < 0:
                    amt = abs(amt)
                self.budget.set_amount(year,m,typ,cat,amt)
            self._recalc_row_total(r)

        self._recalc_footer()
        QMessageBox.information(self, "OK", "Budget gespeichert. (Tipp: Strg+S funktioniert auch)")

    def _apply_request(self, req: BudgetEntryRequest):
        if req.category not in self.cats.list_names(req.typ):
            QMessageBox.warning(self, "Kategorie fehlt", "Diese Kategorie existiert noch nicht im Kategorien-Tab. Bitte dort zuerst anlegen.")
            return

        self.budget.seed_year_from_categories(req.year, req.typ, [req.category], amount=0.0)

        if req.mode == "Alle":
            months = list(range(1,13))
        elif req.mode == "Bereich":
            a, b = sorted([req.from_month, req.to_month])
            months = list(range(a, b+1))
        else:
            months = [req.month]

        for m in months:
            amt = abs(req.amount) if (req.typ == "Ausgaben" and req.amount < 0) else req.amount

            if req.only_if_empty:
                mat = self.budget.get_matrix(req.year, req.typ)
                current = mat.get(req.category, {}).get(m, 0.0)
                if abs(float(current)) > 1e-9:
                    continue

            self.budget.set_amount(req.year, m, req.typ, req.category, amt)

        self.year_spin.setValue(req.year)
        self.typ_cb.setCurrentText(req.typ)
        self.load()
        self._focus_category_month(req.category, months[0])

    def _focus_category_month(self, category: str, month: int):
        data_rows = self._row_count_data()
        for r in range(data_rows):
            it = self.table.item(r,0)
            if it and it.text() == category:
                col = max(1, min(12, month))
                self.table.setCurrentCell(r, col)
                return

    def open_entry_dialog(self):
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        cats=self.cats.list_names(typ)

        preset = None
        r = self.table.currentRow()
        if r >= 0 and r < self._row_count_data():
            cat = self.table.item(r,0).text()
            _, is_rec, _day = self.cats.get_flags(typ, cat)
            preset = {"category": cat, "mode": ("Alle" if is_rec else "Monat")}

        dlg = BudgetEntryDialog(self, default_year=year, default_typ=typ, categories=cats, preset=preset)
        if dlg.exec() != QDialog.Accepted:
            return
        self._apply_request(dlg.get_request())

    def open_edit_dialog(self):
        r = self.table.currentRow()
        c = self.table.currentColumn()
        if r < 0 or c < 1 or c > 12:
            QMessageBox.information(self, "Hinweis", "Bitte eine Monatszelle (Jan–Dez) auswählen, die du bearbeiten willst.")
            return

        cat = self.table.item(r,0).text()
        current_txt = self.table.item(r,c).text() if self.table.item(r,c) else ""
        current_val = parse_amount(current_txt) if current_txt else 0.0

        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()
        cats=self.cats.list_names(typ)

        _, is_rec, _day = self.cats.get_flags(typ, cat)
        default_mode = "Alle" if is_rec else "Monat"

        dlg = BudgetEntryDialog(
            self,
            default_year=year,
            default_typ=typ,
            categories=cats,
            preset={"category": cat, "amount": current_val, "month": c, "mode": default_mode, "only_if_empty": False},
        )
        if dlg.exec() != QDialog.Accepted:
            return
        self._apply_request(dlg.get_request())

    def _selected_category(self) -> str | None:
        r = self.table.currentRow()
        if r < 0:
            return None
        it0 = self.table.item(r,0)
        if not it0:
            return None
        if it0.text() == "TOTAL":
            return None
        return it0.text()

    def remove_budget_row(self):
        cat = self._selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte eine Kategorie-Zeile auswählen (nicht TOTAL).")
            return
        year=int(self.year_spin.value())
        typ=self.typ_cb.currentText()

        if QMessageBox.question(
            self,
            "Budget-Zeile entfernen",
            f"Soll die Budget-Zeile '{cat}' für {typ} im Jahr {year} gelöscht werden?",
        ) != QMessageBox.Yes:
            return

        self.budget.delete_category_for_year(year, typ, cat)
        self.load()

    def delete_category_global(self):
        cat = self._selected_category()
        if not cat:
            QMessageBox.information(self, "Hinweis", "Bitte eine Kategorie-Zeile auswählen (nicht TOTAL).")
            return
        typ=self.typ_cb.currentText()

        msg = (
            "ACHTUNG: Das entfernt die Kategorie GLOBAL aus der Kategorien-Liste und löscht alle Budget-Einträge "
            f"für '{cat}' ({typ}) in ALLEN Jahren.\n\nFortfahren?"
        )

        if QMessageBox.question(self, "Kategorie löschen", msg) != QMessageBox.Yes:
            return

        self.budget.delete_category_all_years(typ, cat)
        self.cats.delete(typ, cat)
        self.load()

    def copy_year_dialog(self):
        default_src=int(self.year_spin.value())
        dlg=CopyYearDialog(self, default_src=default_src, known_years=self.budget.years())
        if dlg.exec() != QDialog.Accepted:
            return
        req=dlg.get_request()

        if req.src_year == req.dst_year:
            QMessageBox.warning(self, "Fehler", "Quelljahr und Zieljahr müssen verschieden sein.")
            return

        typ = None if req.scope_typ == "Alle" else req.scope_typ
        self.budget.copy_year(req.src_year, req.dst_year, carry_amounts=req.carry_amounts, typ=typ)

        if typ is None:
            for t in ["Ausgaben","Einkommen","Ersparnisse"]:
                self.budget.seed_year_from_categories(req.dst_year, t, self.cats.list_names(t), amount=0.0)
        else:
            self.budget.seed_year_from_categories(req.dst_year, typ, self.cats.list_names(typ), amount=0.0)

        QMessageBox.information(self, "OK", f"Budget {req.src_year} → {req.dst_year} kopiert.")
        self.year_spin.setValue(req.dst_year)
        self.load()
