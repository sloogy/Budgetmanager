from __future__ import annotations
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
import logging

logger = logging.getLogger(__name__)

from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QLabel,
    QAbstractItemView,
    QHeaderView,
    QCheckBox,
    QFrame,
    QComboBox,
)

from views.missing_bookings_dialog import PendingBooking
from utils.money import (
    format_short as _fmt_chf,
    parse_money as _parse_chf,
    currency_header,
)
from views.ui_colors import ui_colors
from utils.i18n import tr, trf, display_typ, db_typ_from_display


class SortablePendingItem:
    """Wrapper für PendingBooking mit Sortierinformationen"""

    def __init__(
        self, booking: PendingBooking, kind: str, is_fix: bool, is_recurring: bool
    ):
        self.booking = booking
        self.kind = kind
        self.is_fix = is_fix
        self.is_recurring = is_recurring

    @property
    def due_date(self) -> date:
        return self.booking.d

    @property
    def is_overdue(self) -> bool:
        return self.due_date < date.today()

    @property
    def days_overdue(self) -> int:
        """Tage überfällig (positiv = überfällig, negativ = in Zukunft)"""
        return (date.today() - self.due_date).days

    @property
    def sort_key(self) -> tuple:
        """Sortierung:
        1. Fälligkeitsdatum
        2. Echte Fixkosten (fix+repeat) vor variablen Fix-/Wiederkehrend-Posten
        """
        if self.is_fix and self.is_recurring:
            priority = 0
        elif self.is_fix:
            priority = 1
        else:
            priority = 2
        return (self.due_date, priority, self.booking.category)

    @property
    def should_be_preselected(self) -> bool:
        """Vorauswahl: Überfällig (bis 60 Tage) = angehakt, Zukunft = nicht angehakt"""
        if not (self.is_fix or self.is_recurring):
            return False  # Optionale Budgetposten nie automatisch vorauswählen.
        if not self.is_overdue:
            return False  # In der Zukunft: nicht angehakt
        # Überfällig: nur wenn <= 60 Tage
        return self.days_overdue <= 60


class RecurringBookingsDialog(QDialog):
    """Dialog für Fixkosten + wiederkehrende (variable) Buchungen.

    Verbesserungen v2.1:
    - Sortierung nach Fälligkeitsdatum, dann Fix+Wiederkehrend vor nur Wiederkehrend
    - Überfällige (30-60 Tage) werden automatisch vorausgewählt
    - Zukünftige sind nicht angehakt
    - Farbcodierung für Status
    """

    def __init__(
        self,
        parent=None,
        *,
        fix_items: list[PendingBooking],
        recurring_items: list[PendingBooking],
        optional_items: list[PendingBooking] | None = None,
        title: str | None = None,
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title or tr("booking.title_fix_recurring"))
        self.setMinimumSize(950, 500)

        # Items mit Sortierinformationen versehen.
        # Flags kommen jetzt direkt von der Buchung (PendingBooking.is_fix/is_recurring).
        self._items: list[SortablePendingItem] = []
        seen: set[tuple[str, str]] = set()

        def _kind_label(it) -> str:
            f = bool(getattr(it, "is_fix", False))
            r = bool(getattr(it, "is_recurring", False))
            if f and r:
                return tr("booking.kind_real_fixed")
            if f:
                return tr("booking.kind_variable_fixed")
            if not r:
                return tr("booking.kind_optional")
            return tr("booking.kind_variable_recurring")

        for it in list(fix_items) + list(recurring_items) + list(optional_items or []):
            key = (it.category, it.typ)
            if key in seen:
                continue
            seen.add(key)
            f = bool(getattr(it, "is_fix", False))
            r = bool(getattr(it, "is_recurring", False))
            self._items.append(
                SortablePendingItem(it, _kind_label(it), is_fix=f, is_recurring=r)
            )

        # Nach sort_key sortieren
        self._items.sort(key=lambda x: x.sort_key)

        self._setup_ui()
        self._fill()

    def _setup_ui(self):
        """Erstellt die UI"""
        root = QVBoxLayout(self)
        root.setSpacing(8)

        # Info-Header
        info_frame = QFrame()
        info_frame.setFrameStyle(QFrame.StyledPanel)
        info_layout = QVBoxLayout(info_frame)

        self.lbl = QLabel(
            tr(
                "auto.views_recurring_bookings_dialog.128_b_fixkosten_b_sind_fix_und_nicht_ed_38adb145"
            )
        )
        self.lbl.setWordWrap(True)
        self.lbl.setTextFormat(Qt.RichText)
        info_layout.addWidget(self.lbl)

        _c = ui_colors(self)
        hint = QLabel(
            trf(
                "auto.views_recurring_bookings_dialog.137_span_style_color_value_0_ueberfaell_81b0f0f3",
                value_0=(_c.negative),
                value_1=(_c.ok),
            )
        )
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        info_layout.addWidget(hint)

        root.addWidget(info_frame)

        # Status-Zeile
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel(tr("lbl.type")))
        self.filter_typ = QComboBox()
        self.filter_typ.addItem(tr("typ.Alle"), "")
        self.filter_typ.addItem(display_typ(TYP_EXPENSES), TYP_EXPENSES)
        self.filter_typ.addItem(display_typ(TYP_INCOME), TYP_INCOME)
        self.filter_typ.addItem(display_typ(TYP_SAVINGS), TYP_SAVINGS)
        self.filter_typ.setToolTip(tr("booking.filter_type_tip"))
        self.filter_typ.currentIndexChanged.connect(lambda _i: self._apply_filters())
        status_layout.addWidget(self.filter_typ)

        status_layout.addWidget(QLabel(tr("booking.filter_kind_label")))
        self.filter_kind = QComboBox()
        self.filter_kind.addItem(tr("booking.filter_kind_all"), "")
        self.filter_kind.addItem(tr("booking.kind_real_fixed"), "real_fixed")
        self.filter_kind.addItem(tr("booking.kind_variable_fixed"), "fix_only")
        self.filter_kind.addItem(
            tr("booking.kind_variable_recurring"), "recurring_only"
        )
        self.filter_kind.addItem(tr("booking.kind_optional"), "optional")
        self.filter_kind.setToolTip(tr("booking.filter_kind_tip"))
        self.filter_kind.currentIndexChanged.connect(lambda _i: self._apply_filters())
        status_layout.addWidget(self.filter_kind)
        status_layout.addWidget(QLabel("|"))
        self.lbl_total = QLabel(trf("lbl.lbl_total", n=0))
        self.lbl_overdue = QLabel(tr("dlg.ueberfaellig_0"))
        self.lbl_overdue.setStyleSheet(f"color: {_c.negative}; font-weight: bold;")
        self.lbl_upcoming = QLabel(trf("lbl.lbl_pending", n=0))
        self.lbl_upcoming.setStyleSheet(f"color: {_c.ok};")
        self.lbl_selected = QLabel(tr("dlg.ausgewaehlt_0"))
        self.lbl_selected.setStyleSheet("font-weight: bold;")

        status_layout.addWidget(self.lbl_total)
        status_layout.addWidget(QLabel("|"))
        status_layout.addWidget(self.lbl_overdue)
        status_layout.addWidget(QLabel("|"))
        status_layout.addWidget(self.lbl_upcoming)
        status_layout.addWidget(QLabel("|"))
        status_layout.addWidget(self.lbl_selected)
        status_layout.addStretch()
        root.addLayout(status_layout)

        # Tabelle
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                tr("btn.book"),
                tr("auto.views_recurring_bookings_dialog.169_art_e71cc758"),
                tr("header.date"),
                tr("lbl.status"),
                tr("header.type"),
                tr("header.category"),
                currency_header(),
                tr("lbl.description"),
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)

        # Spaltenbreiten
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # Buchen
        header.setSectionResizeMode(1, QHeaderView.Fixed)  # Art
        header.setSectionResizeMode(2, QHeaderView.Fixed)  # Datum
        header.setSectionResizeMode(3, QHeaderView.Fixed)  # Status
        header.setSectionResizeMode(4, QHeaderView.Fixed)  # Typ
        header.setSectionResizeMode(5, QHeaderView.Stretch)  # Kategorie
        header.setSectionResizeMode(6, QHeaderView.Fixed)  # Betrag
        header.setSectionResizeMode(7, QHeaderView.Stretch)  # Bemerkung

        self.table.setColumnWidth(0, 50)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 90)
        self.table.setColumnWidth(3, 100)
        self.table.setColumnWidth(4, 90)
        self.table.setColumnWidth(6, 100)

        root.addWidget(self.table)

        # Buttons
        row_btns = QHBoxLayout()

        self.btn_all = QPushButton(tr("btn.all"))
        self.btn_none = QPushButton(tr("btn.none"))
        self.btn_overdue_only = QPushButton(tr("dlg.nur_ueberfaellige"))
        self.btn_fix_only = QPushButton(tr("booking.btn_real_fixed_only"))
        self.btn_ok = QPushButton(tr("btn.book"))
        self.btn_ok.setStyleSheet(f"""
            QPushButton {{
                background-color: {_c.ok};
                color: white;
                padding: 8px 16px;
                font-weight: bold;
            }}
            QPushButton:hover {{
                opacity: 0.9;
            }}
        """)
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        row_btns.addWidget(self.btn_all)
        row_btns.addWidget(self.btn_none)
        row_btns.addWidget(self.btn_overdue_only)
        row_btns.addStretch(1)
        row_btns.addWidget(self.btn_fix_only)
        row_btns.addWidget(self.btn_ok)
        row_btns.addWidget(self.btn_cancel)

        root.addLayout(row_btns)

        # Verbindungen
        self.btn_all.clicked.connect(lambda: self._set_all(True))
        self.btn_none.clicked.connect(lambda: self._set_all(False))
        self.btn_overdue_only.clicked.connect(self._select_overdue_only)
        self.btn_fix_only.clicked.connect(self._accept_fix_only)
        self.btn_ok.clicked.connect(self.accept)
        self.btn_cancel.clicked.connect(self.reject)

    def _fill(self) -> None:
        """Füllt die Tabelle mit den Items"""
        self.table.setRowCount(0)

        for item in self._items:
            self._add_row(item)

        self.table.itemChanged.connect(lambda _it: self._update_status())
        self._apply_filters()
        self._update_status()

    def _add_row(self, item: SortablePendingItem) -> None:
        """Fügt eine Zeile hinzu"""
        r = self.table.rowCount()
        self.table.insertRow(r)

        it = item.booking
        is_overdue = item.is_overdue
        days = item.days_overdue

        # Checkbox - Vorauswahl basierend auf Überfälligkeit
        chk = QTableWidgetItem("✓")
        chk.setFlags(Qt.ItemIsEnabled | Qt.ItemIsUserCheckable)
        chk.setCheckState(Qt.Checked if item.should_be_preselected else Qt.Unchecked)
        chk.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, 0, chk)

        # Art (Fix / Wiederkehrend / Fix+Wiederkehrend)
        c = ui_colors(self)
        if item.is_fix and item.is_recurring:
            art_text = tr("booking.kind_real_fixed_short")
            art_color = QColor(ui_colors(self).accent)  # Buchungsart-Akzent
        elif item.is_fix:
            art_text = tr("booking.kind_variable_fixed_short")
            art_color = QColor(c.accent)
        elif item.is_recurring:
            art_text = tr("booking.kind_variable_recurring_short")
            art_color = QColor(c.type_color(tr("typ.Ersparnisse")))
        else:
            art_text = tr("booking.kind_optional_short")
            art_color = QColor(c.text_dim)

        art_item = QTableWidgetItem(art_text)
        art_item.setForeground(art_color)
        self.table.setItem(r, 1, art_item)

        # Datum
        date_item = QTableWidgetItem(it.d.strftime("%d.%m.%Y"))
        date_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, 2, date_item)

        # Status
        if is_overdue:
            if days > 30:
                status_text = f"⚠️ {days} Tage"
                status_color = QColor(c.danger)
            else:
                status_text = f"🔴 {days} Tage"
                status_color = QColor(c.negative)
        elif days == 0:
            status_text = "📅 Heute"
            status_color = QColor(c.warning)
        else:
            status_text = f"🟢 in {-days} T."
            status_color = QColor(c.ok)

        status_item = QTableWidgetItem(status_text)
        status_item.setForeground(status_color)
        status_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, 3, status_item)

        # Typ
        typ_item = QTableWidgetItem(it.typ)
        typ_item.setTextAlignment(Qt.AlignCenter)
        self.table.setItem(r, 4, typ_item)

        # Kategorie
        self.table.setItem(r, 5, QTableWidgetItem(it.category))

        # Betrag editierbar – nur echte Fixkosten (fix UND wiederkehrend) sind gesperrt
        amt = QTableWidgetItem(_fmt_chf(float(it.amount)))
        amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if item.is_fix and item.is_recurring:
            amt.setFlags(amt.flags() & ~Qt.ItemIsEditable)
        else:
            amt.setFlags(amt.flags() | Qt.ItemIsEditable)
        self.table.setItem(r, 6, amt)

        # Bemerkung (immer editierbar)
        det = QTableWidgetItem(it.details or "")
        det.setFlags(det.flags() | Qt.ItemIsEditable)
        self.table.setItem(r, 7, det)

        # Hintergrundfarbe für stark überfällige
        if is_overdue and days > 30:
            for col in range(self.table.columnCount()):
                cell = self.table.item(r, col)
                if cell:
                    cell.setBackground(QColor(c.error_bg))

    def _update_status(self):
        """Aktualisiert die Statusanzeige"""
        visible_items = [
            it for row, it in enumerate(self._items) if not self.table.isRowHidden(row)
        ]
        total = len(visible_items)
        overdue = sum(1 for it in visible_items if it.is_overdue)
        upcoming = total - overdue
        selected = self._count_selected()

        self.lbl_total.setText(trf("lbl.lbl_total", n=total))
        self.lbl_overdue.setText(trf("dlg.ueberfaellig_overdue", overdue=overdue))
        self.lbl_upcoming.setText(trf("lbl.lbl_pending", n=upcoming))
        self.lbl_selected.setText(trf("dlg.ausgewaehlt_selected", selected=selected))

    def _count_selected(self) -> int:
        """Zählt ausgewählte Items"""
        count = 0
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            chk = self.table.item(r, 0)
            if chk and chk.checkState() == Qt.Checked:
                count += 1
        return count

    def _current_type_filter(self) -> str:
        data = self.filter_typ.currentData() if hasattr(self, "filter_typ") else ""
        return str(data or "")

    def _current_kind_filter(self) -> str:
        data = self.filter_kind.currentData() if hasattr(self, "filter_kind") else ""
        return str(data or "")

    @staticmethod
    def _matches_kind_filter(item: SortablePendingItem, wanted: str) -> bool:
        if not wanted:
            return True
        if wanted == "real_fixed":
            return item.is_fix and item.is_recurring
        if wanted == "fix_only":
            return item.is_fix and not item.is_recurring
        if wanted == "recurring_only":
            return item.is_recurring and not item.is_fix
        if wanted == "optional":
            return not item.is_fix and not item.is_recurring
        return True

    def _apply_filters(self) -> None:
        """Blendet Kandidaten nach Konto/Typ und Buchungsart ein oder aus."""
        wanted_type = self._current_type_filter()
        wanted_kind = self._current_kind_filter()
        for row, item in enumerate(self._items):
            hide_by_type = bool(wanted_type and item.booking.typ != wanted_type)
            hide_by_kind = not self._matches_kind_filter(item, wanted_kind)
            self.table.setRowHidden(row, hide_by_type or hide_by_kind)
        self._update_status()

    def _apply_type_filter(self) -> None:
        """Kompatibilitätsalias für ältere Tests/Aufrufer."""
        self._apply_filters()

    def _set_all(self, checked: bool) -> None:
        """Setzt alle Checkboxen"""
        state = Qt.Checked if checked else Qt.Unchecked
        for r in range(self.table.rowCount()):
            if self.table.isRowHidden(r):
                continue
            it = self.table.item(r, 0)
            if it is not None:
                it.setCheckState(state)
        self._update_status()

    def _select_overdue_only(self) -> None:
        """Wählt nur überfällige aus"""
        for r, item in enumerate(self._items):
            if self.table.isRowHidden(r):
                continue
            chk = self.table.item(r, 0)
            if chk is not None:
                # Nur überfällige (max 60 Tage) auswählen
                should_select = item.is_overdue and item.days_overdue <= 60
                chk.setCheckState(Qt.Checked if should_select else Qt.Unchecked)
        self._update_status()

    def _accept_fix_only(self) -> None:
        """Bucht nur echte Fixkosten (fix UND wiederkehrend) ohne Betragsedit.

        Fix-only Kategorien wie Franchise/Selbstbehalt bleiben bewusst außen vor:
        sie sind variabel, müssen editierbar bleiben und sollen nicht durch den
        Schnellbutton versehentlich mit dem Restbetrag gebucht werden.
        """
        for r, item in enumerate(self._items):
            if self.table.isRowHidden(r):
                continue
            chk = self.table.item(r, 0)
            if chk is not None:
                chk.setCheckState(
                    Qt.Checked if (item.is_fix and item.is_recurring) else Qt.Unchecked
                )
        self._update_status()
        self.accept()

    def selected_items(self) -> list[PendingBooking]:
        """Gibt die ausgewählten Items zurück"""
        out: list[PendingBooking] = []

        for r, item in enumerate(self._items):
            if self.table.isRowHidden(r):
                continue
            chk = self.table.item(r, 0)
            if chk is None or chk.checkState() != Qt.Checked:
                continue

            base = item.booking

            # Amount/Details ggf. vom UI übernehmen
            amt_item = self.table.item(r, 6)
            det_item = self.table.item(r, 7)
            amt = _parse_chf(amt_item.text() if amt_item else "")
            det = det_item.text() if det_item else (base.details or "")

            out.append(
                PendingBooking(
                    d=base.d,
                    typ=base.typ,
                    category=base.category,
                    amount=float(amt),
                    details=str(det or ""),
                    source=getattr(base, "source", "manual"),
                    is_fix=getattr(base, "is_fix", False),
                    is_recurring=getattr(base, "is_recurring", False),
                    budget=getattr(base, "budget", 0.0),
                    booked=getattr(base, "booked", 0.0),
                )
            )
        return out
