"""Erstes-Start Sprach-Auswahl Dialog."""
from __future__ import annotations
from utils.i18n import tr, trf
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QListWidget, QListWidgetItem
)
from views.ui_colors import ui_colors


class LanguageSelectDialog(QDialog):
    """Erscheint beim ersten Start – User wählt die Sprache."""

    LANGUAGES = [
        ("de", "🇩🇪  Deutsch"),
        ("en", "🇬🇧  English"),
        ("fr", "🇫🇷  Français"),
    ]

    def __init__(self, parent=None, *, current: str = "de"):
        super().__init__(parent)
        self.setWindowTitle(tr('auto.views_language_select_dialog.22_language_sprache_langue_cec30925'))
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(340)
        self.selected_code = current
        self._build_ui(current)

    def _build_ui(self, current: str = "de"):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        c = ui_colors(self)
        lbl = QLabel(
            trf('auto.views_language_select_dialog.34_h3_style_margin_0_welcome_willkomme_eef30112', value_0=(c.text_dim))
        )
        lbl.setTextFormat(Qt.RichText)
        lay.addWidget(lbl)

        self.list = QListWidget()
        self.list.setSpacing(4)
        default_row = 0
        for i, (code, label) in enumerate(self.LANGUAGES):
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, code)
            item.setSizeHint(item.sizeHint().__class__(0, 42))
            self.list.addItem(item)
            if code == current:
                default_row = i
        self.list.setCurrentRow(default_row)
        self.list.itemDoubleClicked.connect(self._accept)
        lay.addWidget(self.list)

        btn_row = QHBoxLayout()
        btn_ok = QPushButton(tr('auto.views_language_select_dialog.57_ok_6128635b'))
        btn_ok.setDefault(True)
        btn_ok.setMinimumHeight(36)
        btn_ok.clicked.connect(self._accept)
        btn_row.addStretch()
        btn_row.addWidget(btn_ok)
        lay.addLayout(btn_row)

    def _accept(self):
        item = self.list.currentItem()
        if item:
            self.selected_code = item.data(Qt.UserRole)
        self.accept()
