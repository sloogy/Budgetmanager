from __future__ import annotations

import logging
import sqlite3
from datetime import date

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
)

from utils.i18n import tr
from views.tabs.budget_tab import BudgetTab

logger = logging.getLogger(__name__)


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
            tr(
                "auto.views_budget_fill_dialog.40_b_budget_ausfuellen_b_br_trage_dein_680d66fc"
            )
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
        # Der Budget-Tab besitzt bewusst viele Direktaktionen. Auf kleineren
        # Displays darf deren natürliche Breite den Dialog nicht auf >1500 px
        # zwingen; stattdessen bleibt alles über eine horizontale Scrollleiste
        # erreichbar.
        self.budget_scroll = QScrollArea()
        self.budget_scroll.setWidgetResizable(True)
        self.budget_scroll.setFocusPolicy(Qt.NoFocus)
        self.budget_scroll.setFrameShape(QFrame.NoFrame)
        self.budget_scroll.setWidget(self.budget_tab)
        root.addWidget(self.budget_scroll, 1)

        buttons = QDialogButtonBox()
        self.btn_save_close = QPushButton(tr("btn.speichern_schliessen"))
        self.btn_close = QPushButton(tr("btn.close"))
        buttons.addButton(self.btn_save_close, QDialogButtonBox.AcceptRole)
        buttons.addButton(self.btn_close, QDialogButtonBox.RejectRole)
        root.addWidget(buttons)

        self.btn_save_close.clicked.connect(self._save_and_close)
        self.btn_close.clicked.connect(self.reject)

        # Startgröße (User kann maximieren); dank ScrollArea auch auf kleinen
        # Notebook-Displays vollständig bedienbar.
        self.setMinimumSize(760, 560)
        self.resize(1280, 820)
        from utils.responsive_dialog import harden_dialog_for_screen

        harden_dialog_for_screen(self)

    def _save_and_close(self) -> None:
        try:
            if hasattr(self.budget_tab, "save"):
                self.budget_tab.save()
        finally:
            self.accept()
