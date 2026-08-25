"""Diagnose-Workflow des Hauptfensters (Logs, Diagnoseordner, Diagnose-ZIP).

Ausgelagert aus ``views/main_window.py``, damit das Hauptfenster Navigation und
Fenster-Lebenszyklus koordiniert und nicht erneut zu einem GUI-Monolithen
waechst (Architektur-Gate: 3500 Zeilen). Das Muster entspricht
``views/main_window_settings.py``: freie Funktionen, die ``self`` als erstes
Argument entgegennehmen, damit die Methoden des Hauptfensters reine
Weiterleitungen bleiben.
"""

from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QMessageBox

from utils.i18n import tr, trf
from utils.notifications import show_warning
from views.main_window_dialogs import LogViewerDialog

logger = logging.getLogger(__name__)


def show_log_file(self, *, path: Path, title_key: str) -> None:
    """Oeffnet eine Logdatei in einem eigenen Dialog statt im Systemeditor."""
    try:
        from model.diagnostics import read_text_tail

        text = read_text_tail(path)
        dlg = LogViewerDialog(self, title=tr(title_key), path=path, text=text)
        dlg.exec()
    except Exception as exc:
        show_warning(
            self,
            tr("msg.error"),
            trf("diagnostics.log_open_failed", error=str(exc)),
        )


def show_app_log(self) -> None:
    """Zeigt das laufende Anwendungsprotokoll."""
    from model.diagnostics import log_file_path

    show_log_file(self, path=log_file_path(), title_key="diagnostics.app_log_title")


def show_crash_log(self) -> None:
    """Zeigt das Absturzprotokoll des letzten unsauberen Endes."""
    from model.diagnostics import crash_log_file_path

    show_log_file(
        self, path=crash_log_file_path(), title_key="diagnostics.crash_log_title"
    )


def open_diagnostics_folder(self) -> None:
    """Oeffnet den Diagnoseordner im Dateimanager."""
    try:
        from model.diagnostics import diagnostics_dir

        folder = diagnostics_dir()
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        if self.statusBar():
            self.statusBar().showMessage(
                trf("diagnostics.folder_opened", folder=str(folder)), 3000
            )
    except Exception as exc:
        show_warning(
            self,
            tr("msg.error"),
            trf("diagnostics.folder_open_failed", error=str(exc)),
        )


def create_diagnostic_report(self) -> None:
    """Erstellt lokal ein Diagnose-ZIP ohne Datenbank/Backups."""
    try:
        from model.diagnostics import (
            create_diagnostic_report_zip,
            remove_old_diagnostic_reports,
        )

        path = create_diagnostic_report_zip(connection=self.conn)
        remove_old_diagnostic_reports()
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Information)
        box.setWindowTitle(tr("diagnostics.report_created_title"))
        box.setText(trf("diagnostics.report_created_text", path=str(path)))
        open_folder_button = box.addButton(
            tr("diagnostics.open_folder"), QMessageBox.ActionRole
        )
        box.addButton(QMessageBox.Ok)
        box.exec()
        if box.clickedButton() is open_folder_button:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
    except Exception as exc:
        show_warning(
            self,
            tr("msg.error"),
            trf("diagnostics.report_create_failed", error=str(exc)),
        )
