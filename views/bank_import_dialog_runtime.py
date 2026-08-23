"""Zusätzliche Bedienlogik für den aktiven Bankimport.

Der kanonische Review-Dialog bleibt in ``bank_import_dialog``. Diese dünne
Runtime-Schicht ergänzt drei Bedienregeln, die bewusst nichts an der
Import-/TWINT-Fachlogik ändern:

- Tags können direkt aus dem Import heraus erstellt werden.
- Alle sichtbaren Importzeilen können gemeinsam an-/abgewählt werden.
- Filter verstecken nicht nur Zeilen, sondern nehmen sie auch aus der
  Mehrfachauswahl. Shift, Strg+A und die Massenbearbeitung wirken dadurch nur
  auf Zeilen, die der Nutzer tatsächlich sieht.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QPushButton,
    QTableWidgetSelectionRange,
    QVBoxLayout,
)

from utils.i18n import tr, trf
from utils.notifications import show_info, show_warning
from views.bank_import_dialog import (
    BankImportDialog as _BankImportDialog,
    CheckableTagCombo,
)


class BankImportDialog(_BankImportDialog):
    """Aktiver Importdialog mit sichtbarkeitsgebundener Mehrfachauswahl."""

    def __init__(self, conn, parent=None):
        super().__init__(conn, parent)
        self._visible_selection_guard = False
        self._install_visibility_controls()
        self.table.itemSelectionChanged.connect(self._drop_hidden_selection)

    def _install_visibility_controls(self) -> None:
        controls = QHBoxLayout()

        self.btn_create_tag = QPushButton(tr("tags.create_inline"))
        self.btn_create_tag.setToolTip(tr("tags.create_inline_tip"))
        self.btn_create_tag.clicked.connect(self._create_tag_inline)
        controls.addWidget(self.btn_create_tag)

        controls.addStretch(1)

        self.btn_select_all_visible = QPushButton(tr("btn.select_all"))
        self.btn_select_all_visible.setToolTip(tr("bank_import.bulk_use_checked"))
        self.btn_select_all_visible.clicked.connect(
            lambda: self._set_visible_import_checked(True)
        )
        controls.addWidget(self.btn_select_all_visible)

        self.btn_deselect_all_visible = QPushButton(tr("btn.deselect_all"))
        self.btn_deselect_all_visible.setToolTip(tr("bank_import.bulk_use_unchecked"))
        self.btn_deselect_all_visible.clicked.connect(
            lambda: self._set_visible_import_checked(False)
        )
        controls.addWidget(self.btn_deselect_all_visible)

        root = self.layout()
        if isinstance(root, QVBoxLayout):
            root.insertLayout(4, controls)

    def _create_tag_inline(self) -> None:
        """Erstellt einen Tag wie in der Schnelleingabe und lädt Picker neu."""
        name, ok = QInputDialog.getText(
            self,
            tr("tags.create_title"),
            tr("tags.create_name_label"),
        )
        if not ok or not name.strip():
            return
        name = name.strip()

        if self.tags.name_exists(name):
            show_warning(
                self,
                tr("auto.views_tags_manager_dialog.221_tag_existiert_20291c3b"),
                trf(
                    "auto.views_tags_manager_dialog.222_ein_tag_mit_dem_namen_value_0_exist_be543b1c",
                    value_0=name,
                ),
            )
            return

        action_text, ok_action = QInputDialog.getText(
            self,
            tr("tags.action_text_title"),
            tr("tags.action_text_label"),
            text="",
        )
        if not ok_action:
            action_text = ""

        tag_id = self.tags.create_tag(name, action_text=action_text.strip())
        if not tag_id:
            show_warning(
                self,
                tr("msg.error"),
                tr(
                    "auto.views_tags_manager_dialog.255_tag_konnte_nicht_erstellt_werden_955e67d7"
                ),
            )
            return

        self._reload_tag_controls(preferred=name)
        show_info(
            self,
            tr("msg.success"),
            trf(
                "auto.views_tags_manager_dialog.249_tag_value_0_wurde_erstellt_3d280c8d",
                value_0=name,
            ),
        )

    def _reload_tag_controls(self, *, preferred: str = "") -> None:
        """Aktualisiert alle Tag-Dropdowns ohne bestehende Auswahl zu verlieren."""
        self._tag_catalog = tuple(
            sorted((tag.name for tag in self.tags.list_all()), key=str.casefold)
        )

        self._updating_row = True
        try:
            for row in range(self.table.rowCount()):
                current = self.table.cellWidget(row, self.COL_TAGS)
                selected = (
                    current.selected_tags()
                    if isinstance(current, CheckableTagCombo)
                    else ()
                )
                fixed = self._category_tag_names(*self._selected_category_identity(row))
                combo = CheckableTagCombo(
                    self._tag_catalog,
                    selected=selected,
                    locked=fixed,
                    parent=self.table,
                )
                combo.tagsChanged.connect(
                    lambda current_row=row: self._tag_selection_changed(current_row)
                )
                self.table.setCellWidget(row, self.COL_TAGS, combo)

            current_bulk = str(self.cmb_bulk_tag.currentData() or "")
            self.cmb_bulk_tag.blockSignals(True)
            try:
                self.cmb_bulk_tag.clear()
                self.cmb_bulk_tag.addItem(tr("bank_import.bulk_tag_keep"), "")
                for tag_name in self._tag_catalog:
                    self.cmb_bulk_tag.addItem(tag_name, tag_name)
                wanted = preferred or current_bulk
                wanted_index = self.cmb_bulk_tag.findData(wanted)
                if wanted_index >= 0:
                    self.cmb_bulk_tag.setCurrentIndex(wanted_index)
            finally:
                self.cmb_bulk_tag.blockSignals(False)
        finally:
            self._updating_row = False

        self._refresh_effective_view()
        self._apply_search_filter()

    def _set_visible_import_checked(self, checked: bool) -> None:
        """Setzt nur sichtbare, tatsächlich checkbare Import-/KI-Zeilen."""
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._updating_row = True
        try:
            for row in range(self.table.rowCount()):
                if self.table.isRowHidden(row):
                    continue
                item = self.table.item(row, self.COL_USE)
                if item is None:
                    continue
                if not (item.flags() & Qt.ItemFlag.ItemIsUserCheckable):
                    continue
                item.setCheckState(state)
        finally:
            self._updating_row = False
        self._refresh_effective_view()

    def _drop_hidden_selection(self) -> None:
        """Entfernt gefilterte Zeilen aus Shift-/Strg-Auswahlen."""
        if getattr(self, "_visible_selection_guard", False):
            return
        self._visible_selection_guard = True
        try:
            last_column = max(0, self.table.columnCount() - 1)
            for row in range(self.table.rowCount()):
                if not self.table.isRowHidden(row):
                    continue
                self.table.setRangeSelected(
                    QTableWidgetSelectionRange(row, 0, row, last_column),
                    False,
                )
        finally:
            self._visible_selection_guard = False

    def _apply_search_filter(self, _text: str = "") -> None:
        super()._apply_search_filter(_text)
        self._drop_hidden_selection()

    def _selected_rows(self) -> list[int]:
        """Massenbearbeitung sieht ausschließlich aktuell sichtbare Zeilen."""
        return [
            row for row in super()._selected_rows() if not self.table.isRowHidden(row)
        ]


__all__ = ["BankImportDialog"]
