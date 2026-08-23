"""Der Update-Weg des Hauptfensters.

Herausgeloest, weil ``views/main_window.py`` an die Zeilengrenze des
Architektur-Gates stiess. Der Start-Update-Check und der manuelle
Update-Dialog sind ein geschlossenes Thema: Beide entscheiden anhand von
``LIFEPLANNER_CENTRAL_UPDATER``, ob der Host die Updates fuehrt, und beide
gehoeren zu ``updater/``, nicht zum Fensteraufbau.

Als Mixin, damit die Methoden weiterhin auf ``MainWindow`` liegen - der
Aufrufer merkt vom Umzug nichts.
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

from PySide6.QtCore import QProcess, QTimer
from PySide6.QtWidgets import QMessageBox

from app_info import APP_VERSION
from updater.common import clear_startup_check_result, read_startup_check_result
from utils.defensive_log import uebersprungen as _uebersprungen
from utils.i18n import tr, trf
from utils.notifications import show_info
from views.update_dialog import UpdateDialog

logger = logging.getLogger(__name__)


class MainWindowUpdateMixin:
    """Start-Update-Check und Update-Dialog des Hauptfensters."""

    def _startup_update_cmd(self) -> list[str]:
        """Baut den leichten Start-Update-Check fuer DEV und PyInstaller."""
        if getattr(sys, "frozen", False):
            return [sys.executable, "--startup-update-check"]
        return [sys.executable, "-m", "updater.startup_check"]

    def schedule_startup_update_check(self, delay_ms: int = 4000) -> None:
        """Prueft nach dem Start unaufdringlich auf Updates.

        Die Pruefung laedt nur das Manifest. Download/Staging/Installation
        passieren erst nach Klick im normalen Update-Dialog.
        """
        if os.environ.get("LIFEPLANNER_CENTRAL_UPDATER", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            return
        if not bool(self.settings.get("check_updates_on_start", True)):
            return
        timer = QTimer(self)
        timer.setSingleShot(True)

        def _run() -> None:
            try:
                self._start_startup_update_check()
            finally:
                try:
                    timer.deleteLater()
                except Exception as fehler:
                    _uebersprungen("schedule_startup_update_check", fehler)

        timer.timeout.connect(_run)
        self._startup_update_timer = timer
        timer.start(max(0, int(delay_ms)))

    def _start_startup_update_check(self) -> None:
        if self._startup_update_proc is not None:
            return
        if getattr(self, "_is_closing", False):
            return
        try:
            clear_startup_check_result()
        except Exception as fehler:
            _uebersprungen("_start_startup_update_check", fehler)

        cmd = self._startup_update_cmd()
        proc = QProcess(self)
        self._startup_update_proc = proc
        if not getattr(sys, "frozen", False):
            proc.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        proc.setProcessChannelMode(QProcess.MergedChannels)
        proc.readyReadStandardOutput.connect(self._on_startup_update_output)
        proc.finished.connect(self._on_startup_update_finished)
        proc.start(cmd[0], cmd[1:])

    def _on_startup_update_output(self) -> None:
        proc = self._startup_update_proc
        if proc is None:
            return
        data = bytes(proc.readAllStandardOutput()).decode(errors="replace").strip()
        if data:
            logger.debug("Startup-Update-Check: %s", data)

    def _on_startup_update_finished(self, _exit_code: int, _status) -> None:
        self._startup_update_proc = None
        if getattr(self, "_is_closing", False):
            return
        res = read_startup_check_result()
        if not res.get("available"):
            if res.get("error"):
                logger.debug(
                    "Startup-Update-Check ohne Hinweis beendet: %s", res.get("error")
                )
            return
        if self._startup_update_prompt_shown:
            return
        self._startup_update_prompt_shown = True

        remote = str(res.get("remote") or "")
        current = str(res.get("current") or APP_VERSION)
        self.statusBar().showMessage(
            trf("update.startup_status_available", version=remote), 10000
        )

        msg = QMessageBox(self)
        msg.setIcon(QMessageBox.Information)
        msg.setWindowTitle(tr("update.startup_available_title"))
        msg.setText(
            trf("update.startup_available_text", current=current, remote=remote)
        )
        msg.setInformativeText(tr("update.startup_available_info"))
        btn_update = msg.addButton(
            tr("update.startup_btn_open"), QMessageBox.AcceptRole
        )
        msg.addButton(tr("update.startup_btn_later"), QMessageBox.RejectRole)
        msg.exec()
        if msg.clickedButton() is btn_update:
            self._show_update_dialog()

    def _show_update_dialog(self):
        """Öffnet standalone den Modul-Updater, im Host den zentralen Updater."""
        if os.environ.get("LIFEPLANNER_CENTRAL_UPDATER", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            show_info(
                self,
                tr("update.title"),
                tr("lifeplanner_import.central_updater"),
            )
            return
        dialog = UpdateDialog(self)
        dialog.exec()
