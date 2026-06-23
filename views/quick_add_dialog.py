from __future__ import annotations
import sqlite3
from datetime import date
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QComboBox,
    QDoubleSpinBox,
    QDateEdit,
    QPushButton,
    QMessageBox,
)

from model.category_model import CategoryModel
from model.tracking_model import TrackingModel
from model.savings_goals_model import SavingsGoalBoundsError
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS, normalize_typ
from utils.money import currency_header, format_money
from views.savings_goal_messages import show_savings_goal_bounds_warning


import logging
from utils.i18n import tr, trf, display_typ, db_typ_from_display

logger = logging.getLogger(__name__)


class QuickAddDialog(QDialog):
    """Schnelleingabe-Dialog für neue Tracking-Einträge (Strg+N)"""

    def __init__(self, conn: sqlite3.Connection, parent=None):
        super().__init__(parent)
        self.conn = conn
        self.cats = CategoryModel(conn)
        self.tracking = TrackingModel(conn)

        self.setWindowTitle(tr("dlg.quick_add"))
        self.setMinimumWidth(400)

        layout = QVBoxLayout()

        # Info
        info = QLabel(tr("lbl.lbl_quick_add_title"))
        layout.addWidget(info)

        # Datum (heute als Standard)
        date_row = QHBoxLayout()
        date_row.addWidget(QLabel(tr("lbl.lbl_date")))
        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDate(date.today())
        self.date_edit.setDisplayFormat("dd.MM.yyyy")
        date_row.addWidget(self.date_edit, 1)
        layout.addLayout(date_row)

        # Typ
        typ_row = QHBoxLayout()
        typ_row.addWidget(QLabel(tr("lbl.type")))
        self.typ_combo = QComboBox()
        self.typ_combo.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.typ_combo.addItem(tr("kpi.income"), TYP_INCOME)
        self.typ_combo.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        self.typ_combo.currentIndexChanged.connect(lambda _: self._on_typ_changed())
        typ_row.addWidget(self.typ_combo, 1)
        layout.addLayout(typ_row)

        # Kategorie: Suche + echtes Dropdown-Menü
        cat_row = QHBoxLayout()
        cat_row.addWidget(QLabel(tr("lbl.category")))

        cat_picker_layout = QVBoxLayout()
        self.cat_search = QLineEdit()
        self.cat_search.setPlaceholderText(tr("quickadd.category_search_placeholder"))
        self.cat_search.setToolTip(tr("quickadd.category_search_tip"))
        self.cat_search.textEdited.connect(self._on_category_search_edited)
        cat_picker_layout.addWidget(self.cat_search)

        self.cat_combo = QComboBox()
        self.cat_combo.setEditable(False)
        self.cat_combo.setInsertPolicy(QComboBox.NoInsert)
        self.cat_combo.setMaxVisibleItems(18)
        self.cat_combo.setToolTip(tr("quickadd.category_dropdown_tip"))
        try:
            self.cat_combo.setPlaceholderText(tr("quickadd.no_category_matches"))
        except Exception:
            pass
        self.cat_combo.activated.connect(lambda _: self._on_category_combo_activated())
        cat_picker_layout.addWidget(self.cat_combo)

        self._all_category_rows: list[tuple[str, str, object]] = []
        self._update_categories()
        cat_row.addLayout(cat_picker_layout, 1)
        layout.addLayout(cat_row)

        # Betrag
        amount_row = QHBoxLayout()
        amount_row.addWidget(QLabel(tr("lbl.lbl_amount")))
        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 999999.99)
        self.amount_spin.setPrefix(f"{currency_header()} ")
        self.amount_spin.setDecimals(2)
        self.amount_spin.setSingleStep(10)
        amount_row.addWidget(self.amount_spin, 1)
        layout.addLayout(amount_row)

        # Details
        details_row = QHBoxLayout()
        details_row.addWidget(QLabel(tr("lbl.lbl_details")))
        self.details_edit = QLineEdit()
        self.details_edit.setPlaceholderText(
            tr("auto.views_quick_add_dialog.83_optional_beschreibung_5622cc90")
        )
        details_row.addWidget(self.details_edit, 1)
        layout.addLayout(details_row)

        # Buttons
        btn_layout = QHBoxLayout()

        self.btn_save_add = QPushButton(tr("btn.btn_save_and_new"))
        self.btn_save_add.clicked.connect(self._save_and_new)
        btn_layout.addWidget(self.btn_save_add)

        self.btn_save_close = QPushButton(tr("btn.speichern_schliessen_1"))
        self.btn_save_close.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self.btn_save_close)

        btn_cancel = QPushButton(tr("btn.cancel"))
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)

        layout.addLayout(btn_layout)

        self.setLayout(layout)
        self._update_amount_range()

        # Enter = Speichern & Schließen
        self.amount_spin.setFocus()

    def _on_typ_changed(self) -> None:
        """Typwechsel: Kategorien und Betragslogik gemeinsam aktualisieren."""
        self.cat_search.clear()
        self._update_categories()
        self._update_amount_range()

    def _update_amount_range(self) -> None:
        """Negative Beträge sind nur für Ersparnisse-Entnahmen vorgesehen.

        Die normale Ausgaben-Erfassung bleibt geschützt. Für Sparziele braucht
        die Schnellerfassung aber negative Ersparnisse-Buchungen, damit Geld aus
        einem freigegebenen Ziel herausgebucht werden kann.
        """
        typ = normalize_typ(
            self.typ_combo.currentData()
            or db_typ_from_display(self.typ_combo.currentText())
        )
        if typ == TYP_SAVINGS:
            self.amount_spin.setRange(-999999.99, 999999.99)
            self.amount_spin.setToolTip(tr("quickadd.savings_negative_tip"))
        else:
            if self.amount_spin.value() < 0:
                self.amount_spin.setValue(abs(self.amount_spin.value()))
            self.amount_spin.setRange(0, 999999.99)
            self.amount_spin.setToolTip("")

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

    def _update_categories(self):
        """Aktualisiert Kategorien nach Typ und baut Suche + Dropdown neu auf."""
        typ = self.typ_combo.currentData() or db_typ_from_display(
            self.typ_combo.currentText()
        )

        current_data = self._selected_category_from_dropdown_only()
        if not current_data:
            current_data = (
                self.cat_combo.currentData() or self.cat_combo.currentText().strip()
            )

        try:
            grouped = self.cats.list_for_tracking_dropdown_grouped(typ)
            if not grouped:
                raise ValueError("leer")
            self._all_category_rows = grouped
        except Exception as e:
            logger.debug("gruppierter Picker, Fallback flach: %s", e)
            self._all_category_rows = [
                ("item", label, real)
                for label, real in self._category_pairs_structured(typ)
            ]

        self._rebuild_category_dropdown(
            query=self.cat_search.text().strip() if hasattr(self, "cat_search") else "",
            preferred_category=str(current_data or ""),
            show_popup=False,
        )

    def _selected_category_from_dropdown_only(self) -> str:
        """Liest nur die echte Dropdown-Auswahl, ohne Suchtext zu interpretieren."""
        data = self.cat_combo.currentData()
        return data.strip() if isinstance(data, str) and data.strip() else ""

    def _rebuild_category_dropdown(
        self,
        *,
        query: str = "",
        preferred_category: str = "",
        show_popup: bool = False,
    ) -> None:
        """Filtert das Dropdown anhand des Suchfelds und erhält die Auswahl."""
        from views.category_picker import (
            filter_grouped_categories,
            populate_grouped_combo,
        )

        rows = filter_grouped_categories(self._all_category_rows, query)
        populate_grouped_combo(self.cat_combo, rows)

        selected = False
        preferred = (preferred_category or "").strip()
        if preferred:
            for i in range(self.cat_combo.count()):
                if self.cat_combo.itemData(i) == preferred:
                    self.cat_combo.setCurrentIndex(i)
                    selected = True
                    break

        if not selected:
            for i in range(self.cat_combo.count()):
                data = self.cat_combo.itemData(i)
                if isinstance(data, str) and data.strip():
                    self.cat_combo.setCurrentIndex(i)
                    selected = True
                    break

        if not selected:
            self.cat_combo.setCurrentIndex(-1)

        self.cat_combo.setEnabled(selected)
        if show_popup and self.cat_combo.count() > 0:
            QTimer.singleShot(0, self.cat_combo.showPopup)

    def _on_category_search_edited(self, text: str) -> None:
        """Suchfeld tippen: Dropdown live filtern und öffnen."""
        self._rebuild_category_dropdown(query=text.strip(), show_popup=True)

    def _on_category_combo_activated(self) -> None:
        """Dropdown-Auswahl bestätigt: Suchfeld sauber auf gewählte Kategorie setzen."""
        from views.category_picker import _clean_category_label

        category = self._selected_category_from_dropdown_only()
        if not category:
            return

        label = self.cat_combo.currentText()
        self.cat_search.blockSignals(True)
        try:
            self.cat_search.setText(_clean_category_label(label) or category)
        finally:
            self.cat_search.blockSignals(False)

        # Nach Auswahl wieder die volle Liste zeigen, Auswahl aber beibehalten.
        self._rebuild_category_dropdown(
            query="", preferred_category=category, show_popup=False
        )

    def _selected_typ(self) -> str:
        return normalize_typ(
            self.typ_combo.currentData()
            or db_typ_from_display(self.typ_combo.currentText())
        )

    def _selected_category(self) -> str:
        from views.category_picker import resolve_combo_category

        category = resolve_combo_category(self.cat_combo)
        resolved = self.cats.resolve_name(self._selected_typ(), category)
        return resolved or category

    def _validate(self) -> bool:
        """Prüft ob alle Pflichtfelder ausgefüllt sind"""
        typ = self._selected_typ()
        category = self._selected_category()
        if not category:
            QMessageBox.warning(
                self, tr("dlg.hinweis"), tr("dlg.bitte_eine_kategorie_auswaehlen")
            )
            return False
        resolved = self.cats.resolve_name(typ, category)
        if not resolved:
            QMessageBox.warning(
                self, tr("dlg.hinweis"), trf("dlg.unknown_category", name=category)
            )
            return False

        amount = self.amount_spin.value()

        if abs(amount) < 1e-9:
            QMessageBox.warning(
                self, tr("dlg.hinweis"), tr("quickadd.amount_must_not_be_zero")
            )
            return False

        if typ == TYP_EXPENSES and amount < 0:
            QMessageBox.warning(
                self, tr("dlg.nicht_erlaubt"), tr("dlg.bei_ausgaben_sind_negative")
            )
            return False

        if typ != TYP_SAVINGS and amount < 0:
            QMessageBox.warning(
                self, tr("dlg.nicht_erlaubt"), tr("quickadd.negative_only_savings")
            )
            return False

        return True

    def _save_entry(self) -> bool:
        """Speichert den Eintrag"""
        if not self._validate():
            return False

        d = self.date_edit.date().toPython()
        typ = self._selected_typ()
        category = self._selected_category()
        amount = self.amount_spin.value()
        details = self.details_edit.text().strip()

        if typ == TYP_SAVINGS:
            try:
                self.tracking.validate_savings_goal_booking(category, amount)
            except SavingsGoalBoundsError as e:
                show_savings_goal_bounds_warning(self, e)
                return False

        if typ == TYP_SAVINGS and amount < 0:
            conflict = self.tracking.check_savings_goal_conflict(category, amount)
            if conflict:
                if not self._confirm_negative_savings_booking(conflict, amount):
                    return False

        # Auto-Details generieren wenn leer
        if not details:
            month_names = [tr(f"month.{i}") for i in range(1, 13)]
            details = f"{month_names[d.month - 1]} - {category}"

        try:
            self.tracking.add(d, typ, category, amount, details)
        except SavingsGoalBoundsError as e:
            show_savings_goal_bounds_warning(self, e)
            return False
        return True

    def _confirm_negative_savings_booking(self, conflict: dict, amount: float) -> bool:
        """Sicherheitsabfrage für negative Ersparnisse-Buchungen in der Schnellerfassung."""
        goal_name = str(conflict.get("goal_name", ""))
        goal_status = str(conflict.get("goal_status", ""))
        current = float(conflict.get("current_amount", 0.0))
        withdrawal = abs(float(amount))

        if goal_status == "freigegeben":
            QMessageBox.information(
                self,
                tr("tracking.title.savings_consumption"),
                trf(
                    "tracking.msg.goal_consumption_info",
                    goal_name=goal_name,
                    current=format_money(current),
                    withdrawal=format_money(withdrawal),
                ),
            )
            return True

        answer = QMessageBox.question(
            self,
            tr("tracking.title.savings_withdraw"),
            trf(
                "quickadd.savings_still_saving_confirm",
                goal_name=goal_name,
                current=format_money(current),
                withdrawal=format_money(withdrawal),
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return answer == QMessageBox.Yes

    def _save_and_new(self):
        """Speichern und Dialog für neuen Eintrag vorbereiten"""
        if self._save_entry():
            # Felder zurücksetzen für nächsten Eintrag
            self.amount_spin.setValue(0)
            self.details_edit.clear()
            self.amount_spin.setFocus()
            self.amount_spin.selectAll()

    def _save_and_close(self):
        """Speichern und Dialog schließen"""
        if self._save_entry():
            self.accept()
