from __future__ import annotations

import logging
logger = logging.getLogger(__name__)
import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QDialogButtonBox,
    QPushButton,
)

from views.tabs.budget_tab import BudgetTab
from utils.i18n import tr, trf, display_typ, db_typ_from_display


class BudgetFillDialog(QDialog):
    """Eigenes Fenster zum Ausfüllen des Budgets.

    Warum ein eigenes Fenster?
    - Im Onboarding soll der Budget-Tab „voll im Fokus“ sein.
    - Der User kann direkt Beträge eintragen und speichern.

    Hinweis: Es wird eine *neue* BudgetTab-Instanz mit derselben DB-Verbindung genutzt.
    """

    def __init__(self, parent, conn: sqlite3.Connection, *, title: str | None = None):
        super().__init__(parent)
        self.setWindowTitle(title or tr("dlg.budget_ausfuellen"))
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowMaximizeButtonHint)

        root = QVBoxLayout(self)

        hint = QLabel(
            "<b>Budget ausfüllen</b><br>"
            "Trage deine Monatswerte direkt in die Tabelle ein (Doppelklick/F2). "
            "Nutze <b>🌳 Baum</b> für Ein-/Ausklappen oder Pfad-Anzeige." \
            "<br><small>Tipp: Speichere danach mit <b>Strg+S</b> oder unten mit \"Speichern &amp; Schließen\".</small>"
        )
        hint.setTextFormat(Qt.RichText)
        hint.setWordWrap(True)
        root.addWidget(hint)

        self.budget_tab = BudgetTab(conn)
        # Im Setup standardmäßig aktuelles Jahr setzen
        try:
            if hasattr(self.budget_tab, "year_spin"):
                self.budget_tab.year_spin.setValue(date.today().year)
            if hasattr(self.budget_tab, "load"):
                self.budget_tab.load()
        except Exception as e:
            logger.debug("if hasattr(self.budget_tab, 'year_spin'):: %s", e)
        root.addWidget(self.budget_tab, 1)

        buttons = QDialogButtonBox()
        self.btn_save_close = QPushButton(tr("btn.speichern_schliessen"))
        self.btn_close = QPushButton(tr("btn.close"))
        buttons.addButton(self.btn_save_close, QDialogButtonBox.AcceptRole)
        buttons.addButton(self.btn_close, QDialogButtonBox.RejectRole)
        root.addWidget(buttons)

        self.btn_save_close.clicked.connect(self._save_and_close)
        self.btn_close.clicked.connect(self.reject)

        # Startgröße (User kann maximieren)
        self.resize(1280, 820)

    def _save_and_close(self) -> None:
        try:
            if hasattr(self.budget_tab, "save"):
                self.budget_tab.save()
        finally:
            self.accept()
