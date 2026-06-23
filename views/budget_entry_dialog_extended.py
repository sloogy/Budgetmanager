"""
Budget-Entry-Dialog mit integrierter Kategorie-Verwaltung.

Funktionen:
- Neue Kategorien direkt erstellen (als Hauptkategorie oder Unterkategorie)
- Parent-Kategorie per Dropdown wählbar
- Kategorie-Flags (Fixkosten, Wiederkehrend, Tag) direkt setzen
- Kategorien umbenennen und löschen
"""

from __future__ import annotations

import logging
import sqlite3

logger = logging.getLogger(__name__)
from dataclasses import dataclass
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QSpinBox,
    QComboBox,
    QLineEdit,
    QCheckBox,
    QPushButton,
    QMessageBox,
    QGroupBox,
    QWidget,
    QToolButton,
    QMenu,
    QInputDialog,
    QDialogButtonBox,
    QFrame,
)

from model.category_model import CategoryModel, Category
from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS
from model.budget_modes import (
    BUDGET_MODE_MONTH,
    BUDGET_MODE_ALL,
    BUDGET_MODE_RANGE,
    normalize_budget_mode,
)
from model.category_forecast_mode import (
    FORECAST_MODE_AUTO,
    FORECAST_MODE_INCREMENTAL,
    FORECAST_MODE_NORMAL,
    FORECAST_MODE_POT,
)
from utils.icons import get_icon


def _get_months():
    """Gibt die lokalisierten Monatskurzbezeichnungen zurück."""
    return [tr(f"month_short.{i}") for i in range(1, 13)]


from utils.money import parse_money, currency_header, format_short
from utils.i18n import tr, trf, display_typ, db_typ_from_display
from views.category_delete_dialog import ask_category_delete_decision


def parse_amount(text: str) -> float:
    return parse_money(text, empty_is_zero=False)


@dataclass(frozen=True)
class BudgetEntryRequest:
    year: int
    typ: str
    category: str
    amount: float
    mode: str  # internal: "month", "all", "range"
    month: int  # 1..12 (für Mode Monat)
    from_month: int  # 1..12 (für Bereich)
    to_month: int  # 1..12 (für Bereich)
    only_if_empty: bool
    # NEU: Kategorie-Erstellungsdaten
    category_created: bool = False
    parent_category_id: int | None = None
    forecast_mode: str = FORECAST_MODE_AUTO


class NewCategoryDialog(QDialog):
    """Dialog zum Erstellen einer neuen Kategorie."""

    def __init__(
        self,
        parent=None,
        *,
        typ: str,
        category_name: str,
        cat_model: CategoryModel,
        existing_categories: list[Category],
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.category_create"))
        self.setModal(True)
        self.setMinimumWidth(450)

        self.cat_model = cat_model
        self.typ = typ
        self.existing_categories = existing_categories
        self._created_id: int | None = None

        # === Haupt-Layout ===
        layout = QVBoxLayout(self)

        # Info-Label
        info = QLabel(
            trf("msg.kategorie_existiert_nicht_html", category_name=category_name)
        )
        info.setWordWrap(True)
        layout.addWidget(info)

        # === Kategorie-Details ===
        group = QGroupBox(
            tr("auto.views_budget_entry_dialog_extended.82_kategorie_details_6ef68b34")
        )
        form = QFormLayout(group)

        # Name
        self.name_edit = QLineEdit(category_name)
        form.addRow(tr("lbl.name"), self.name_edit)

        # Typ (read-only anzeigen)
        typ_label = QLabel(
            trf(
                "auto.views_budget_entry_dialog_extended.90_b_value_0_b_ee6c93f4",
                value_0=(typ),
            )
        )
        form.addRow(tr("header.type"), typ_label)

        # Parent-Kategorie
        self.parent_combo = QComboBox()
        self.parent_combo.addItem(
            tr(
                "auto.views_budget_entry_dialog_extended.95_hauptkategorie_kein_parent_883e571a"
            ),
            None,
        )

        # Nur Kategorien des gleichen Typs als mögliche Parents
        for cat in existing_categories:
            indent = ""
            # Hierarchie-Einrückung berechnen
            if cat.parent_id:
                indent = "  "
            self.parent_combo.addItem(f"{indent}{cat.name}", cat.id)

        form.addRow(tr("lbl.parent_category"), self.parent_combo)

        layout.addWidget(group)

        # === Flags ===
        flags_group = QGroupBox(
            tr("auto.views_budget_entry_dialog_extended.110_eigenschaften_902ad0b9")
        )
        flags_layout = QGridLayout(flags_group)

        self.chk_fix = QCheckBox(tr("tracking.title.fixcosts"))
        self.chk_fix.setToolTip(tr("help.tip.fixcost"))
        flags_layout.addWidget(self.chk_fix, 0, 0)

        self.chk_recurring = QCheckBox(tr("lbl.recurring"))
        self.chk_recurring.setToolTip(tr("help.tip.recurring"))
        flags_layout.addWidget(self.chk_recurring, 0, 1)

        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel(tr("dlg.faelligkeitstag_1")))
        self.day_spin = QSpinBox()
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(1)
        self.day_spin.setEnabled(False)
        day_layout.addWidget(self.day_spin)
        day_layout.addStretch()
        flags_layout.addLayout(day_layout, 1, 0, 1, 2)

        flags_layout.addWidget(QLabel(tr("forecast.mode.label")), 2, 0)
        self.forecast_mode = QComboBox()
        self.forecast_mode.addItem(tr("forecast.mode.auto"), FORECAST_MODE_AUTO)
        self.forecast_mode.addItem(tr("forecast.mode.pot"), FORECAST_MODE_POT)
        self.forecast_mode.addItem(
            tr("forecast.mode.incremental"), FORECAST_MODE_INCREMENTAL
        )
        self.forecast_mode.addItem(tr("forecast.mode.normal"), FORECAST_MODE_NORMAL)
        self.forecast_mode.setToolTip(tr("forecast.mode.tooltip"))
        flags_layout.addWidget(self.forecast_mode, 2, 1)

        layout.addWidget(flags_group)

        # Verbindungen
        self.chk_recurring.toggled.connect(self.day_spin.setEnabled)

        # === Buttons ===
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_create = QPushButton(
            tr(
                "auto.views_budget_entry_dialog_extended.140_kategorie_erstellen_d45dd95d"
            )
        )
        self.btn_create.setDefault(True)
        btn_layout.addWidget(self.btn_create)

        self.btn_cancel = QPushButton(tr("btn.cancel"))
        btn_layout.addWidget(self.btn_cancel)

        layout.addLayout(btn_layout)

        # Signale
        self.btn_create.clicked.connect(self._create_category)
        self.btn_cancel.clicked.connect(self.reject)

    def _create_category(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(
                self, tr("dlg.hinweis"), tr("account.bitte_einen_namen_eingeben")
            )
            return

        # Prüfen ob Name bereits existiert
        for cat in self.existing_categories:
            if cat.name.lower() == name.lower():
                QMessageBox.warning(
                    self,
                    tr("msg.error"),
                    trf(
                        "auto.views_budget_entry_dialog_extended.164_eine_kategorie_mit_dem_namen_value__2fba299b",
                        value_0=(name),
                    ),
                )
                return

        parent_id = self.parent_combo.currentData()
        is_fix = self.chk_fix.isChecked()
        is_recurring = self.chk_recurring.isChecked()
        recurring_day = self.day_spin.value() if is_recurring else 1
        forecast_mode = str(self.forecast_mode.currentData() or FORECAST_MODE_AUTO)

        try:
            self._created_id = self.cat_model.create(
                typ=self.typ,
                name=name,
                is_fix=is_fix,
                is_recurring=is_recurring,
                recurring_day=recurring_day,
                parent_id=parent_id,
                forecast_mode=forecast_mode,
            )
            self.accept()
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_budget_entry_dialog_extended.184_konnte_kategorie_nicht_erstellen_va_dce4d9f6",
                    value_0=(e),
                ),
            )

    def get_created_name(self) -> str:
        return self.name_edit.text().strip()

    def get_created_id(self) -> int | None:
        return self._created_id


class CategoryManagementWidget(QWidget):
    """Widget für Kategorie-Verwaltung im Budget-Dialog."""

    category_changed = Signal()  # Signalisiert Änderungen

    def __init__(self, parent=None, *, conn: sqlite3.Connection, typ: str):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self.typ = typ

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Kategorie-ComboBox
        self.category_combo = QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setMinimumWidth(200)
        self.category_combo.setPlaceholderText(
            tr("dlg.kategorie_eingeben_oder_auswaehlen")
        )
        # Autofilter/Completer deaktivieren - nur manuelle Auswahl
        self.category_combo.setCompleter(None)
        layout.addWidget(self.category_combo, 1)

        # Management-Button mit Menü
        self.btn_manage = QToolButton()
        self.btn_manage.setText("")
        self.btn_manage.setIcon(get_icon("⚙️"))
        self.btn_manage.setToolTip(
            tr(
                "auto.views_budget_entry_dialog_extended.220_kategorie_optionen_e050bea2"
            )
        )
        self.btn_manage.setPopupMode(QToolButton.InstantPopup)

        menu = QMenu(self.btn_manage)
        self.act_new = menu.addAction(tr("budget.ctx.new_category"))
        self.act_new_sub = menu.addAction(
            tr(
                "auto.views_budget_entry_dialog_extended.225_neue_unterkategorie_e01e0b00"
            )
        )
        self.act_new_sub.setIcon(get_icon("📂"))
        menu.addSeparator()
        self.act_rename = menu.addAction(tr("budget.ctx.rename"))
        self.act_delete = menu.addAction(tr("btn.loeschen_2"))
        menu.addSeparator()
        self.act_toggle_fix = menu.addAction(tr("ctx.toggle_fix"))
        self.act_toggle_fix.setIcon(get_icon("📌"))
        self.act_toggle_rec = menu.addAction(tr("ctx.toggle_recurring"))
        self.act_toggle_rec.setIcon(get_icon("🔁"))
        self.act_set_day = menu.addAction(tr("dlg.faelligkeitstag_setzen_1"))

        self.btn_manage.setMenu(menu)
        layout.addWidget(self.btn_manage)

        # Signale verbinden
        self.act_new.triggered.connect(self._new_category)
        self.act_new_sub.triggered.connect(self._new_subcategory)
        self.act_rename.triggered.connect(self._rename_category)
        self.act_delete.triggered.connect(self._delete_category)
        self.act_toggle_fix.triggered.connect(self._toggle_fix)
        self.act_toggle_rec.triggered.connect(self._toggle_recurring)
        self.act_set_day.triggered.connect(self._set_day)

        self._refresh_categories()

    def set_typ(self, typ: str) -> None:
        """Ändert den Typ und lädt Kategorien neu."""
        self.typ = typ
        self._refresh_categories()

    def _refresh_categories(self) -> None:
        """Lädt die Kategorien-Liste neu."""
        current_text = self.get_category()
        self.category_combo.clear()

        cats = self.cat_model.list(self.typ)
        # Hierarchische Darstellung
        nodes = self.cat_model.build_tree(cats)

        def add_items(children: list[dict], depth: int = 0):
            for node in children:
                cat: Category = node["cat"]
                prefix = "  " * depth
                marker = "▸ " if node["children"] else "• "
                display = f"{prefix}{marker}{cat.name}"
                self.category_combo.addItem(display, cat.name)
                add_items(node["children"], depth + 1)

        add_items(nodes)

        # Vorherige Auswahl wiederherstellen
        if current_text:
            idx = self.category_combo.findData(current_text)
            if idx >= 0:
                self.category_combo.setCurrentIndex(idx)
            else:
                self.category_combo.setEditText(current_text)

    def get_category(self) -> str:
        """Gibt den aktuell ausgewählten/eingegebenen Kategorie-Namen zurück.

        Bei editierbaren QComboBoxen kann currentData() auf dem vorherigen
        Eintrag stehen bleiben, während der Benutzer bereits neuen Text tippt.
        Deshalb nutzen wir denselben robusten Resolver wie Tracker/Schnelleingabe.
        """
        from views.category_picker import resolve_combo_category

        name = resolve_combo_category(self.category_combo).strip().lstrip("▸• ").strip()
        resolved = self.cat_model.resolve_name(self.typ, name)
        return resolved or name

    def set_category(self, name: str) -> None:
        """Setzt die ausgewählte Kategorie."""
        idx = self.category_combo.findData(name)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setEditText(name)

    def _get_selected_category(self) -> Category | None:
        """Gibt die aktuell ausgewählte Kategorie als Category-Objekt zurück."""
        name = self.get_category()
        if not name:
            return None

        for cat in self.cat_model.list(self.typ):
            if cat.name == name:
                return cat
        return None

    def _new_category(self) -> None:
        """Erstellt eine neue Hauptkategorie."""
        name, ok = QInputDialog.getText(
            self,
            tr("btn.new_category"),
            trf(
                "auto.views_budget_entry_dialog_extended.314_name_der_neuen_kategorie_value_0_399f599a",
                value_0=(self.typ),
            ),
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        try:
            self.cat_model.create(
                typ=self.typ,
                name=name,
                is_fix=False,
                is_recurring=False,
                parent_id=None,
            )
            self._refresh_categories()
            self.set_category(name)
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_budget_entry_dialog_extended.333_konnte_kategorie_nicht_erstellen_va_12bb8446",
                    value_0=(e),
                ),
            )

    def _new_subcategory(self) -> None:
        """Erstellt eine neue Unterkategorie."""
        parent_cat = self._get_selected_category()

        # Parent-Auswahl Dialog
        cats = self.cat_model.list(self.typ)
        if not cats:
            QMessageBox.information(
                self, tr("msg.info"), tr("budget.msg.no_categories_create_main")
            )
            return

        # Auswahl der Parent-Kategorie
        items = [cat.name for cat in cats]
        default_idx = 0
        if parent_cat:
            try:
                default_idx = items.index(parent_cat.name)
            except ValueError as e:
                logger.debug("default_idx = items.index(parent_cat.name): %s", e)

        parent_name, ok = QInputDialog.getItem(
            self,
            tr("auto.views_budget_entry_dialog_extended.358_parent_kategorie_23016e6b"),
            tr("dlg.unter_welcher_kategorie_soll"),
            items,
            default_idx,
            False,
        )
        if not ok:
            return

        # Parent-ID finden
        parent_id = None
        for cat in cats:
            if cat.name == parent_name:
                parent_id = cat.id
                break

        # Name der neuen Unterkategorie
        name, ok = QInputDialog.getText(
            self,
            tr("budget.title.new_subcategory"),
            trf(
                "auto.views_budget_entry_dialog_extended.375_name_der_neuen_unterkategorie_unter_655e15ec",
                value_0=(parent_name),
            ),
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        try:
            self.cat_model.create(
                typ=self.typ,
                name=name,
                is_fix=False,
                is_recurring=False,
                parent_id=parent_id,
            )
            self._refresh_categories()
            self.set_category(name)
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_budget_entry_dialog_extended.394_konnte_unterkategorie_nicht_erstell_10c56189",
                    value_0=(e),
                ),
            )

    def _rename_category(self) -> None:
        """Benennt die ausgewählte Kategorie um."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(
                self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie")
            )
            return

        new_name, ok = QInputDialog.getText(
            self,
            tr("auto.views_budget_entry_dialog_extended.404_umbenennen_6ad211f7"),
            trf(
                "auto.views_budget_entry_dialog_extended.405_neuer_name_fuer_value_0_ac7dc2c9",
                value_0=(cat.name),
            ),
            text=cat.name,
        )
        if not ok or not new_name.strip():
            return

        new_name = new_name.strip()
        if new_name == cat.name:
            return

        try:
            self.cat_model.rename_and_cascade(
                cat.id, typ=self.typ, old_name=cat.name, new_name=new_name
            )
            self._refresh_categories()
            self.set_category(new_name)
            self.category_changed.emit()
            QMessageBox.information(
                self,
                "OK",
                trf(
                    "auto.views_budget_entry_dialog_extended.425_kategorie_umbenannt_value_0_value_1_ac33fb77",
                    value_0=(cat.name),
                    value_1=(new_name),
                ),
            )
        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_budget_entry_dialog_extended.429_umbenennen_fehlgeschlagen_value_0_5f1ed952",
                    value_0=(e),
                ),
            )

    def _delete_category(self) -> None:
        """Löscht die ausgewählte Kategorie."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(
                self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie")
            )
            return

        decision = ask_category_delete_decision(self, conn=self.conn, cat_ids=[cat.id])
        if decision is None:
            return

        try:
            self.cat_model.delete_category_safely(
                cat.id,
                data_action=decision.action,
                reassign_to_id=decision.reassign_to_id,
                promote_children=True,
            )
            self._refresh_categories()
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.delete_failed", e=e))

    def _toggle_fix(self) -> None:
        """Fixkosten-Flag umschalten."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(
                self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie")
            )
            return

        try:
            self.cat_model.update_flags(cat.id, is_fix=not cat.is_fix)
            status = "aktiviert" if not cat.is_fix else "deaktiviert"
            QMessageBox.information(
                self,
                tr("msg.info"),
                trf("msg.fixcost_status_changed", cat_name=cat.name, status=status),
            )
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))

    def _toggle_recurring(self) -> None:
        """Wiederkehrend-Flag umschalten."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(
                self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie")
            )
            return

        try:
            self.cat_model.update_flags(cat.id, is_recurring=not cat.is_recurring)
            status = "aktiviert" if not cat.is_recurring else "deaktiviert"
            QMessageBox.information(
                self,
                tr("msg.info"),
                trf("msg.recurring_status_changed", cat_name=cat.name, status=status),
            )
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))

    def _set_day(self) -> None:
        """Fälligkeitstag setzen."""
        cat = self._get_selected_category()
        if not cat:
            QMessageBox.information(
                self, tr("msg.info"), tr("tab_ui.bitte_zuerst_eine_kategorie")
            )
            return

        day, ok = QInputDialog.getInt(
            self,
            tr("dlg.faelligkeitstag"),
            trf(
                "auto.views_budget_entry_dialog_extended.506_tag_im_monat_fuer_value_0_1_31_1fcfbede",
                value_0=(cat.name),
            ),
            cat.recurring_day,
            1,
            31,
        )
        if not ok:
            return

        try:
            self.cat_model.update_flags(cat.id, is_recurring=True, recurring_day=day)
            QMessageBox.information(
                self,
                "OK",
                trf(
                    "auto.views_budget_entry_dialog_extended.516_faelligkeitstag_fuer_value_0_auf_va_02c90616",
                    value_0=(cat.name),
                    value_1=(day),
                ),
            )
            self.category_changed.emit()
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("msg.change_failed", e=e))

    def check_and_create_if_needed(self) -> bool:
        """
        Prüft ob die eingegebene Kategorie existiert.
        Falls nicht, wird ein Dialog zum Erstellen angeboten.

        Returns: True wenn Kategorie existiert oder erstellt wurde, False bei Abbruch
        """
        name = self.get_category()
        if not name:
            return False

        # Prüfen ob Kategorie existiert
        existing = self.cat_model.list(self.typ)
        for cat in existing:
            if cat.name.casefold() == name.casefold():
                self.set_category(cat.name)
                return True

        # Kategorie existiert nicht -> Dialog anbieten
        reply = QMessageBox.question(
            self,
            tr("dlg.kategorie_nicht_gefunden"),
            trf("budget_entry.msg.category_missing_create", category=name),
            QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel,
        )

        if reply == QMessageBox.Cancel:
            return False

        if reply == QMessageBox.No:
            # Nicht mit einer nicht existierenden Kategorie fortfahren: Budget-
            # und Tracking-Tabellen referenzieren Kategorien historisch per Text.
            # Orphan-Namen würden Filter, Forecast und Auswertungen verfälschen.
            return False

        # Dialog zum Erstellen öffnen
        dlg = NewCategoryDialog(
            self,
            typ=self.typ,
            category_name=name,
            cat_model=self.cat_model,
            existing_categories=existing,
        )

        if dlg.exec() == QDialog.Accepted:
            created_name = dlg.get_created_name()
            self._refresh_categories()
            self.set_category(created_name)
            self.category_changed.emit()
            return True

        return False


class BudgetEntryDialogExtended(QDialog):
    """
    Erweiterter Budget-Entry-Dialog mit integrierter Kategorie-Verwaltung.

    Features:
    - Kategorie-ComboBox mit Management-Button
    - Automatische Erkennung neuer Kategorien
    - Inline-Erstellung von Kategorien mit Parent-Auswahl
    - Kategorie-Flags direkt setzen
    """

    def __init__(
        self,
        parent=None,
        *,
        conn: sqlite3.Connection,
        default_year: int,
        default_typ: str,
        preset: Optional[dict] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.budget_entry"))
        self.setModal(True)
        self.setMinimumWidth(500)

        self.conn = conn
        self.cat_model = CategoryModel(conn)

        # === Jahr und Typ ===
        self.year = QSpinBox()
        self.year.setRange(2000, 2100)
        self.year.setValue(default_year)

        self.typ = QComboBox()
        self.typ.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.typ.addItem(tr("kpi.income"), TYP_INCOME)
        self.typ.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        _idx = self.typ.findData(default_typ)
        if _idx >= 0:
            self.typ.setCurrentIndex(_idx)

        # === Kategorie-Management-Widget ===
        self.category_widget = CategoryManagementWidget(
            self, conn=conn, typ=default_typ
        )

        # === Betrag ===
        self.amount = QLineEdit()
        self.amount.setPlaceholderText(
            trf("lbl.example_amount", amount=format_short(1200))
        )

        # === Modus ===
        self.mode = QComboBox()
        self.mode.addItem(
            tr("auto.views_budget_entry_dialog_extended.620_monat_88dd17e2"),
            BUDGET_MODE_MONTH,
        )
        self.mode.addItem(tr("typ.Alle"), BUDGET_MODE_ALL)
        self.mode.addItem(
            tr("auto.views_budget_entry_dialog_extended.620_bereich_8b22d123"),
            BUDGET_MODE_RANGE,
        )

        self.month = QComboBox()
        self.month.addItems(_get_months())

        self.from_month = QComboBox()
        self.from_month.addItems(_get_months())

        self.to_month = QComboBox()
        self.to_month.addItems(_get_months())

        self.only_if_empty = QCheckBox(tr("dlg.nur_ueberschreiben_wenn_zelle"))
        self.only_if_empty.setChecked(False)

        # === Buttons ===
        self.btn_ok = QPushButton(tr("dlg.uebernehmen"))
        self.btn_ok.setDefault(True)
        self.btn_cancel = QPushButton(tr("btn.cancel"))

        # === Layout ===
        form = QFormLayout()
        form.addRow(tr("lbl.year"), self.year)
        form.addRow(tr("header.type"), self.typ)
        form.addRow(tr("lbl.category"), self.category_widget)
        form.addRow(
            trf("lbl.amount_with_currency", currency=currency_header()), self.amount
        )

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        form.addRow(line)

        form.addRow(tr("lbl.mode"), self.mode)
        form.addRow(tr("lbl.month"), self.month)
        form.addRow(tr("lbl.from"), self.from_month)
        form.addRow(tr("lbl.to"), self.to_month)
        form.addRow("", self.only_if_empty)

        btns = QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btn_ok)
        btns.addWidget(self.btn_cancel)

        root = QVBoxLayout()
        root.addLayout(form)
        root.addLayout(btns)
        self.setLayout(root)

        # === Signale ===
        self.mode.currentIndexChanged.connect(lambda _: self._mode_changed())
        self.typ.currentIndexChanged.connect(
            lambda _: self._typ_changed(
                self.typ.currentData() or self.typ.currentText()
            )
        )
        self.btn_ok.clicked.connect(self._validate_and_accept)
        self.btn_cancel.clicked.connect(self.reject)

        self._mode_changed()

        if preset:
            self._apply_preset(preset)

    def _typ_changed(self, typ: str) -> None:
        """Aktualisiert die Kategorie-Liste bei Typwechsel."""
        self.category_widget.set_typ(typ)

    def _current_mode(self) -> str:
        return normalize_budget_mode(self.mode.currentData() or self.mode.currentText())

    def _set_mode(self, value: object) -> None:
        mode = normalize_budget_mode(value)
        idx = self.mode.findData(mode)
        if idx >= 0:
            self.mode.setCurrentIndex(idx)

    def _mode_changed(self) -> None:
        mode = self._current_mode()
        is_month = mode == BUDGET_MODE_MONTH
        is_range = mode == BUDGET_MODE_RANGE
        self.month.setEnabled(is_month)
        self.from_month.setEnabled(is_range)
        self.to_month.setEnabled(is_range)

    def _apply_preset(self, preset: dict) -> None:
        if "category" in preset and preset["category"]:
            self.category_widget.set_category(str(preset["category"]))
        if "amount" in preset and preset["amount"] is not None:
            self.amount.setText(str(preset["amount"]))
        if "month" in preset and preset["month"]:
            self.month.setCurrentIndex(int(preset["month"]) - 1)
        if "mode" in preset and preset["mode"]:
            self._set_mode(preset["mode"])
        if "from_month" in preset and preset["from_month"]:
            self.from_month.setCurrentIndex(int(preset["from_month"]) - 1)
        if "to_month" in preset and preset["to_month"]:
            self.to_month.setCurrentIndex(int(preset["to_month"]) - 1)
        if "only_if_empty" in preset:
            self.only_if_empty.setChecked(bool(preset["only_if_empty"]))

    def _validate_and_accept(self) -> None:
        # Kategorie prüfen/erstellen
        if not self.category_widget.check_and_create_if_needed():
            return

        cat = self.category_widget.get_category()
        if not cat:
            QMessageBox.warning(
                self,
                tr("auto.views_budget_entry_dialog_extended.715_fehlt_2f708b3e"),
                tr("dlg.bitte_kategorie_auswaehleneingeben"),
            )
            return

        try:
            amt = parse_amount(self.amount.text())
        except Exception:
            QMessageBox.warning(self, tr("dlg.hinweis"), tr("dlg.betrag_ist_ungueltig"))
            return

        # Ausgaben: negative Zahlen verhindern
        typ_data = self.typ.currentData() or self.typ.currentText()
        if typ_data == TYP_EXPENSES and amt < 0:
            QMessageBox.warning(
                self, tr("dlg.nicht_erlaubt"), tr("dlg.bei_ausgaben_sind_negative")
            )
            return

        self.accept()

    def get_request(self) -> BudgetEntryRequest:
        mode = self._current_mode()
        month = self.month.currentIndex() + 1
        fm = self.from_month.currentIndex() + 1
        tm = self.to_month.currentIndex() + 1
        amt = parse_amount(self.amount.text())

        return BudgetEntryRequest(
            year=int(self.year.value()),
            typ=str(self.typ.currentData() or self.typ.currentText()),
            category=str(self.category_widget.get_category()),
            amount=float(amt),
            mode=str(mode),
            month=int(month),
            from_month=int(fm),
            to_month=int(tm),
            only_if_empty=bool(self.only_if_empty.isChecked()),
        )
