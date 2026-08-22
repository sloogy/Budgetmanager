"""
Kategorie-Eigenschaften-Dialog für schnelle Bearbeitung.

Features:
- Einfache Bearbeitung von Name, Fixkosten, Wiederkehrend, Tag
- Parent-Kategorie ändern
- Bulk-Edit für mehrere Kategorien
"""

from __future__ import annotations

import logging
import sqlite3

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from model.category_forecast_mode import (
    FORECAST_MODE_AUTO,
    FORECAST_MODE_INCREMENTAL,
    FORECAST_MODE_NORMAL,
    FORECAST_MODE_POT,
)
from model.category_model import Category, CategoryModel
from model.tags_model import TagsModel
from utils.accessibility import configure_dialog_tab_order
from utils.i18n import db_typ_from_display, tr, trf
from utils.icons import get_icon
from utils.notifications import show_info, show_warning
from views.category_delete_dialog import ask_category_delete_decision

logger = logging.getLogger(__name__)


class CategoryPropertiesDialog(QDialog):
    """Dialog zum Bearbeiten einer einzelnen Kategorie."""

    category_updated = Signal()  # Wird ausgelöst wenn Änderungen gespeichert wurden

    def __init__(
        self, parent=None, *, conn: sqlite3.Connection, category_name: str, typ: str
    ):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self.tags_model = TagsModel(conn)
        self.typ = typ
        self.original_name = category_name

        # Kategorie laden
        self.category = self._find_category(category_name)
        if not self.category:
            show_warning(
                self,
                tr("dlg.hinweis"),
                trf("msg.kategorie_nicht_gefunden_name", category_name=category_name),
            )
            self.reject()
            return

        self.setWindowTitle(trf("dlg.category_edit_title", name=category_name))
        self.setModal(True)
        self.setMinimumWidth(450)

        self._build_ui()
        self._load_data()
        configure_dialog_tab_order(self)

    def _find_category(self, name: str) -> Category | None:
        for cat in self.cat_model.list(self.typ):
            if cat.name == name:
                return cat
        return None

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # === Basis-Eigenschaften ===
        basic_group = QGroupBox(tr("grp.base_properties"))
        form = QFormLayout(basic_group)

        self.name_edit = QLineEdit()
        form.addRow(tr("lbl.name"), self.name_edit)

        self.typ_label = QLabel(
            trf(
                "auto.views_category_properties_dialog.72_b_value_0_b_dba5f175",
                value_0=(self.typ),
            )
        )
        form.addRow(tr("header.type"), self.typ_label)

        # Parent-Kategorie
        self.parent_combo = QComboBox()
        self.parent_combo.addItem(tr("dlg.keine_hauptkategorie"), None)
        for cat in self.cat_model.list(self.typ):
            if cat.id != self.category.id:  # Sich selbst nicht als Parent erlauben
                indent = "  " if cat.parent_id else ""
                self.parent_combo.addItem(f"{indent}{cat.name}", cat.id)
        form.addRow(tr("lbl.parent_category"), self.parent_combo)

        layout.addWidget(basic_group)

        # === Flags ===
        flags_group = QGroupBox(tr("dlg.eigenschaften_fuer_fixkosten_wiederkehrende"))
        flags_layout = QGridLayout(flags_group)

        self.chk_fix = QCheckBox(tr("tracking.title.fixcosts"))
        self.chk_fix.setToolTip(tr("help.tip.fixcost"))
        flags_layout.addWidget(self.chk_fix, 0, 0)

        self.chk_recurring = QCheckBox(tr("lbl.recurring"))
        self.chk_recurring.setToolTip(tr("help.tip.recurring"))
        flags_layout.addWidget(self.chk_recurring, 0, 1)

        # Tag im Monat
        day_layout = QHBoxLayout()
        day_layout.addWidget(QLabel(tr("dlg.faelligkeitstag_1")))
        self.day_spin = QSpinBox()
        self.day_spin.setAccessibleName(tr("dlg.faelligkeitstag_setzen"))
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(CategoryModel.preferred_recurring_day())
        self.day_spin.setSuffix(tr("categories.day_suffix"))
        self.day_spin.setToolTip(tr("tip.due_day"))
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

        # Hinweis
        hint = QLabel(
            tr(
                "auto.views_category_properties_dialog.117_small_i_tipp_wenn_du_einen_faelligk_01c58f1d"
            )
        )
        hint.setWordWrap(True)
        flags_layout.addWidget(hint, 3, 0, 1, 2)

        layout.addWidget(flags_group)

        # === Fixe Kategorie-Tags ===
        tags_group = QGroupBox(tr("categories.fixed_tags.label"))
        tags_layout = QVBoxLayout(tags_group)
        tags_hint = QLabel(tr("categories.fixed_tags.tip"))
        tags_hint.setWordWrap(True)
        tags_layout.addWidget(tags_hint)
        self.tag_list = QListWidget()
        self.tag_list.setMaximumHeight(130)
        self.tag_list.setAlternatingRowColors(True)
        tags_layout.addWidget(self.tag_list)
        layout.addWidget(tags_group)
        self._fill_tag_list()

        # === Buttons ===
        btn_layout = QHBoxLayout()

        self.btn_delete = QPushButton(tr("btn.loeschen_1"))
        self.btn_delete.setStyleSheet("")  # Theme handles button colors
        btn_layout.addWidget(self.btn_delete)

        btn_layout.addStretch()

        self.btn_cancel = QPushButton(tr("btn.cancel"))
        btn_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton(tr("btn.save"))
        self.btn_save.setIcon(get_icon("💾"))
        self.btn_save.setDefault(True)
        btn_layout.addWidget(self.btn_save)

        layout.addLayout(btn_layout)

        # Signale
        self.chk_recurring.toggled.connect(self._on_recurring_toggled)
        self.day_spin.valueChanged.connect(self._on_day_changed)
        self.btn_save.clicked.connect(self._save)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_delete.clicked.connect(self._delete)

    def _fill_tag_list(self) -> None:
        """Lädt alle Tags als Mehrfach-Auswahl für fixe Kategorie-Tags."""
        self.tag_list.clear()
        try:
            tags = self.tags_model.list_all()
        except Exception:
            tags = []
        if not tags:
            item = QListWidgetItem(tr("tags.no_tags_click_create"))
            item.setFlags(Qt.NoItemFlags)
            self.tag_list.addItem(item)
            return
        for tag in tags:
            item = QListWidgetItem(str(tag.name))
            item.setData(Qt.UserRole, int(tag.id))
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.tag_list.addItem(item)

    def _selected_category_tag_ids(self) -> list[int]:
        ids: list[int] = []
        for i in range(self.tag_list.count()):
            item = self.tag_list.item(i)
            if not item or not (item.flags() & Qt.ItemIsUserCheckable):
                continue
            if item.checkState() == Qt.Checked:
                ids.append(int(item.data(Qt.UserRole)))
        return ids

    def _load_data(self) -> None:
        self.name_edit.setText(self.category.name)

        # Parent setzen
        if self.category.parent_id:
            idx = self.parent_combo.findData(self.category.parent_id)
            if idx >= 0:
                self.parent_combo.setCurrentIndex(idx)

        self.chk_fix.setChecked(self.category.is_fix)
        self.chk_recurring.setChecked(self.category.is_recurring)
        self.day_spin.setValue(
            int(self.category.recurring_day)
            if self.category.is_recurring
            else CategoryModel.preferred_recurring_day()
        )
        self.day_spin.setEnabled(self.category.is_recurring)
        idx = self.forecast_mode.findData(
            getattr(self.category, "forecast_mode", FORECAST_MODE_AUTO)
        )
        self.forecast_mode.setCurrentIndex(idx if idx >= 0 else 0)
        try:
            fixed_ids = {
                int(t.id)
                for t in self.tags_model.get_tags_for_category(self.category.id)
            }
            for i in range(self.tag_list.count()):
                item = self.tag_list.item(i)
                if item and (item.flags() & Qt.ItemIsUserCheckable):
                    item.setCheckState(
                        Qt.Checked
                        if int(item.data(Qt.UserRole)) in fixed_ids
                        else Qt.Unchecked
                    )
        except Exception as exc:
            logger.debug("Kategorie-Tags konnten nicht geladen werden: %s", exc)

    def _on_recurring_toggled(self, checked: bool) -> None:
        self.day_spin.setEnabled(checked)
        if checked and not self.category.is_recurring:
            self.day_spin.setValue(CategoryModel.preferred_recurring_day())

    def _on_day_changed(self, value: int) -> None:
        # Wenn Tag geändert wird, Wiederkehrend automatisch aktivieren
        if value > 0 and not self.chk_recurring.isChecked():
            self.chk_recurring.setChecked(True)

    def _save(self) -> None:
        new_name = self.name_edit.text().strip()
        if not new_name:
            show_warning(
                self, tr("dlg.hinweis"), tr("account.bitte_einen_namen_eingeben")
            )
            return

        # Prüfen ob neuer Name bereits existiert (wenn umbenannt)
        if new_name != self.category.name:
            for cat in self.cat_model.list(self.typ):
                if cat.name.lower() == new_name.lower() and cat.id != self.category.id:
                    show_warning(
                        self,
                        tr("msg.error"),
                        trf(
                            "auto.views_category_properties_dialog.185_eine_kategorie_mit_dem_namen_value__53b9f84f",
                            value_0=(new_name),
                        ),
                    )
                    return

        try:
            # Name ändern (mit Cascade zu Budget/Tracking)
            if new_name != self.category.name:
                self.cat_model.rename_and_cascade(
                    self.category.id,
                    typ=self.typ,
                    old_name=self.category.name,
                    new_name=new_name,
                )

            # Parent ändern
            new_parent_id = self.parent_combo.currentData()
            if new_parent_id != self.category.parent_id:
                self.cat_model.update_parent(self.category.id, new_parent_id)

            # Flags speichern
            is_fix = self.chk_fix.isChecked()
            is_recurring = self.chk_recurring.isChecked()
            recurring_day = self.day_spin.value() if is_recurring else 1

            self.cat_model.update_flags(
                self.category.id,
                is_fix=is_fix,
                is_recurring=is_recurring,
                recurring_day=recurring_day,
                forecast_mode=str(
                    self.forecast_mode.currentData() or FORECAST_MODE_AUTO
                ),
            )
            self.tags_model.set_category_tags(
                self.category.id, self._selected_category_tag_ids()
            )

            self.category_updated.emit()
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_category_properties_dialog.220_speichern_fehlgeschlagen_value_0_3a729058",
                    value_0=(e),
                ),
            )

    def _delete(self) -> None:
        decision = ask_category_delete_decision(
            self, conn=self.conn, cat_ids=[self.category.id]
        )
        if decision is None:
            return

        try:
            self.cat_model.delete_category_safely(
                self.category.id,
                data_action=decision.action,
                reassign_to_id=decision.reassign_to_id,
                promote_children=True,
            )
            self.category_updated.emit()
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_category_properties_dialog.254_loeschen_fehlgeschlagen_value_0_833e313c",
                    value_0=(e),
                ),
            )


class BulkCategoryEditDialog(QDialog):
    """Dialog zum Bearbeiten mehrerer Kategorien gleichzeitig."""

    categories_updated = Signal()

    def __init__(
        self,
        parent=None,
        *,
        conn: sqlite3.Connection,
        categories: list[tuple[str, str]],
    ):  # List of (name, typ)
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)
        self.categories = categories  # [(name, typ), ...]

        self.setWindowTitle(trf("dlg.mass_edit_title", count=len(categories)))
        self.setModal(True)
        self.setMinimumWidth(500)

        self._build_ui()
        configure_dialog_tab_order(self)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Info
        info = QLabel(
            trf(
                "dlg.blenselfcategoriesb_kategorien_ausgewaehlt",
                count=len(self.categories),
            )
        )
        layout.addWidget(info)

        # Liste der ausgewählten Kategorien
        self.list_widget = QListWidget()
        self.list_widget.setMaximumHeight(100)
        for name, typ in self.categories:
            self.list_widget.addItem(
                trf(
                    "auto.views_category_properties_dialog.286_value_0_value_1_90606f5a",
                    value_0=(name),
                    value_1=(typ),
                )
            )
        layout.addWidget(self.list_widget)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        line.setFrameShadow(QFrame.Sunken)
        layout.addWidget(line)

        # === Änderungen ===
        changes_group = QGroupBox(tr("dlg.aenderungen_anwenden"))
        form = QFormLayout(changes_group)

        # Fixkosten
        self.fix_combo = QComboBox()
        self.fix_combo.addItems(
            [
                tr("dlg.nicht_aendern"),
                tr("categories.activate"),
                tr("categories.deactivate"),
            ]
        )
        form.addRow(tr("tracking.title.fixcosts"), self.fix_combo)

        # Wiederkehrend
        self.rec_combo = QComboBox()
        self.rec_combo.addItems(
            [
                tr("dlg.nicht_aendern"),
                tr("categories.activate"),
                tr("categories.deactivate"),
            ]
        )
        form.addRow(tr("lbl.recurring"), self.rec_combo)

        # Tag
        day_layout = QHBoxLayout()
        self.day_check = QCheckBox(tr("dlg.faelligkeitstag_setzen"))
        self.day_spin = QSpinBox()
        self.day_spin.setAccessibleName(tr("dlg.faelligkeitstag_setzen"))
        self.day_spin.setRange(1, 31)
        self.day_spin.setValue(CategoryModel.preferred_recurring_day())
        self.day_spin.setSuffix(tr("categories.day_suffix"))
        self.day_spin.setEnabled(False)
        day_layout.addWidget(self.day_check)
        day_layout.addWidget(self.day_spin)
        day_layout.addStretch()
        form.addRow("", day_layout)

        layout.addWidget(changes_group)

        # Hinweis
        hint = QLabel(
            tr(
                "auto.views_category_properties_dialog.325_small_i_hinweis_wenn_du_einen_faell_5237905b"
            )
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)

        # === Buttons ===
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Signale
        self.day_check.toggled.connect(self.day_spin.setEnabled)

    def _apply(self) -> None:
        fix_choice = self.fix_combo.currentIndex()
        rec_choice = self.rec_combo.currentIndex()
        set_day = self.day_check.isChecked()
        day_val = self.day_spin.value()

        if fix_choice == 0 and rec_choice == 0 and not set_day:
            show_info(self, tr("dlg.hinweis"), tr("msg.no_changes_selected"))
            return

        changed = 0
        errors = []

        for name, typ in self.categories:
            cat = None
            for c in self.cat_model.list(typ):
                if c.name == name:
                    cat = c
                    break

            if not cat:
                errors.append(f"{name} ({typ})")
                continue

            try:
                kwargs = {}

                if fix_choice == 1:
                    kwargs["is_fix"] = True
                elif fix_choice == 2:
                    kwargs["is_fix"] = False

                if rec_choice == 1:
                    kwargs["is_recurring"] = True
                elif rec_choice == 2:
                    kwargs["is_recurring"] = False

                if set_day:
                    kwargs["is_recurring"] = True
                    kwargs["recurring_day"] = day_val

                if kwargs:
                    self.cat_model.update_flags(cat.id, **kwargs)
                    changed += 1

            except Exception as e:
                errors.append(f"{name}: {e}")

        msg = f"{changed} Kategorie(n) aktualisiert."
        if errors:
            msg += "\n\nFehler bei:\n" + "\n".join(errors[:10])

        show_info(
            self, tr("auto.views_category_properties_dialog.397_ergebnis_0d350353"), msg
        )

        if changed > 0:
            self.categories_updated.emit()

        self.accept()


class QuickCategoryDialog(QDialog):
    """Schneller Dialog zum Erstellen einer neuen Kategorie."""

    category_created = Signal(str, str)  # name, typ

    def __init__(
        self,
        parent=None,
        *,
        conn: sqlite3.Connection,
        default_typ: str = tr("kpi.expenses"),
        default_name: str = "",
    ):
        super().__init__(parent)
        self.conn = conn
        self.cat_model = CategoryModel(conn)

        self.setWindowTitle(tr("dlg.category_create"))
        self.setModal(True)
        self.setMinimumWidth(400)

        self._build_ui(default_typ, default_name)
        configure_dialog_tab_order(self)

    def _build_ui(self, default_typ: str, default_name: str) -> None:
        layout = QVBoxLayout(self)

        form = QFormLayout()

        # Name
        self.name_edit = QLineEdit(default_name)
        self.name_edit.setPlaceholderText(
            tr(
                "auto.views_category_properties_dialog.429_z_b_versicherung_streaming_6d95c073"
            )
        )
        form.addRow(tr("lbl.name"), self.name_edit)

        # Typ
        from model.typ_constants import TYP_EXPENSES, TYP_INCOME, TYP_SAVINGS

        self.typ_combo = QComboBox()
        self.typ_combo.addItem(tr("kpi.expenses"), TYP_EXPENSES)
        self.typ_combo.addItem(tr("kpi.income"), TYP_INCOME)
        self.typ_combo.addItem(tr("typ.Ersparnisse"), TYP_SAVINGS)
        # Setze default via data (DB-Key) oder fallback via display text
        _idx = self.typ_combo.findData(default_typ)
        if _idx < 0:
            _idx = self.typ_combo.findText(default_typ)
        if _idx >= 0:
            self.typ_combo.setCurrentIndex(_idx)
        form.addRow(tr("header.type"), self.typ_combo)

        # Parent (dynamisch basierend auf Typ)
        self.parent_combo = QComboBox()
        form.addRow(tr("lbl.parent_category"), self.parent_combo)

        layout.addLayout(form)

        # Separator
        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        layout.addWidget(line)

        # Quick-Flags
        flags_layout = QHBoxLayout()
        self.chk_fix = QCheckBox(tr("tracking.title.fixcosts"))
        self.chk_fix.setToolTip(tr("help.tip.fixcost"))
        self.chk_recurring = QCheckBox(tr("lbl.recurring"))
        self.chk_recurring.setToolTip(tr("help.tip.recurring"))
        flags_layout.addWidget(self.chk_fix)
        flags_layout.addWidget(self.chk_recurring)
        flags_layout.addStretch()
        layout.addLayout(flags_layout)

        forecast_layout = QHBoxLayout()
        forecast_layout.addWidget(QLabel(tr("forecast.mode.label")))
        self.forecast_mode = QComboBox()
        self.forecast_mode.addItem(tr("forecast.mode.auto"), FORECAST_MODE_AUTO)
        self.forecast_mode.addItem(tr("forecast.mode.pot"), FORECAST_MODE_POT)
        self.forecast_mode.addItem(
            tr("forecast.mode.incremental"), FORECAST_MODE_INCREMENTAL
        )
        self.forecast_mode.addItem(tr("forecast.mode.normal"), FORECAST_MODE_NORMAL)
        self.forecast_mode.setToolTip(tr("forecast.mode.tooltip"))
        forecast_layout.addWidget(self.forecast_mode, 1)
        layout.addLayout(forecast_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_cancel = QPushButton(tr("btn.cancel"))
        btn_layout.addWidget(self.btn_cancel)

        self.btn_create = QPushButton(
            tr("auto.views_category_properties_dialog.473_erstellen_482a728e")
        )
        self.btn_create.setDefault(True)
        btn_layout.addWidget(self.btn_create)

        layout.addLayout(btn_layout)

        # Signale
        self.typ_combo.currentTextChanged.connect(self._update_parents)
        self.btn_cancel.clicked.connect(self.reject)
        self.btn_create.clicked.connect(self._create)

        # Initial parents laden
        self._update_parents(default_typ)

    def _update_parents(self, typ_display: str) -> None:
        typ = self.typ_combo.currentData() or db_typ_from_display(typ_display)
        self.parent_combo.clear()
        self.parent_combo.addItem(
            tr(
                "auto.views_category_properties_dialog.490_hauptkategorie_kein_parent_90e59485"
            ),
            None,
        )

        for cat in self.cat_model.list(typ):
            indent = "  " if cat.parent_id else ""
            self.parent_combo.addItem(f"{indent}{cat.name}", cat.id)

    def _create(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            show_warning(
                self, tr("dlg.hinweis"), tr("account.bitte_einen_namen_eingeben")
            )
            return

        typ = self.typ_combo.currentData() or db_typ_from_display(
            self.typ_combo.currentText()
        )

        # Prüfen ob Name bereits existiert
        for cat in self.cat_model.list(typ):
            if cat.name.lower() == name.lower():
                show_warning(
                    self,
                    tr("msg.error"),
                    trf(
                        "auto.views_category_properties_dialog.509_eine_kategorie_mit_dem_namen_value__1f3513d0",
                        value_0=(name),
                    ),
                )
                return

        try:
            parent_id = self.parent_combo.currentData()
            is_fix = self.chk_fix.isChecked()
            is_recurring = self.chk_recurring.isChecked()
            forecast_mode = str(self.forecast_mode.currentData() or FORECAST_MODE_AUTO)

            self.cat_model.create(
                typ=typ,
                name=name,
                is_fix=is_fix,
                is_recurring=is_recurring,
                parent_id=parent_id,
                forecast_mode=forecast_mode,
            )

            self.category_created.emit(name, typ)
            self.accept()

        except Exception as e:
            QMessageBox.critical(
                self,
                tr("msg.error"),
                trf(
                    "auto.views_category_properties_dialog.530_erstellen_fehlgeschlagen_value_0_bb0f3855",
                    value_0=(e),
                ),
            )

    def get_created_name(self) -> str:
        return self.name_edit.text().strip()

    def get_created_typ(self) -> str:
        return self.typ_combo.currentData() or db_typ_from_display(
            self.typ_combo.currentText()
        )
