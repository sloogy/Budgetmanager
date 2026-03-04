"""Rechte Seitenleiste der Finanzübersicht: Filter + Transaktionsliste.

Extrahiert aus overview_tab.py (v1.0.5 – Patch C: Aufspaltung).
Verantwortlich für:
- Filter-Formular (Datum, Typ, Kategorie, Tag, Suche, Betrag, Flags)
- Transaktions-Tabelle
- Laden + Filtern der Buchungen

Schnittstelle zu OverviewTab:
    panel = OverviewRightPanel(conn, track, categories, tags, parent=self)
    panel.load(date_from, date_to, categories_list, tags_list)
    panel.typ_filter_changed.connect(...)
"""
from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)

from datetime import date, timedelta

from PySide6.QtCore import Qt, QDate, Signal
from PySide6.QtGui import QDoubleValidator
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel, QComboBox,
    QFrame, QTabWidget, QLineEdit, QCheckBox, QSpinBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView, QDateEdit,
)

from model.tracking_model import TrackingModel, TrackingRow
from model.category_model import CategoryModel
from model.tags_model import TagsModel
from utils.i18n import tr, trf
from utils.money import format_money as format_chf, currency_header
from views.ui_colors import ui_colors

# Normalisierung für Typ-Strings (Alias-Mapping)
from model.typ_constants import TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS, normalize_typ

from model.typ_constants import normalize_typ as _norm_typ, TYP_INCOME, TYP_EXPENSES, TYP_SAVINGS


def _to_qdate(d: date) -> QDate:
    return QDate(d.year, d.month, d.day)


def _typ_items() -> list[tuple[str, str]]:
    """Gibt (Anzeigetext, DB-Schlüssel) zurück. DB-Schlüssel leer = 'Alle'."""
    from utils.i18n import display_typ
    return [
        (tr("lbl.all"), ""),
        (display_typ(TYP_EXPENSES), TYP_EXPENSES),
        (display_typ(TYP_INCOME),   TYP_INCOME),
        (display_typ(TYP_SAVINGS),  TYP_SAVINGS),
    ]


class OverviewRightPanel(QWidget):
    """Rechtes Panel: Filter-Formular + Transaktionsliste als Tab-Widget."""

    # Emittiert wenn Typ-Filter geändert – OverviewTab kann darauf reagieren
    typ_filter_changed = Signal(str)
    # Emittiert wenn Filter zurückgesetzt
    filters_reset = Signal()

    def __init__(self, conn: sqlite3.Connection,
                 track: TrackingModel,
                 categories: CategoryModel,
                 tags: TagsModel,
                 parent=None):
        super().__init__(parent)
        self.conn = conn
        self.track = track
        self.categories = categories
        self.tags = tags
        self._tag_name_to_id: dict[str, int] = {}
        self._cat_tree: dict[str, dict] = {}
        self._setup_ui()

    # ── Aufbau ──────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)
        layout.setSpacing(0)

        tabs = QTabWidget()
        tabs.addTab(self._create_filter_tab(), tr("tab.filter"))
        tabs.addTab(self._create_transactions_tab(), tr("tab.transactions"))
        layout.addWidget(tabs)

    def _create_filter_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(8, 8, 8, 8)

        form = QGridLayout()
        form.setHorizontalSpacing(8)
        form.setVerticalSpacing(5)

        # Datum
        form.addWidget(QLabel(tr("lbl.from")), 0, 0)
        self.date_from = QDateEdit()
        self.date_from.setCalendarPopup(True)
        self.date_from.setDate(_to_qdate(date.today() - timedelta(days=30)))
        form.addWidget(self.date_from, 0, 1)

        form.addWidget(QLabel(tr("lbl.to")), 1, 0)
        self.date_to = QDateEdit()
        self.date_to.setCalendarPopup(True)
        self.date_to.setDate(_to_qdate(date.today()))
        form.addWidget(self.date_to, 1, 1)

        # Typ
        form.addWidget(QLabel(tr("lbl.type")), 2, 0)
        self.typ_combo = QComboBox()
        for _disp, _key in _typ_items():
            self.typ_combo.addItem(_disp, _key)
        self.typ_combo.currentTextChanged.connect(
            lambda t: self.typ_filter_changed.emit(t)
        )
        form.addWidget(self.typ_combo, 2, 1)

        # Kategorie
        form.addWidget(QLabel(tr("lbl.category")), 3, 0)
        self.category_combo = QComboBox()
        self.category_combo.addItem(tr("tracking.filter.all_categories"))
        form.addWidget(self.category_combo, 3, 1)

        # Tag
        form.addWidget(QLabel(tr("lbl.day")), 4, 0)
        self.tag_combo = QComboBox()
        self.tag_combo.addItem(tr("tracking.filter.all_tags"))
        form.addWidget(self.tag_combo, 4, 1)

        # Suche
        form.addWidget(QLabel(tr("lbl.search")), 5, 0)
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText(tr("overview.search.placeholder"))
        form.addWidget(self.search_edit, 5, 1)

        # Betrag
        form.addWidget(QLabel(f"Min {currency_header()}:"), 6, 0)
        self.min_amount = QLineEdit()
        self.min_amount.setPlaceholderText(tr("overview.amount.min_placeholder"))
        self.min_amount.setValidator(QDoubleValidator(0.0, 1e12, 2, self))
        form.addWidget(self.min_amount, 6, 1)

        form.addWidget(QLabel(f"Max {currency_header()}:"), 7, 0)
        self.max_amount = QLineEdit()
        self.max_amount.setPlaceholderText(tr("overview.amount.max_placeholder"))
        self.max_amount.setValidator(QDoubleValidator(0.0, 1e12, 2, self))
        form.addWidget(self.max_amount, 7, 1)

        # Flags
        self.only_fix = QCheckBox(tr("chk.only_fixed"))
        form.addWidget(self.only_fix, 8, 0, 1, 2)
        self.only_recurring = QCheckBox(tr("chk.only_recurring"))
        form.addWidget(self.only_recurring, 9, 0, 1, 2)

        # Limit
        form.addWidget(QLabel(tr("lbl.limit")), 10, 0)
        self.limit_spin = QSpinBox()
        self.limit_spin.setRange(10, 500)
        self.limit_spin.setValue(50)
        form.addWidget(self.limit_spin, 10, 1)

        layout.addLayout(form)

        self.btn_reset = QPushButton(tr("tab_ui.filter_zuruecksetzen"))
        self.btn_reset.clicked.connect(self._reset_filters)
        layout.addWidget(self.btn_reset)
        layout.addStretch()
        return widget

    def _create_transactions_tab(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self.lbl_count = QLabel(trf("overview.count.transactions", n=0))
        self.lbl_count.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(self.lbl_count)

        self.tbl_transactions = QTableWidget()
        self.tbl_transactions.setColumnCount(6)
        self.tbl_transactions.setHorizontalHeaderLabels([
            tr("header.date"), tr("header.type"), tr("header.category"), tr("header.amount"), tr("header.description"), tr("header.tags")
        ])

        header = self.tbl_transactions.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.Stretch)
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)
        header.setMinimumSectionSize(50)

        self.tbl_transactions.setAlternatingRowColors(True)
        self.tbl_transactions.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.tbl_transactions.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.tbl_transactions.verticalHeader().setVisible(False)
        layout.addWidget(self.tbl_transactions)
        return widget

    # ── Hilfsmethoden ───────────────────────────────────────────────────────

    def _reset_filters(self) -> None:
        self.typ_combo.setCurrentIndex(0)
        self.category_combo.setCurrentIndex(0)
        self.tag_combo.setCurrentIndex(0)
        self.search_edit.clear()
        self.min_amount.clear()
        self.max_amount.clear()
        self.only_fix.setChecked(False)
        self.only_recurring.setChecked(False)
        self.limit_spin.setValue(50)
        self.filters_reset.emit()

    def update_categories(self, typ_filter: str, cat_names: list[str]) -> None:
        """Kategorien-Dropdown aktualisieren (wird vom OverviewTab gerufen)."""
        from PySide6.QtCore import QSignalBlocker
        with QSignalBlocker(self.category_combo):
            self.category_combo.clear()
            self.category_combo.addItem(tr("tracking.filter.all_categories"))
            for name in cat_names:
                self.category_combo.addItem(name)

    def update_tags(self, tag_map: dict[str, int]) -> None:
        """Tag-Dropdown aktualisieren."""
        from PySide6.QtCore import QSignalBlocker
        self._tag_name_to_id = tag_map
        with QSignalBlocker(self.tag_combo):
            self.tag_combo.clear()
            self.tag_combo.addItem(tr("tracking.filter.all_tags"))
            for name in tag_map:
                self.tag_combo.addItem(name)

    def set_typ(self, typ_db_or_display: str) -> None:
        """Typ-Filter setzen (z.B. vom KPI-Card-Klick).

        Akzeptiert DB-Schlüssel ('Ausgaben', 'Einkommen', 'Ersparnisse')
        ODER Anzeigename – per normalize_typ() wird auf DB-Schlüssel normalisiert.
        """
        from PySide6.QtCore import QSignalBlocker
        from model.typ_constants import normalize_typ
        db_key = normalize_typ(typ_db_or_display)
        # Suche per userData (DB-Schlüssel) – sprachunabhängig
        idx = self.typ_combo.findData(db_key)
        if idx < 0:
            # Fallback: Textsuche (rückwärtskompatibel)
            idx = self.typ_combo.findText(typ_db_or_display)
        if idx >= 0:
            with QSignalBlocker(self.typ_combo):
                self.typ_combo.setCurrentIndex(idx)

    # ── Daten laden ─────────────────────────────────────────────────────────

    def load(self, date_from: date, date_to: date,
             cat_tree: dict | None = None) -> None:
        """Transaktionen laden und filtern.
        
        cat_tree: dict {(typ, cat): set_of_descendants} für Hierarchie-Filter.
        """
        if cat_tree:
            self._cat_tree = cat_tree

        # userData = DB-Schlüssel (sprachunabhängig); leer = "Alle"
        _typ_data = self.typ_combo.currentData()
        typ_filter = _typ_data if _typ_data else ""
        cat_filter = self.category_combo.currentText()
        tag_filter = self.tag_combo.currentText()
        search_text = self.search_edit.text().strip().lower()

        try:
            min_amt = float(self.min_amount.text()) if self.min_amount.text() else None
        except Exception:
            min_amt = None
        try:
            max_amt = float(self.max_amount.text()) if self.max_amount.text() else None
        except Exception:
            max_amt = None

        only_fix = self.only_fix.isChecked()
        only_rec = self.only_recurring.isChecked()
        limit = self.limit_spin.value()

        rows = self.track.get_entries_in_range(date_from, date_to)

        filtered = []
        for r in rows:
            if typ_filter and _norm_typ(r.typ) != typ_filter:
                continue
            if cat_filter != tr("tracking.filter.all_categories"):
                # Hierarchie-Filter: erlaubt Haupt- und Unterkategorien
                allowed = self._cat_tree.get((r.typ, cat_filter))
                if allowed is not None and r.category not in allowed:
                    continue
            if tag_filter != tr("tracking.filter.all_tags"):
                tag_id = self._tag_name_to_id.get(tag_filter)
                if tag_id:
                    entry_tags = self.tags.get_tags_for_entry(r.id)
                    if tag_id not in [t["id"] for t in entry_tags]:
                        continue
            if search_text and search_text not in r.description.lower():
                continue
            amt = abs(r.amount)
            if min_amt is not None and amt < min_amt:
                continue
            if max_amt is not None and amt > max_amt:
                continue
            if only_fix or only_rec:
                try:
                    is_fix, is_rec, _day = self.categories.get_flags(r.typ, r.category)
                    if only_fix and not is_fix:
                        continue
                    if only_rec and not is_rec:
                        continue
                except Exception as e:
                    logger.debug("get_flags failed for %s %s: %s", r.typ, r.category, e)
                    continue
            filtered.append(r)

        filtered = filtered[:limit]
        self._display(filtered, limit)

    def _display(self, rows: list[TrackingRow], limit: int) -> None:
        self.tbl_transactions.setRowCount(len(rows))
        for i, r in enumerate(rows):
            self.tbl_transactions.setItem(i, 0, QTableWidgetItem(str(r.date)))
            self.tbl_transactions.setItem(i, 1, QTableWidgetItem(r.typ))
            self.tbl_transactions.setItem(i, 2, QTableWidgetItem(r.category))
            amt = QTableWidgetItem(format_chf(r.amount))
            amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.tbl_transactions.setItem(i, 3, amt)
            self.tbl_transactions.setItem(i, 4, QTableWidgetItem(r.description))
            try:
                tags = self.tags.get_tags_for_entry(r.id)
                tag_names = ", ".join(t["name"] for t in tags)
            except Exception:
                tag_names = ""
            self.tbl_transactions.setItem(i, 5, QTableWidgetItem(tag_names))
        self.tbl_transactions.resizeRowsToContents()
        self.lbl_count.setText(trf("overview.count.transactions_limit", n=len(rows), limit=limit))
