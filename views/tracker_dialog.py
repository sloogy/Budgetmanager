from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
from dataclasses import dataclass
from datetime import date, datetime
import sqlite3

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QFormLayout, QHBoxLayout, QPushButton, QComboBox,
    QLineEdit, QDateEdit, QVBoxLayout, QMessageBox, QLabel, QCompleter,
    QListWidget, QListWidgetItem
)

from model.category_model import CategoryModel
from model.tracking_model import TrackingModel
from model.tags_model import TagsModel
from settings import Settings
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS, normalize_typ
from utils.money import parse_money, currency_header
from utils.i18n import tr, trf, display_typ, db_typ_from_display

def parse_amount(text: str) -> float:
    return parse_money(text, empty_is_zero=False)

@dataclass(frozen=True)
class TrackingInput:
    d: date
    typ: str
    category: str
    amount: float
    details: str
    tag_ids: tuple[int, ...] = ()

class TrackerDialog(QDialog):
    def __init__(self, parent=None, *, conn: sqlite3.Connection, cats: CategoryModel, preset: dict | None = None):
        super().__init__(parent)
        self.setMinimumSize(650, 420)
        self.setWindowTitle(tr("dlg.tracking_entry"))
        self.setModal(True)
        self.conn = conn
        self.cats = cats
        self._track = TrackingModel(conn)
        self._tags = TagsModel(conn)

        self.ed_date = QDateEdit()
        self.ed_date.setCalendarPopup(True)
        self.ed_date.setDate(date.today())

        self.cb_typ = QComboBox()
        self.cb_typ.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.cb_typ.addItem(tr("kpi.income"), TYP_INCOME)
        self.cb_typ.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)

        self.cb_cat = QComboBox()
        self.cb_cat.setEnabled(False)
        self.cb_cat.setEditable(True)
        self.cb_cat.setInsertPolicy(QComboBox.NoInsert)
        self.cb_cat.setMaxVisibleItems(18)
        self.cb_cat.setToolTip(tr("tracking.category_tip"))
        try:
            self.cb_cat.lineEdit().setPlaceholderText(tr("tracking.category_placeholder"))
        except Exception:
            pass

        self.ed_amount = QLineEdit()
        self.ed_amount.setPlaceholderText(tr('auto.views_tracker_dialog.54_z_b_12_50_7eb13fc1'))

        self.ed_details = QLineEdit()

        self.lst_tags = QListWidget()
        self.lst_tags.setMaximumHeight(110)
        self.lst_tags.setAlternatingRowColors(True)
        self.lst_tags.setToolTip(tr("tracking.tags_input_tip"))
        self._fill_tags(())

        self.btn_ok = QPushButton(tr("btn.save"))
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        form = QFormLayout()
        form.addRow(tr("header.date"), self.ed_date)
        form.addRow(tr("lbl.type"), self.cb_typ)
        form.addRow(tr("header.category"), self.cb_cat)
        self.lbl_cat_tip = QLabel(tr("tracking.category_tip"))
        self.lbl_cat_tip.setWordWrap(True)
        self.lbl_cat_tip.setStyleSheet("font-size: 11px; opacity: 0.75;")
        form.addRow("", self.lbl_cat_tip)
        form.addRow(currency_header(), self.ed_amount)
        form.addRow(tr("lbl.lbl_details"), self.ed_details)
        form.addRow(tr("header.tags"), self.lst_tags)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

        self.cb_typ.currentIndexChanged.connect(lambda _: self._fill_categories())
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._fill_categories()

        if preset:
            self._apply_preset(preset)

    def _apply_preset(self, p: dict) -> None:
        # date: "dd.mm.yyyy" or iso
        if "date" in p and p["date"]:
            s = str(p["date"]).strip()
            try:
                if "." in s:
                    d = datetime.strptime(s, "%d.%m.%Y").date()
                else:
                    d = date.fromisoformat(s)
                self.ed_date.setDate(d)
            except Exception as e:
                logger.debug("if '.' in s:: %s", e)
        if "typ" in p and p["typ"]:
            raw_typ = str(p["typ"]).strip()
            typ_db = normalize_typ(db_typ_from_display(raw_typ))
            self._set_combo_by_data(self.cb_typ, typ_db)
        self._fill_categories()
        if "category" in p and p["category"]:
            self._set_combo_by_data(self.cb_cat, str(p["category"]))
        if "amount" in p and p["amount"] is not None:
            self.ed_amount.setText(str(p["amount"]))
        if "details" in p and p["details"] is not None:
            self.ed_details.setText(str(p["details"]))
        if "tag_ids" in p:
            try:
                self._fill_tags(tuple(int(x) for x in (p.get("tag_ids") or ())))
            except Exception as e:
                logger.debug("preset tags: %s", e)

    def _fill_tags(self, selected_ids: tuple[int, ...] = ()) -> None:
        """Füllt die Tag-Auswahl für die Buchung direkt im Dialog."""
        try:
            selected = {int(x) for x in selected_ids}
        except Exception:
            selected = set()
        self.lst_tags.clear()
        try:
            tags = self._tags.list_all()
        except Exception as exc:
            logger.debug("tags load: %s", exc)
            tags = []
        if not tags:
            item = QListWidgetItem(tr("tracking.tags_no_tags_short"))
            item.setFlags(Qt.NoItemFlags)
            self.lst_tags.addItem(item)
            return
        for tag in tags:
            item = QListWidgetItem(str(tag.name))
            item.setData(Qt.UserRole, int(tag.id))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if int(tag.id) in selected else Qt.Unchecked)
            self.lst_tags.addItem(item)

    def _selected_tag_ids(self) -> tuple[int, ...]:
        ids: list[int] = []
        for i in range(self.lst_tags.count()):
            item = self.lst_tags.item(i)
            if not item or not (item.flags() & Qt.ItemIsUserCheckable):
                continue
            if item.checkState() == Qt.Checked:
                try:
                    ids.append(int(item.data(Qt.UserRole)))
                except Exception:
                    pass
        return tuple(ids)


    def _set_combo_by_data(self, combo, value: str) -> None:
        """Setzt ComboBox-Auswahl über itemData (fallback: Textvergleich)."""
        if not value:
            return
        value = str(value)
        for i in range(combo.count()):
            data = combo.itemData(i)
            if data == value:
                combo.setCurrentIndex(i)
                return
        # Fallback: Text ohne Einrückung
        for i in range(combo.count()):
            if str(combo.itemText(i)).strip() == value:
                combo.setCurrentIndex(i)
                return
        # Letzter Fallback nur für editierbare Combos (Kategorie-Picker):
        # Seit v2.1.7 listet der Tracking-Picker Parent-Kategorien mit
        # Unterkategorien bewusst nicht mehr. Alte Buchungen auf solche
        # Parents müssen beim Bearbeiten trotzdem sichtbar bleiben. Ohne
        # diesen Fallback bliebe still der erste Picker-Eintrag stehen und
        # die Buchung würde beim Speichern ungewollt umgehängt.
        try:
            if combo.isEditable():
                combo.setCurrentIndex(-1)
                combo.setEditText(value)
        except Exception as e:
            logger.debug("Editable-Preset-Fallback: %s", e)

    def _category_pairs_structured(self, typ: str) -> list[tuple[str, str]]:
        """Dropdown-Reihenfolge: Favoriten zuerst, danach manuelle Nutzungshäufigkeit."""
        try:
            return self.cats.list_for_tracking_dropdown(typ)
        except Exception as e:
            logger.debug("category dropdown order: %s", e)
            try:
                return self.cats.list_names_tree(typ)
            except Exception:
                return [(n, n) for n in self.cats.list_names(typ)]

    def _fill_categories(self) -> None:
        typ = self.cb_typ.currentData() or db_typ_from_display(self.cb_typ.currentText())
        self.cb_cat.setEnabled(True)
        current_data = self.cb_cat.currentData() or self.cb_cat.currentText().strip()
        # v2.2.0: Fallback auf die zuletzt gebuchte Kategorie dieses Kontos.
        if not current_data:
            try:
                last_map = Settings().get("tracking_last_category", {}) or {}
                from model.typ_constants import normalize_typ as _nt

                current_data = str(last_map.get(_nt(str(typ)), "") or "")
            except Exception as e:
                logger.debug("last category restore: %s", e)

        try:
            from views.category_picker import populate_grouped_combo
            grouped = self.cats.list_for_tracking_dropdown_grouped(typ)
            if grouped:
                populate_grouped_combo(self.cb_cat, grouped)
            else:
                raise ValueError("leer")
        except Exception as e:
            logger.debug("gruppierter Picker, Fallback flach: %s", e)
            self.cb_cat.clear()
            for label, real in self._category_pairs_structured(typ):
                self.cb_cat.addItem(label, real)
            try:
                completer = self.cb_cat.completer()
                completer.setCompletionMode(QCompleter.PopupCompletion)
                completer.setFilterMode(Qt.MatchContains)
                completer.setCaseSensitivity(Qt.CaseInsensitive)
            except Exception as e2:
                logger.debug("category completer: %s", e2)

        # Vorherige Auswahl wiederherstellen (über echte itemData).
        restored = False
        if current_data:
            for i in range(self.cb_cat.count()):
                if self.cb_cat.itemData(i) == current_data:
                    self.cb_cat.setCurrentIndex(i)
                    restored = True
                    break
        if not restored:
            # ersten echten Eintrag (kein Header) wählen
            for i in range(self.cb_cat.count()):
                if self.cb_cat.itemData(i) is not None:
                    self.cb_cat.setCurrentIndex(i)
                    break

    def _selected_typ(self) -> str:
        return normalize_typ(self.cb_typ.currentData() or db_typ_from_display(self.cb_typ.currentText()))

    def _selected_category(self) -> str:
        from views.category_picker import resolve_combo_category

        category = resolve_combo_category(self.cb_cat)
        resolved = self.cats.resolve_name(self._selected_typ(), category)
        return resolved or category

    def _validate_and_accept(self) -> None:
        typ = self._selected_typ()
        if not typ:
            QMessageBox.warning(self, tr('auto.views_tracker_dialog.162_fehlt_fb898654'), tr("dlg.bitte_typ_auswaehlen"))
            return
        category = self._selected_category()
        if not category:
            QMessageBox.warning(self, tr('auto.views_tracker_dialog.165_fehlt_a7f19cb1'), tr("dlg.bitte_kategorie_auswaehlen"))
            return
        if not self.cats.resolve_name(typ, category):
            QMessageBox.warning(self, tr("dlg.hinweis"), trf("dlg.unknown_category", name=category))
            return
        try:
            amt = parse_amount(self.ed_amount.text())
        except Exception:
            QMessageBox.warning(self, tr('dlg.hinweis'), tr("dlg.betrag_ist_ungueltig"))
            return
        if typ == TYP_EXPENSES and amt < 0:
            QMessageBox.warning(self, tr("dlg.nicht_erlaubt"), tr("dlg.bei_ausgaben_sind_negative"))
            return
        # v2.2.0: letzte Auswahl je Konto merken (konsistent zur Schnellerfassung).
        try:
            last_map = dict(Settings().get("tracking_last_category", {}) or {})
            last_map[typ] = str(category)
            Settings().set("tracking_last_category", last_map)
        except Exception as e:
            logger.debug("last category persist: %s", e)
        self.accept()

    def get_input(self) -> TrackingInput:
        d = self.ed_date.date().toPython()
        typ = self._selected_typ()
        cat = self._selected_category()
        amt = parse_amount(self.ed_amount.text())
        details = self.ed_details.text() or ""
        return TrackingInput(d, typ, cat, float(amt), details, self._selected_tag_ids())
