from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from model.shortcuts_config import (
    SHORTCUT_DEFS,
    group_for,
    label_for,
    load_shortcuts,
    shortcut_display_name,
)
from utils.i18n import tr, trf, display_typ, db_typ_from_display


class ShortcutsDialog(QDialog):
    """Zeigt alle verfügbaren Tastenkürzel an (F1).

    Liest die *aktuell konfigurierten* Kürzel aus den Settings,
    sodass benutzerdefinierte Overrides korrekt dargestellt werden.
    """

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.setWindowTitle(tr("dlg.shortcuts"))
        self.setMinimumSize(560, 640)

        layout = QVBoxLayout()

        # Titel
        title = QLabel(tr("dlg.h2tastenkuerzelh2"))
        layout.addWidget(title)

        # Aktuelle Shortcuts laden (mit Overrides)
        if settings is not None:
            shortcuts_map = load_shortcuts(settings)
        else:
            # Fallback: nur Defaults
            shortcuts_map = {aid: key for aid, key, _l, _g in SHORTCUT_DEFS}

        # Tabelle
        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(
            [tr("dlg.shortcuts"), tr("header.action"), tr("header.group")]
        )
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)

        # Zeilen aufbauen – mit Gruppen-Trennern
        rows: list[tuple[str, str, str]] = []  # (key_display, label, group)
        last_group = ""
        for aid, _dkey, _label_key, _group_key in SHORTCUT_DEFS:
            label = label_for(aid)
            group = group_for(aid)
            if group != last_group:
                if last_group:
                    rows.append(("", "", ""))  # Leerzeile als Trenner
                last_group = group
            key_str = shortcuts_map.get(aid, _dkey)
            rows.append((shortcut_display_name(key_str), label, group))

        # Zusätzliche Hinweise (nicht konfigurierbar)
        rows.append(("", "", ""))
        rows.append(
            ("Enter", tr("dlg.in_tabelle_naechste_zelle"), tr("shortcut.group.table"))
        )
        rows.append(("Tab", tr("dlg.zum_naechsten_feld"), tr("shortcut.group.table")))
        rows.append(("Escape", tr("btn.dialog_schliessen"), tr("shortcut.group.table")))

        self.table.setRowCount(len(rows))
        bold = QFont()
        bold.setBold(True)

        for i, (key, action, grp) in enumerate(rows):
            key_item = QTableWidgetItem(key)
            key_item.setTextAlignment(Qt.AlignCenter)
            if key:
                key_item.setFont(bold)
            self.table.setItem(i, 0, key_item)

            action_item = QTableWidgetItem(action)
            self.table.setItem(i, 1, action_item)

            grp_item = QTableWidgetItem(grp)
            grp_item.setForeground(Qt.gray)
            self.table.setItem(i, 2, grp_item)

        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setColumnWidth(0, 160)

        layout.addWidget(self.table)

        # Tipp
        tip = QLabel(
            tr(
                "auto.views_shortcuts_dialog.92_i_tipp_tastenkuerzel_koennen_unter__17d1ba87"
            )
        )
        tip.setWordWrap(True)
        layout.addWidget(tip)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.setLayout(layout)
