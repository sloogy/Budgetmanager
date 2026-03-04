"""Erstes-Start Sprach-Auswahl Dialog."""
from __future__ import annotations
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
        self.setWindowTitle("Language / Sprache / Langue")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.setMinimumWidth(340)
        self.selected_code = current
        self._build_ui(current)

    def _build_ui(self, current: str = "de"):
        lay = QVBoxLayout(self)
        lay.setSpacing(12)

        c = ui_colors(self)
        lbl = QLabel(
            "<h3 style='margin:0'>Welcome / Willkommen / Bienvenue</h3>"
            f"<p style='color:{c.text_dim}'>Please select your language:<br>"
            "Bitte wähle deine Sprache:<br>"
            "Veuillez choisir votre langue :</p>"
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
        btn_ok = QPushButton("✓  OK")
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
