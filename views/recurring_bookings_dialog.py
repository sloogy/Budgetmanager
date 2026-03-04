from __future__ import annotations
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
)

from views.missing_bookings_dialog import PendingBooking
from utils.money import format_short as _fmt_chf, parse_money as _parse_chf, currency_header
from views.ui_colors import ui_colors
from utils.i18n import tr, trf, display_typ, db_typ_from_display


class SortablePendingItem:
    """Wrapper für PendingBooking mit Sortierinformationen"""
    def __init__(self, booking: PendingBooking, kind: str, is_fix: bool, is_recurring: bool):
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
        2. Fix+Wiederkehrend (0) vor nur Fix (1) vor nur Wiederkehrend (2)
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
        title: str = "Fixkosten & Wiederkehrende",
    ):
        super().__init__(parent)
        self.setModal(True)
        self.setWindowTitle(title)
        self.setMinimumSize(950, 500)

        # Items mit Sortierinformationen versehen
        self._items: list[SortablePendingItem] = []
        
        # Fix items (is_fix=True)
        for it in fix_items:
            # Prüfe ob auch wiederkehrend
            is_recurring = any(r.category == it.category and r.typ == it.typ for r in recurring_items)
            self._items.append(SortablePendingItem(it, "Fix", is_fix=True, is_recurring=is_recurring))
        
        # Recurring items (nur wenn nicht schon als Fix erfasst)
        fix_cats = {(it.category, it.typ) for it in fix_items}
        for it in recurring_items:
            if (it.category, it.typ) not in fix_cats:
                self._items.append(SortablePendingItem(it, tr("lbl.recurring"), is_fix=False, is_recurring=True))
        
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
            "<b>Fixkosten</b> sind fix und nicht editierbar. "
            "<b>Wiederkehrende</b> (ohne Fixkosten) sind variabel: Betrag anpassen und auswählen, was gebucht werden soll."
        )
        self.lbl.setWordWrap(True)
        self.lbl.setTextFormat(Qt.RichText)
        info_layout.addWidget(self.lbl)
        
        _c = ui_colors(self)
        hint = QLabel(
            f"💡 <span style='color:{_c.negative};'>Überfällige</span> Buchungen sind vorausgewählt. "
            f"<span style='color:{_c.ok};'>Zukünftige</span> können manuell ausgewählt werden."
        )
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        info_layout.addWidget(hint)
        
        root.addWidget(info_frame)
        
        # Status-Zeile
        status_layout = QHBoxLayout()
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
        self.table.setHorizontalHeaderLabels([
            "Buchen", "Art", "Datum", "Status", "Typ", tr("header.category"), currency_header(), tr("lbl.description")
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        
        # Spaltenbreiten
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)     # Buchen
        header.setSectionResizeMode(1, QHeaderView.Fixed)     # Art
        header.setSectionResizeMode(2, QHeaderView.Fixed)     # Datum
        header.setSectionResizeMode(3, QHeaderView.Fixed)     # Status
        header.setSectionResizeMode(4, QHeaderView.Fixed)     # Typ
        header.setSectionResizeMode(5, QHeaderView.Stretch)   # Kategorie
        header.setSectionResizeMode(6, QHeaderView.Fixed)     # Betrag
        header.setSectionResizeMode(7, QHeaderView.Stretch)   # Bemerkung
        
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
        self.btn_fix_only = QPushButton("Nur Fixkosten")
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
            art_text = "Fix + Wied."
            art_color = QColor(ui_colors(self).accent)  # Buchungsart-Akzent
        elif item.is_fix:
            art_text = "Fix"
            art_color = QColor(c.accent)
        else:
            art_text = tr("lbl.recurring")
            art_color = QColor(c.type_color(tr("typ.Ersparnisse")))
        
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

        # Betrag (editierbar nur für nicht-Fix)
        amt = QTableWidgetItem(_fmt_chf(float(it.amount)))
        amt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if item.is_fix:
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
        total = len(self._items)
        overdue = sum(1 for it in self._items if it.is_overdue)
        upcoming = total - overdue
        selected = self._count_selected()
        
        self.lbl_total.setText(trf("lbl.lbl_total", n=total))
        self.lbl_overdue.setText(trf("dlg.ueberfaellig_overdue"))
        self.lbl_upcoming.setText(trf("lbl.lbl_pending", n=upcoming))
        self.lbl_selected.setText(trf("dlg.ausgewaehlt_selected"))

    def _count_selected(self) -> int:
        """Zählt ausgewählte Items"""
        count = 0
        for r in range(self.table.rowCount()):
            chk = self.table.item(r, 0)
            if chk and chk.checkState() == Qt.Checked:
                count += 1
        return count

    def _set_all(self, checked: bool) -> None:
        """Setzt alle Checkboxen"""
        state = Qt.Checked if checked else Qt.Unchecked
        for r in range(self.table.rowCount()):
            it = self.table.item(r, 0)
            if it is not None:
                it.setCheckState(state)
        self._update_status()

    def _select_overdue_only(self) -> None:
        """Wählt nur überfällige aus"""
        for r, item in enumerate(self._items):
            chk = self.table.item(r, 0)
            if chk is not None:
                # Nur überfällige (max 60 Tage) auswählen
                should_select = item.is_overdue and item.days_overdue <= 60
                chk.setCheckState(Qt.Checked if should_select else Qt.Unchecked)
        self._update_status()

    def _accept_fix_only(self) -> None:
        """Wählt nur Fixkosten aus und akzeptiert"""
        for r, item in enumerate(self._items):
            chk = self.table.item(r, 0)
            if chk is not None:
                chk.setCheckState(Qt.Checked if item.is_fix else Qt.Unchecked)
        self._update_status()
        self.accept()

    def selected_items(self) -> list[PendingBooking]:
        """Gibt die ausgewählten Items zurück"""
        out: list[PendingBooking] = []

        for r, item in enumerate(self._items):
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
                )
            )
        return out
