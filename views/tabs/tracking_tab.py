from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
import sqlite3
import calendar
from datetime import date

from PySide6.QtCore import Qt, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
    QTableWidget, QTableWidgetItem, QAbstractItemView, QMessageBox, QDialog,
    QComboBox, QLabel, QLineEdit, QDateEdit, QGroupBox, QDoubleSpinBox, QMenu
)

from model.category_model import CategoryModel
from model.tags_model import TagsModel
from views.type_color_helper import apply_tracking_type_colors
from views.delegates.badge_delegate import BadgeDelegate
from model.tracking_model import TrackingModel
from model.budget_model import BudgetModel
from views.tracker_dialog import TrackerDialog, TrackingInput
from views.fixcost_dialog import FixcostDialog
from views.missing_bookings_dialog import MissingBookingsDialog, PendingBooking
from views.recurring_bookings_dialog import RecurringBookingsDialog
from utils.money import format_short as format_chf, format_money, currency_header
from views.ui_colors import ui_colors
from utils.i18n import tr, trf
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS
from utils.i18n import display_typ, db_typ_from_display

def _months_de() -> list[str]: return [tr(f"month.{i}") for i in range(1, 13)]
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
        self.tags_model=TagsModel(conn)

        # Buttons
        self.btn_add=QPushButton(tr("btn.add") + "…")
        # Quick action: erzeugt Buchungen aus Fixkosten-/Wiederkehrend-Markierungen der Kategorien
        self.btn_fix=QPushButton(tr("btn.recurring_book"))
        self.btn_edit=QPushButton(tr("btn.edit"))
        self.btn_del=QPushButton(tr("btn.delete"))
        self.btn_clear_filters=QPushButton(tr("btn.reset_filters"))

        # Quick Filters
        self.chk_recent=QCheckBox(f"Nur letzte {self.recent_days} Tage")
        self.chk_recent.setChecked(False)
        
        # ===== ERWEITERTE FILTER =====
        
        # Typ-Filter
        self.filter_typ = QComboBox()
        # userData = DB-Schlüssel (sprachunabhängig), text = Anzeigename
        for _disp, _key in [(tr("typ.Alle"), ""), (tr("typ.Ausgaben"), "Ausgaben"),
                             (tr("typ.Einkommen"), "Einkommen"), (tr("typ.Ersparnisse"), "Ersparnisse")]:
            self.filter_typ.addItem(_disp, _key)
        
        # Kategorie-Filter
        self.filter_category = QComboBox()
        self.filter_category.addItem(tr("tracking.filter.all_categories"))
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
        
        self.chk_use_date_filter = QCheckBox(tr("tracking.chk.date_filter"))
        self.chk_use_date_filter.setChecked(False)
        
        # Betragsfilter
        self.filter_min_amount = QDoubleSpinBox()
        self.filter_min_amount.setRange(0, 999999)
        self.filter_min_amount.setPrefix(f"{currency_header()} ")
        self.filter_min_amount.setValue(0)
        self.filter_min_amount.setSingleStep(10)
        
        self.filter_max_amount = QDoubleSpinBox()
        self.filter_max_amount.setRange(0, 999999)
        self.filter_max_amount.setPrefix(f"{currency_header()} ")
        self.filter_max_amount.setValue(999999)
        self.filter_max_amount.setSingleStep(10)
        
        self.chk_use_amount_filter = QCheckBox(tr("tracking.chk.amount_filter"))
        self.chk_use_amount_filter.setChecked(False)
        
        # Textsuche
        self.filter_search = QLineEdit()
        self.filter_search.setPlaceholderText(tr("tracking.ph.search"))
        self.filter_search.setClearButtonEnabled(True)

        # Tag-Filter
        self.filter_tag = QComboBox()
        self.filter_tag.addItem(tr("tracking.filter.all_tags"), None)
        self._reload_tags()

        # Summen-Label
        self.lbl_summary = QLabel()
        self.lbl_summary.setStyleSheet("font-weight: bold; padding: 5px;")

        # Tabelle
        self.table=QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([tr("header.date"), tr("header.type"), tr("header.category"), currency_header(), tr("header.description"), "_id"])

        # Accessibility: Header-Tooltips
        _hdr = self.table.horizontalHeader()
        for _i, _tip in enumerate([tr("tracking.tip.col_date"), tr("tracking.tip.col_type"), tr("tracking.tip.col_category"), tr("tracking.tip.col_amount"), tr("tracking.tip.col_details")]):
            if _i < self.table.columnCount():
                self.table.horizontalHeaderItem(_i).setToolTip(_tip)
        # Badge/Pillen Darstellung für Typ-Spalte
        self._badge_delegate = BadgeDelegate(self.table, color_map=self.settings.get("type_colors", {}))
        self.table.setItemDelegateForColumn(1, self._badge_delegate)
        self.table.setColumnWidth(1, 120)
        self.table.setColumnHidden(5, True)  # internal id
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setContextMenuPolicy(Qt.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)

        # Debounce-Timer: bei Filter-Änderungen nur 1× refreshen
        self._refresh_timer = QTimer(self)
        self._refresh_timer.setSingleShot(True)
        self._refresh_timer.setInterval(200)
        self._refresh_timer.timeout.connect(self.refresh)

        # === LAYOUTS ===
        
        # Button-Leiste (kompakt - nur Hinzufügen und Löschen)
        top=QHBoxLayout()
        top.addWidget(self.btn_add)
        top.addWidget(self.btn_fix)
        top.addWidget(self.btn_del)
        top.addStretch(1)
        top.addWidget(self.chk_recent)
        # btn_edit ist im Menü "Bearbeiten" verfügbar
        self.btn_edit.setVisible(False)

        # Filter-GroupBox
        filter_group = QGroupBox(tr("tracking.grp.filters"))
        filter_layout = QVBoxLayout()
        
        # Zeile 1: Typ und Kategorie
        row1 = QHBoxLayout()
        row1.addWidget(QLabel("Typ:"))
        row1.addWidget(self.filter_typ, 1)
        row1.addWidget(QLabel(tr("lbl.category")))
        row1.addWidget(self.filter_category, 2)
        row1.addWidget(QLabel("Tag:"))
        row1.addWidget(self.filter_tag, 1)
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
        row4.addWidget(QLabel(tr("lbl.search")))
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
        
        # Filter-Änderungen triggern debounced refresh (200ms)
        self.chk_recent.toggled.connect(lambda _: self._delayed_refresh())
        self.filter_typ.currentIndexChanged.connect(lambda _: self._on_typ_changed())
        self.filter_category.currentIndexChanged.connect(lambda _: self._delayed_refresh())
        self.chk_use_date_filter.toggled.connect(lambda _: self._delayed_refresh())
        self.filter_date_from.dateChanged.connect(lambda _: self._delayed_refresh())
        self.filter_date_to.dateChanged.connect(lambda _: self._delayed_refresh())
        self.chk_use_amount_filter.toggled.connect(lambda _: self._delayed_refresh())
        self.filter_min_amount.valueChanged.connect(lambda _: self._delayed_refresh())
        self.filter_max_amount.valueChanged.connect(lambda _: self._delayed_refresh())
        self.filter_search.textChanged.connect(lambda _: self._delayed_refresh())
        self.filter_tag.currentIndexChanged.connect(lambda _: self._delayed_refresh())
        
        self.table.doubleClicked.connect(lambda _: self.edit())

        self.refresh()

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def _reload_categories(self):
        """Lädt alle Kategorien in den Filter (Tree-fähig)"""
        current_data = self.filter_category.currentData() or self.filter_category.currentText().strip()
        self.filter_category.clear()
        self.filter_category.addItem(tr("tracking.filter.all_categories"), None)

        # In 'Alle' zeigen wir Typ-Prefix zur besseren Unterscheidung
        rows = []
        for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
            pairs = []
            if hasattr(self.cats, "list_names_tree"):
                try:
                    pairs = self.cats.list_names_tree(typ)
                except Exception:
                    pairs = []
            if pairs:
                for label, real in pairs:
                    rows.append((trf("tracking.filter.typ_prefix", typ=display_typ(typ), label=label), real))
            else:
                for cat in self.cats.list_names(typ):
                    rows.append((trf("tracking.filter.typ_prefix", typ=display_typ(typ), label=cat), cat))

        # sort by display text
        for disp, real in sorted(rows, key=lambda x: str(x[0]).lower()):
            self.filter_category.addItem(disp, real)

        # Auswahl wiederherstellen
        if current_data:
            for i in range(self.filter_category.count()):
                if self.filter_category.itemData(i) == current_data or self.filter_category.itemText(i).strip().endswith(str(current_data)):
                    self.filter_category.setCurrentIndex(i)
                    break

    def _reload_tags(self):
        """Lädt alle Tags in den Tag-Filter."""
        current_data = self.filter_tag.currentData()
        self.filter_tag.clear()
        self.filter_tag.addItem(tr("tracking.filter.all_tags"), None)
        try:
            for tag in self.tags_model.list_all():
                self.filter_tag.addItem(tag.name, tag.id)
        except Exception as e:
            logger.debug("for tag in self.tags_model.list_all():: %s", e)
        # Auswahl wiederherstellen
        if current_data is not None:
            for i in range(self.filter_tag.count()):
                if self.filter_tag.itemData(i) == current_data:
                    self.filter_tag.setCurrentIndex(i)
                    break

    def _on_typ_changed(self):
        """Wenn Typ geändert wird, Kategorien-Filter anpassen"""
        typ = self._current_filter_typ_db()
        if typ == "Alle":
            self._reload_categories()
        else:
            current_data = self.filter_category.currentData() or self.filter_category.currentText().strip()
            self.filter_category.clear()
            self.filter_category.addItem(tr("tracking.filter.all_categories"), None)

            pairs = []
            if hasattr(self.cats, "list_names_tree"):
                try:
                    pairs = self.cats.list_names_tree(typ)
                except Exception:
                    pairs = []

            if pairs:
                for label, real in pairs:
                    self.filter_category.addItem(label, real)
            else:
                for cat in self.cats.list_names(typ):
                    self.filter_category.addItem(cat, cat)

            if current_data:
                for i in range(self.filter_category.count()):
                    if self.filter_category.itemData(i) == current_data or self.filter_category.itemText(i).strip() == str(current_data):
                        self.filter_category.setCurrentIndex(i)
                        break
        
        self._delayed_refresh()

    def _delayed_refresh(self):
        """Debounced: Timer (re-)starten – refresh() wird erst nach 200ms Ruhe ausgelöst."""
        self._refresh_timer.stop()
        self._refresh_timer.start()

    def _show_context_menu(self, pos):
        """Rechtsklick-Kontextmenü auf der Tracking-Tabelle."""
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        self.table.selectRow(row)
        menu = QMenu(self)
        act_edit = menu.addAction(tr("btn.edit"))
        act_tags = menu.addAction(tr("tracking.ctx.set_tags"))
        menu.addSeparator()
        act_duplicate = menu.addAction(tr("tracking.ctx.duplicate"))
        menu.addSeparator()
        act_delete = menu.addAction(tr("btn.delete"))
        chosen = menu.exec(self.table.viewport().mapToGlobal(pos))
        if chosen == act_edit:
            self.edit()
        elif chosen == act_tags:
            self._set_tags_for_selected()
        elif chosen == act_duplicate:
            self._duplicate_selected()
        elif chosen == act_delete:
            self.delete()

    def _set_tags_for_selected(self):
        """Dialog zum Setzen von Tags für den ausgewählten Eintrag."""
        sel = self.table.currentRow()
        if sel < 0:
            return
        entry_id = int(self.table.item(sel, 5).text())

        all_tags = self.tags_model.list_all()
        if not all_tags:
            QMessageBox.information(self, tr("header.tags"), tr("tracking.msg.no_tags"))
            return

        current_tags = self.tags_model.get_tags_for_entry(entry_id)
        current_ids = {t["id"] for t in current_tags}

        # Einfacher Checkable-Dialog
        from PySide6.QtWidgets import QListWidget, QListWidgetItem, QDialogButtonBox
        dlg = QDialog(self)
        dlg.setWindowTitle(tr("tracking.title.set_tags"))
        dlg.setMinimumWidth(300)
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(trf("tracking.lbl.tags_for_entry", entry_id=entry_id)))

        lw = QListWidget()
        for tag in all_tags:
            item = QListWidgetItem(tag.name)
            item.setCheckState(Qt.Checked if tag.id in current_ids else Qt.Unchecked)
            item.setData(Qt.UserRole, tag.id)
            lw.addItem(item)
        layout.addWidget(lw)

        bb = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        bb.accepted.connect(dlg.accept)
        bb.rejected.connect(dlg.reject)
        layout.addWidget(bb)

        if dlg.exec() == QDialog.Accepted:
            new_ids = []
            for i in range(lw.count()):
                item = lw.item(i)
                if item.checkState() == Qt.Checked:
                    new_ids.append(item.data(Qt.UserRole))
            self.tags_model.set_entry_tags(entry_id, new_ids)
            self._reload_tags()

    def _duplicate_selected(self):
        """Dupliziert den ausgewählten Eintrag (mit heutigem Datum)."""
        row_id = self._selected_id()
        if row_id is None:
            return
        r = self.table.currentRow()
        typ = self.table.item(r, 1).text()
        cat = self.table.item(r, 2).text()
        amt_txt = self.table.item(r, 3).text().replace("'", "").replace(",", ".").strip()
        try:
            amt = float(amt_txt)
        except Exception:
            amt = 0.0
        details = self.table.item(r, 4).text() if self.table.item(r, 4) else ""
        self.model.add(date.today(), db_typ_from_display(typ), cat, amt, details)
        self.refresh()

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def clear_filters(self):
        """Setzt alle Filter zurück"""
        self.filter_typ.setCurrentIndex(0)
        self.filter_category.setCurrentIndex(0)
        self.filter_tag.setCurrentIndex(0)
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

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def refresh(self):
        """Lädt Daten mit aktiven Filtern"""
        
        # Quick Filter: Letzte 14 Tage
        if self.chk_recent.isChecked():
            rows = self.model.list_recent_sorted(self.recent_days)
        else:
            # Erweiterte Filter verwenden
            typ = (self._current_filter_typ_db() if not self._is_all_typ() else None)
            category = self.filter_category.currentData()
            
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

            # Tag-Filter
            tag_id = self.filter_tag.currentData()

            rows = self.model.list_filtered(
                typ=typ,
                category=category,
                date_from=date_from,
                date_to=date_to,
                min_amount=min_amount,
                max_amount=max_amount,
                search_text=search_text,
                tag_id=tag_id,
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
            self.table.setItem(i,1,QTableWidgetItem(display_typ(str(r.typ))))
            self.table.setItem(i,2,QTableWidgetItem(self.cats.display_with_parent(str(r.typ), str(r.category))))
            a=QTableWidgetItem(format_chf(float(r.amount)))
            a.setTextAlignment(Qt.AlignRight|Qt.AlignVCenter)
            self.table.setItem(i,3,a)
            self.table.setItem(i,4,QTableWidgetItem(str(r.details)))
            self.table.setItem(i,5,QTableWidgetItem(str(r.id)))
            
            # Summen berechnen
            if r.typ == TYP_EXPENSES:
                total_ausgaben += r.amount
            elif r.typ == TYP_INCOME:
                total_einkommen += r.amount
            elif r.typ == TYP_SAVINGS:
                total_ersparnisse += r.amount
        
        self.table.resizeColumnsToContents()
        
        # Summen anzeigen
        saldo = total_einkommen - total_ausgaben - total_ersparnisse
        summary_text = trf("tracking.summary", count=len(rows), income=format_money(total_einkommen), expenses=format_money(total_ausgaben), savings=format_money(total_ersparnisse), balance=format_money(saldo))
        self.lbl_summary.setText(summary_text)
        # Typ- und Negativfarben anwenden (vom Theme Manager holen)
        type_colors = {}
        negative_color = None
        try:
            # Hole MainWindow reference
            main_window = self
            while main_window.parent() is not None:
                main_window = main_window.parent()
            
            # Hole Farben vom Theme Manager
            if hasattr(main_window, 'theme_manager'):
                type_colors = main_window.theme_manager.get_type_colors()
                negative_color = main_window.theme_manager.get_negative_color()
            else:
                # Fallback via ui_colors
                _uc = ui_colors(self)
                type_colors = _uc.type_colors
                negative_color = _uc.negative
        except Exception as e:
            # Fallback via ui_colors
            _uc = ui_colors(self)
            type_colors = _uc.type_colors
            negative_color = _uc.negative
        
        try:
            apply_tracking_type_colors(self.table, type_colors, negative_color)
            if hasattr(self, '_badge_delegate') and self._badge_delegate is not None:
                self._badge_delegate.set_colors(type_colors)
                self.table.viewport().update()
        except Exception as e:
            logger.debug("apply_tracking_type_colors(self.table, type_colors: %s", e)



    def set_recent_days(self, days: int):
        """Setzt die Anzahl Tage für den Quick-Filter (nur 14 oder 30)."""
        self.recent_days = 30 if int(days) == 30 else 14
        self.chk_recent.setText(f"Nur letzte {self.recent_days} Tage")
        # Wenn der Filter aktiv ist, direkt neu laden
        if self.chk_recent.isChecked():
            self.refresh()

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def add(self):
        dlg=TrackerDialog(self, conn=self.conn, cats=self.cats)
        if dlg.exec() != QDialog.Accepted:
            return
        inp: TrackingInput = dlg.get_input()

        # ── Sparziel-Konfliktprüfung bei negativer Ersparnisse-Buchung ──
        if inp.typ == TYP_SAVINGS and inp.amount < 0:
            conflict = self.model.check_savings_goal_conflict(inp.category, inp.amount)
            if conflict:
                result = self._ask_savings_withdrawal(conflict, inp.amount)
                if result == "cancel":
                    return  # Abbrechen

        self.model.add(inp.d, inp.typ, inp.category, inp.amount, inp.details)
        self.refresh()

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def _ask_savings_withdrawal(self, conflict: dict, amount: float) -> str:
        """Fragt den Benutzer ob eine negative Buchung auf ein Sparziel ein Bezug oder eine Korrektur ist.

        Args:
            conflict: Dict mit goal_id, goal_name, goal_status, current_amount, target_amount
            amount: Der negative Betrag

        Returns:
            'correction' = normale Korrektur (einfach buchen)
            'withdrawal' = Bezug/Entnahme (buchen + Warnung)
            'cancel' = Abbrechen
        """
        goal_name = conflict['goal_name']
        goal_status = conflict['goal_status']
        current = conflict['current_amount']
        target = conflict['target_amount']
        abs_amount = abs(amount)

        if goal_status == "sparend":
            msg = (
                f"Du buchst <b>{format_money(abs_amount)}</b> negativ auf die Kategorie "
                f"mit dem aktiven Sparziel <b>«{goal_name}»</b>.\n\n"
                f"Aktueller Stand: {format_money(current)} / {format_money(target)}\n\n"
                f"<b>Was ist der Grund?</b>"
            )
            box = QMessageBox(self)
            box.setWindowTitle(tr("tracking.title.savings_withdraw"))
            box.setTextFormat(Qt.RichText)
            box.setText(msg)
            box.setIcon(QMessageBox.Question)

            btn_correction = box.addButton(tr("tracking.btn.correction"), QMessageBox.AcceptRole)
            btn_withdrawal = box.addButton(tr("tracking.btn.withdrawal"), QMessageBox.DestructiveRole)
            btn_cancel = box.addButton(tr("btn.cancel"), QMessageBox.RejectRole)

            box.exec()
            clicked = box.clickedButton()
            if clicked == btn_cancel:
                return "cancel"
            elif clicked == btn_withdrawal:
                QMessageBox.warning(
                    self,
                    tr("msg.info"),
                    trf("tracking.msg.goal_still_saving", goal_name=goal_name) + "\n\n" + tr("tracking.tip.unlock_goal_1") + tr("tracking.tip.unlock_goal_2") + tr("tracking.tip.unlock_goal_3")
                )
                return "withdrawal"
            else:
                return "correction"

        elif goal_status == "freigegeben":
            # Bei freigegebenen Zielen: einfach informieren, kein Block
            QMessageBox.information(
                self,
                tr("tracking.title.savings_consumption"),
                f"Diese Buchung wird als Verbrauch vom freigegebenen Sparziel "
                f"<b>«{goal_name}»</b> erfasst.\n\n"
                f"Freigegebener Betrag: {format_money(conflict['current_amount'])}\n"
                f"Entnahme: {format_money(abs_amount)}"
            )
            return "withdrawal"

        return "correction"

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
        month_name = _months_de()[month-1]

        # Kandidaten sammeln: Fixkosten (fixer Betrag) vs. Wiederkehrend (variabel)
        fix_items: list[PendingBooking] = []
        recurring_items: list[PendingBooking] = []
        skipped_existing = 0
        skipped_zero = 0

        last_day = calendar.monthrange(year, month)[1]

        for typ in [TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS]:
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
                QMessageBox.information(self, tr("msg.info"), tr("tracking.msg.already_booked"))
            else:
                QMessageBox.information(
                    self,
                    tr("msg.info"),
                    tr("tracking.msg.no_fix_or_recurring") + "\n" + tr("tracking.tip.set_budget_and_mark_fix"),
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
                QMessageBox.information(self, tr("msg.info"), tr("tracking.msg.no_fixcosts"))
                return
            res = QMessageBox.question(
                self,
                tr("tracking.title.fixcosts"),
                trf("tracking.msg.fixcosts_missing", count=len(fix_items), month=month_name, year=year) + "\n\n" + tr("tracking.msg.show_list_prompt") + tr("tracking.msg.no_means_book_all"),
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
            )
            if res == QMessageBox.Cancel:
                return
            if res == QMessageBox.Yes:
                dlg_list = MissingBookingsDialog(self, items=fix_items, title=tr("tracking.title.fixcosts"))
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
            trf("tracking.msg.fixcosts_result", inserted=inserted, skipped_existing=skipped_existing, skipped_zero=skipped_zero, skipped_zero_book=skipped_zero_book),
        )
        self.refresh()

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def edit(self):
        row_id = self._selected_id()
        if row_id is None:
            QMessageBox.information(self, tr("msg.info"), tr("msg.no_selection"))
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

    # --- i18n helper: Typ aus Filter (Anzeige -> DB) ---
    def _current_filter_typ_db(self) -> str:
        # userData ist der DB-Schlüssel (sprachunabhängig)
        data = self.filter_typ.currentData()
        if data is not None:
            return data if data else "Alle"
        # Fallback für Index-0 (leer = Alle)
        return "Alle" if self.filter_typ.currentIndex() == 0 else self.filter_typ.currentText()

    def _is_all_typ(self) -> bool:
        return self._current_filter_typ_db() == "Alle"

    def delete(self):
        row_id = self._selected_id()
        if row_id is None:
            QMessageBox.information(self, tr("msg.info"), tr("msg.no_selection"))
            return
        r = self.table.currentRow()
        summary = f"{self.table.item(r,0).text()} | {self.table.item(r,1).text()} | {self.table.item(r,2).text()} | {self.table.item(r,3).text()}"
        if QMessageBox.question(self, tr("msg.delete_entry"), trf("tracking.msg.delete_confirm", summary=summary)) != QMessageBox.Yes:
            return
        self.model.delete(row_id)
        self.refresh()
