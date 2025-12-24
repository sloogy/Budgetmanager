from __future__ import annotations

import sqlite3
import calendar
from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QDialog,
    QComboBox, QLabel, QLineEdit, QDateEdit, QGroupBox, QDoubleSpinBox
)

from model.category_model import CategoryModel
from views.type_color_helper import apply_tracking_type_colors
from views.delegates.badge_delegate import BadgeDelegate
from model.tracking_model import TrackingModel, TrackingRow
from model.budget_model import BudgetModel
from views.tracker_dialog import TrackerDialog, TrackingInput
from views.fixcost_dialog import FixcostDialog
from views.missing_bookings_dialog import MissingBookingsDialog, PendingBooking
from views.recurring_bookings_dialog import RecurringBookingsDialog

MONTHS_DE = ["Januar","Februar","März","April","Mai","Juni","Juli","August","September","Oktober","November","Dezember"]

def format_chf(amount: float) -> str:
    s=f"{amount:,.2f}"
    return s.replace(",", "X").replace(".", ".").replace("X", "'")

class TrackingTab(QWidget):
    def __init__(self, conn: sqlite3.Connection, settings=None):
        super().__init__()
        self.conn=conn
        self.settings = settings
        try:
            self.recent_days = 30 if int(getattr(settings, "recent_days", 14)) == 30 else 14
        except Exception:
            self.recent_days = 14
        self.cats=CategoryModel(conn)
        self.model=TrackingModel(conn)
        self.budget=BudgetModel(conn)

        # Buttons
        self.btn_add=QPushButton("Hinzufügen…")
        self.btn_fix=QPushButton("Fixkosten / Wiederkehrende…")
        self.btn_edit=QPushButton("Bearbeiten…")
        self.btn_del=QPushButton("Löschen")
        self.btn_clear_filters=QPushButton("Filter zurücksetzen")

        # Quick Filters
        self.chk_recent=QCheckBox(f"Nur letzte {self.recent_days} Tage")
        self.chk_recent.setChecked(False)
        
        # ===== ERWEITERTE FILTER =====
        
        # Typ-Filter
        self.filter_typ = QComboBox()
        self.filter_typ.addItems(["Alle", "Ausgaben", "Einkommen", "Ersparnisse"])
        
        # Kategorie-Filter
        self.filter_category = QComboBox()
        self.filter_category.addItem("Alle Kategorien")
        self._reload_categories()
        
        # Datumsfilter
        self.filter_date_from = QDateEdit()
        self.filter_date_from.setCalendarPopup(True)
        self.filter_date_from.setDate(date.today().replace(day=1))  # Erster des Monats
        self.filter_date_from.setDisplayFormat("dd.MM.yyyy")
        
        self.filter_date_to = QDateEdit()
        self.filter_date_to.setCalendarPopup(True)
        self.filter_date_to.setDate(date.today())
        self.filter_date_to.setDisplayFormat("dd.MM.yyyy")
        
        self.chk_use_date_filter = QCheckBox("Datumsfilter aktiv")
        self.chk_use_date_filter.setChecked(False)
        
        # Betragsfilter
        self.filter_min_amount = QDoubleSpinBox()
        self.filter_min_amount.setRange(0, 999999)
        self.filter_min_amount.setPrefix("CHF ")
        self.filter_min_amount.setValue(0)
        self.filter_min_amount.setSingleStep(10)
        
        self.filter_max_amount = QDoubleSpinBox()
        self.filter_max_amount.setRange(0, 999999)
        self.filter_max_amount.setPrefix("CHF ")
        self.filter_max_amount.setValue(999999)
        self.filter_max_amount.setSingleStep(10)
        
        self.chk_use_amount_filter = QCheckBox("Betragsfilter aktiv")
        self.chk_use_amount_filter.setChecked(False)
        
        # Textsuche
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText("Suche in Details und Kategorie...")
        self.filter_search.setClearButtonEnabled(True)

        # Summen-Label
        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("font-weight: bold; padding: 5px;")

        # Tabelle
        self.table=QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels(["Datum","Typ","Kategorie","CHF","Details","_id"])
        # Badge/Pillen Darstellung für Typ-Spalte
        self._badge_delegate = BadgeDelegate(self.table, color_map=self.settings.get("type_colors", {}))
        self.table.setItemDelegateForColumn(1, self._badge_delegate)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnHidden(5, True)  # internal id
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.setAlternatingRowColors(True)

        # === LAYOUTS ===
        
        # Button-Leiste
        top=QHBoxLayout()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_fix)
        top.addWidget(self.btn_edit)
        top.addWidget(self.btn_del)
        top.addStretch(1)
        top.addWidget(self.chk_recent)

        # Filter-GroupBox
        filter_group = QGroupBox("Filter")
        filter_layout = QVBoxLayout()
        
        # Zeile 1: Typ und Kategorie
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Typ:"))
        row1.addWidget(self.filter_typ, 1)
        row1.addWidget(QLabel("Kategorie:"))
        row1.addWidget(self.filter_category, 2)
        filter_layout.addLayout(row1)
        
        # Zeile 2: Datumsfilter
        row2 = QHBoxLayout()
        row2.addWidget(self.chk_use_date_filter)
        row2.addWidget(QLabel("Von:"))
        row2.addWidget(self.filter_date_from)
        row2.addWidget(QLabel("Bis:"))
        row2.addWidget(self.filter_date_to)
        row2.addStretch(1)
        filter_layout.addLayout(row2)
        
        # Zeile 3: Betragsfilter
        row3 = QHBoxLayout()
        row3.addWidget(self.chk_use_amount_filter)
        row3.addWidget(QLabel("Min:"))
        row3.addWidget(self.filter_min_amount)
        row3.addWidget(QLabel("Max:"))
        row3.addWidget(self.filter_max_amount)
        row3.addStretch(1)
        filter_layout.addLayout(row3)
        
        # Zeile 4: Textsuche und Reset
        row4 = QHBoxLayout()
        row4.addWidget(QLabel("Suche:"))
        row4.addWidget(self.filter_search, 3)
        row4.addWidget(self.btn_clear_filters)
        filter_layout.addLayout(row4)
        
        filter_group.setLayout(filter_layout)

        # Hauptlayout
        root=QVBoxLayout()
        root.addLayout(top)
        root.addWidget(filter_group)
        root.addWidget(self.lbl_summary)
        root.addWidget(self.table)
        self.setLayout(root)

        # === SIGNALS ===
        self.btn_add.clicked.connect(self.add)
        self.btn_fix.clicked.connect(self.add_fixcosts)
        self.btn_edit.clicked.connect(self.edit)
        self.btn_del.clicked.connect(self.delete)
        self.btn_clear_filters.clicked.connect(self.clear_filters)
        
        # Filter-Änderungen triggern refresh
        self.chk_recent.toggled.connect(lambda _: self.refresh())
        self.filter_typ.currentIndexChanged.connect(lambda _: self._on_typ_changed())
        self.filter_category.currentIndexChanged.connect(lambda _: self.refresh())
        self.chk_use_date_filter.toggled.connect(lambda _: self.refresh())
        self.filter_date_from.dateChanged.connect(lambda _: self.refresh())
        self.filter_date_to.dateChanged.connect(lambda _: self.refresh())
        self.chk_use_amount_filter.toggled.connect(lambda _: self.refresh())
        self.filter_min_amount.valueChanged.connect(lambda _: self.refresh())
        self.filter_max_amount.valueChanged.connect(lambda _: self.refresh())
        self.filter_search.textChanged.connect(lambda _: self.refresh())
        
        self.table.doubleClicked.connect(lambda _: self.edit())

        self.refresh()

    def _reload_categories(self):
        """Lädt alle Kategorien in den Filter"""
        current = self.filter_category.currentText()
        self.filter_category.clear()
        self.filter_category.addItem("Alle Kategorien")
        
        all_cats = set()
        for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
            cats = self.cats.list_names(typ)
            all_cats.update(cats)
        
        for cat in sorted(all_cats):
            self.filter_category.addItem(cat)
        
        # Wiederherstellen der vorherigen Auswahl
        idx = self.filter_category.findText(current)
        if idx >= 0:
            self.filter_category.setCurrentIndex(idx)

    def _on_typ_changed(self):
        """Wenn Typ geändert wird, Kategorien-Filter anpassen"""
        typ = self.filter_typ.currentText()
        if typ == "Alle":
            self._reload_categories()
        else:
            current = self.filter_category.currentText()
            self.filter_category.clear()
            self.filter_category.addItem("Alle Kategorien")
            cats = self.cats.list_names(typ)
            for cat in cats:
                self.filter_category.addItem(cat)
            
            idx = self.filter_category.findText(current)
            if idx >= 0:
                self.filter_category.setCurrentIndex(idx)
        
        self.refresh()

    def clear_filters(self):
        """Setzt alle Filter zurück"""
        self.filter_typ.setCurrentIndex(0)
        self.filter_category.setCurrentIndex(0)
        self.chk_use_date_filter.setChecked(False)
        self.filter_date_from.setDate(date.today().replace(day=1))
        self.filter_date_to.setDate(date.today())
        self.chk_use_amount_filter.setChecked(False)
        self.filter_min_amount.setValue(0)
        self.filter_max_amount.setValue(999999)
        self.filter_search.clear()
        self.chk_recent.setChecked(False)

    def _selected_id(self) -> int | None:
        r = self.table.currentRow()
        if r < 0:
            return None
        it = self.table.item(r,5)
        if not it:
            return None
        try:
            return int(it.text())
        except Exception:
            return None

    def set_recent_days(self, days: int):
        """Setzt den Zeitraum für den Quick-Filter (nur 14 oder 30)."""
        self.recent_days = 30 if int(days) == 30 else 14
        self.chk_recent.setText(f"Nur letzte {self.recent_days} Tage")
        # Wenn Quick-Filter aktiv ist, sofort neu laden
        if self.chk_recent.isChecked():
            self.refresh()

    def refresh(self):
        """Lädt Daten mit aktiven Filtern"""
        
        # Quick Filter: Letzte 14 Tage
        if self.chk_recent.isChecked():
            rows = self.model.list_recent_sorted(self.recent_days)
        else:
            # Erweiterte Filter verwenden
            typ = self.filter_typ.currentText() if self.filter_typ.currentText() != "Alle" else None
            category = self.filter_category.currentText() if self.filter_category.currentText() != "Alle Kategorien" else None
            
            date_from = None
            date_to = None
            if self.chk_use_date_filter.isChecked():
                date_from = self.filter_date_from.date().toPython()
                date_to = self.filter_date_to.date().toPython()
            
            min_amount = None
            max_amount = None
            if self.chk_use_amount_filter.isChecked():
                min_amount = self.filter_min_amount.value()
                max_amount = self.filter_max_amount.value()
            
            search_text = self.filter_search.text().strip() or None
            
            rows = self.model.list_filtered(
                typ=typ,
                category=category,
                date_from=date_from,
                date_to=date_to,
                min_amount=min_amount,
                max_amount=max_amount,
                search_text=search_text
            )

        # Tabelle füllen
        self.table.setRowCount(0)
        total_ausgaben = 0.0
        total_einkommen = 0.0
        total_ersparnisse = 0.0
        
        for r in rows:
            i=self.table.rowCount()
            self.table.insertRow(i)
            self.table.setItem(i,0,QTableWidgetItem(r.d.strftime("%d.%m.%Y")))
            self.table.setItem(i,1,QTableWidgetItem(str(r.typ)))
            self.table.setItem(i,2,QTableWidgetItem(str(r.category)))
            a=QTableWidgetItem(format_chf(float(r.amount)))
            a.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.table.setItem(i,3,a)
            self.table.setItem(i,4,QTableWidgetItem(str(r.details)))
            self.table.setItem(i,5,QTableWidgetItem(str(r.id)))
            
            # Summen berechnen
            if r.typ == "Ausgaben":
                total_ausgaben += r.amount
            elif r.typ == "Einkommen":
                total_einkommen += r.amount
            elif r.typ == "Ersparnisse":
                total_ersparnisse += r.amount
        
        self.table.resizeColumnsToContents()
        
        # Summen anzeigen
        saldo = total_einkommen - total_ausgaben - total_ersparnisse
        summary_text = (
            f"Einträge: {len(rows)} | "
            f"Einkommen: {format_chf(total_einkommen)} CHF | "
            f"Ausgaben: {format_chf(total_ausgaben)} CHF | "
            f"Ersparnisse: {format_chf(total_ersparnisse)} CHF | "
            f"Saldo: {format_chf(saldo)} CHF"
        )
        self.lbl_summary.setText(summary_text)
        # Typ- und Negativfarben anwenden (Erscheinungsprofil)
        type_colors = self.settings.get('type_colors', {}) if hasattr(self, 'settings') else {}
        negative_color = self.settings.get('negative_color', None) if hasattr(self, 'settings') else None
        try:
            apply_tracking_type_colors(self.table, type_colors, negative_color)
            if hasattr(self, '_badge_delegate') and self._badge_delegate is not None:
                self._badge_delegate.set_colors(type_colors)
                self.table.viewport().update()
        except Exception:
            pass



    def set_recent_days(self, days: int):
        """Setzt die Anzahl Tage für den Quick-Filter (nur 14 oder 30)."""
        self.recent_days = 30 if int(days) == 30 else 14
        self.chk_recent.setText(f"Nur letzte {self.recent_days} Tage")
        # Wenn der Filter aktiv ist, direkt neu laden
        if self.chk_recent.isChecked():
            self.refresh()

    def add(self):
        dlg=TrackerDialog(self, conn=self.conn, cats=self.cats)
        if dlg.exec() != QDialog.Accepted:
            return
        inp: TrackingInput = dlg.get_input()
        self.model.add(inp.d, inp.typ, inp.category, inp.amount, inp.details)
        self.refresh()

    def add_fixcosts(self):
        # default: first day of current month
        today = date.today()
        default_date = date(today.year, today.month, 1)

        dlg = FixcostDialog(self, default_date=default_date)
        if dlg.exec() != QDialog.Accepted:
            return
        req = dlg.get_request()

        year = req.d.year
        month = req.d.month
        month_name = MONTHS_DE[month-1]

        # Kandidaten sammeln: Fixkosten (fixer Betrag) vs. Wiederkehrend (variabel)
        fix_items: list[PendingBooking] = []
        recurring_items: list[PendingBooking] = []
        skipped_existing = 0
        skipped_zero = 0

        last_day = calendar.monthrange(year, month)[1]

        for typ in ["Ausgaben", "Einkommen", "Ersparnisse"]:
            for cat in self.cats.list(typ):
                if not (cat.is_fix or cat.is_recurring):
                    continue

                amt = self.budget.get_amount(year, month, typ, cat.name)

                # Buchungsdatum: Tag aus Kategorie (falls gesetzt), sonst Monatsanfang
                # (für Fixkosten genauso relevant wie für Wiederkehrend)
                day = int(cat.recurring_day or 1) if (cat.is_recurring or cat.is_fix) else 1
                if day < 1:
                    day = 1
                if day > last_day:
                    day = last_day

                d = date(year, month, day)
                details = f"{month_name} - {cat.name}"

                # Doppelte vermeiden: wenn schon in diesem Monat vorhanden -> überspringen
                if self.model.exists_in_month(year=year, month=month, typ=typ, category=cat.name):
                    skipped_existing += 1
                    continue

                # Fixkosten: Betrag muss > 0 sein (sonst macht Fixkosten-Buchung keinen Sinn)
                if cat.is_fix:
                    if abs(float(amt)) < 1e-9:
                        skipped_zero += 1
                        continue
                    fix_items.append(PendingBooking(d=d, typ=typ, category=cat.name, amount=float(amt), details=details))
                    continue

                # Wiederkehrend, aber NICHT Fixkosten -> variabel: in Liste anzeigen (Betrag editierbar)
                if cat.is_recurring and not cat.is_fix:
                    recurring_items.append(PendingBooking(d=d, typ=typ, category=cat.name, amount=float(amt), details=details))
                    continue

        if not fix_items and not recurring_items:
            if skipped_existing > 0:
                QMessageBox.information(self, "Info", "Für diesen Monat ist bereits alles gebucht.")
            else:
                QMessageBox.information(
                    self,
                    "Info",
                    "Keine Fixkosten/Wiederkehrenden Kategorien mit Budget-Betrag gefunden.\n"
                    "Tipp: Betrag im Budget setzen und Kategorie als Fixkosten oder wiederkehrend markieren.",
                )
            return

        # Wenn wiederkehrende (variable) existieren: immer Liste öffnen (Beträge editierbar)
        # + Button "Nur Fixkosten" für den schnellen Fixkosten-Only-Run.
        to_book: list[PendingBooking] = []
        if recurring_items:
            dlg_book = RecurringBookingsDialog(self, fix_items=fix_items, recurring_items=recurring_items)
            if dlg_book.exec() != QDialog.Accepted:
                return
            to_book = dlg_book.selected_items()
        else:
            # Nur Fixkosten: optional Liste anzeigen (wie vorher)
            if not fix_items:
                QMessageBox.information(self, "Info", "Keine Fixkosten gefunden.")
                return
            res = QMessageBox.question(
                self,
                "Fixkosten",
                f"{len(fix_items)} Fixkosten fehlen in {month_name} {year}.\n\n"
                "Liste anzeigen zum Auswählen?\n"
                "(Nein = alle fehlenden direkt buchen)",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if res == QMessageBox.Cancel:
                return
            if res == QMessageBox.Yes:
                dlg_list = MissingBookingsDialog(self, items=fix_items, title="Fixkosten")
                if dlg_list.exec() != QDialog.Accepted:
                    return
                to_book = dlg_list.selected_items()
            else:
                to_book = fix_items

        inserted = 0
        skipped_zero_book = 0
        for it in to_book:
            if abs(float(it.amount)) < 1e-9:
                skipped_zero_book += 1
                continue
            self.model.add(it.d, it.typ, it.category, float(it.amount), it.details)
            inserted += 1

        QMessageBox.information(
            self,
            "OK",
            f"{inserted} Buchungen hinzugefügt.\n"
            f"Übersprungen (bereits vorhanden): {skipped_existing}\n"
            f"Übersprungen (Budget=0 bei Fixkosten): {skipped_zero}\n"
            f"Übersprungen (0-Betrag in Liste): {skipped_zero_book}",
        )
        self.refresh()

    def edit(self):
        row_id = self._selected_id()
        if row_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Zeile auswählen.")
            return

        r = self.table.currentRow()
        d = self.table.item(r,0).text()
        typ = self.table.item(r,1).text()
        cat = self.table.item(r,2).text()
        amt_txt = self.table.item(r,3).text().replace("'", "").replace(",", ".").strip()
        try:
            amt = float(amt_txt)
        except Exception:
            amt = 0.0
        details = self.table.item(r,4).text() if self.table.item(r,4) else ""

        dlg=TrackerDialog(self, conn=self.conn, cats=self.cats, preset={"date": d, "typ": typ, "category": cat, "amount": amt, "details": details})
        if dlg.exec() != QDialog.Accepted:
            return
        inp: TrackingInput = dlg.get_input()
        self.model.update(row_id, inp.d, inp.typ, inp.category, inp.amount, inp.details)
        self.refresh()

    def delete(self):
        row_id = self._selected_id()
        if row_id is None:
            QMessageBox.information(self, "Hinweis", "Bitte zuerst eine Zeile auswählen.")
            return
        r = self.table.currentRow()
        summary = f"{self.table.item(r,0).text()} | {self.table.item(r,1).text()} | {self.table.item(r,2).text()} | {self.table.item(r,3).text()}"
        if QMessageBox.question(self, "Löschen", f"Diesen Eintrag löschen?\n\n{summary}") != QMessageBox.Yes:
            return
        self.model.delete(row_id)
        self.refresh()
