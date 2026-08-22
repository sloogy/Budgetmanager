"""Wiederaufrufbarer Dialog zum Anzeigen des Datenbank-/Restore-Keys.

Im Gegensatz zum Erststart-Dialog (der den Key „nur einmal“ mit
Bestätigungs-Häkchen zeigt) ist dieser hier jederzeit über die Hilfe
erreichbar: ansehen + kopieren. Der Key gehört zur aktuell geöffneten
Datenbank.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from utils.i18n import tr

logger = logging.getLogger(__name__)


class RestoreKeyDialog(QDialog):
    """Zeigt den Restore-Key (lesbar, gruppiert) mit Kopier-Funktion."""

    def __init__(self, parent=None, *, restore_key: str):
        super().__init__(parent)
        self._key = restore_key or ""
        self.setWindowTitle(tr("restore_key.view_title"))
        self.setMinimumSize(480, 320)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        root = QVBoxLayout(self)

        intro = QLabel(tr("restore_key.view_intro"))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.RichText)
        root.addWidget(intro)

        self.key_box = QTextEdit()
        self.key_box.setReadOnly(True)
        self.key_box.setPlainText(
            self._key if self._key else tr("account.restorekey_nicht_verfuegbar")
        )
        self.key_box.setStyleSheet(
            "font-family: 'Consolas', 'Courier New', monospace; "
            "font-size: 14px; padding: 10px; letter-spacing: 1px;"
        )
        self.key_box.setMaximumHeight(90)
        root.addWidget(self.key_box)

        note = QLabel(tr("restore_key.view_note"))
        note.setWordWrap(True)
        root.addWidget(note)

        btn_row = QHBoxLayout()
        self.btn_copy = QPushButton(tr("btn.copy"))
        self.btn_copy.setEnabled(bool(self._key))
        self.btn_copy.clicked.connect(self._copy)
        btn_row.addWidget(self.btn_copy)
        self.lbl_copied = QLabel("")
        btn_row.addWidget(self.lbl_copied)
        btn_row.addStretch(1)
        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self.accept)
        btn_row.addWidget(self.btn_close)
        root.addLayout(btn_row)

    def _copy(self) -> None:
        if not self._key:
            return
        try:
            cb = QApplication.clipboard()
            if cb is not None:
                cb.setText(self._key)
                self.lbl_copied.setText(tr("restore_key.copied"))
        except Exception:
            logger.exception(
                "Restore-Key konnte nicht in die Zwischenablage kopiert werden"
            )
