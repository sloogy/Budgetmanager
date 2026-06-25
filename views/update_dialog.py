"""Geführter Update-Dialog (Portable / EXE-kompatibel).

Ablauf für den Nutzer:
1. Dialog öffnen → Prüfung startet automatisch.
2. Bei vorhandener neuer Version: Update wird heruntergeladen und vorbereitet.
3. Ein Klick auf „Jetzt aktualisieren & neu starten“ schließt die App.
4. Windows: sichtbares externes Update-Fenster ersetzt die Dateien und startet neu.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

from PySide6.QtCore import QProcess, Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
)

from app_info import APP_VERSION, app_version_label
from updater.common import clear_check_result, read_check_result
from utils.i18n import tr, trf

GITHUB_RELEASES_URL = "https://github.com/sloogy/Budgetmanager/releases/latest"


def _entrypoint_cmd(module: str | None = None) -> list[str]:
    """Baut einen Aufruf, der in DEV und im PyInstaller-Fall funktioniert.

    DEV/Source: bewusst NICHT wieder ``main.py`` starten. Sonst erscheint im
    Prozessmonitor ein weiterer ``python main.py`` und in budgetmanager.log ein
    zweiter scheinbarer App-Start, obwohl nur der Updater-Check läuft. Das war
    nach der Cockpit-Integration besonders verwirrend und wirkte wie eine
    weitere Instanz.

    PyInstaller/frozen: Die EXE ist der einzige Einstiegspunkt; dort bleiben die
    bestehenden CLI-Flags erhalten.
    """
    if getattr(sys, "frozen", False):
        if module == "updater.check_update":
            return [sys.executable, "--check-update"]
        if module == "updater.apply_update":
            return [sys.executable, "--apply-update"]
        return [sys.executable]
    mod = module or "updater.check_update"
    return [sys.executable, "-m", mod]


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(tr("update.title"))
        self.setMinimumSize(620, 430)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)

        self._proc: QProcess | None = None
        self._available = False
        self._busy = False

        root = QVBoxLayout(self)
        root.setSpacing(10)

        self.lbl_info = QLabel(trf("update.current_version", version=app_version_label()))
        self.lbl_info.setTextFormat(Qt.RichText)
        self.lbl_info.setWordWrap(True)
        root.addWidget(self.lbl_info)

        self.lbl_status = QLabel(tr("update.status_checking"))
        self.lbl_status.setWordWrap(True)
        self.lbl_status.setStyleSheet("font-weight: 600;")
        root.addWidget(self.lbl_status)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setVisible(False)
        root.addWidget(self.progress)

        self.btn_details = QPushButton(tr("update.show_details"))
        self.btn_details.setCheckable(True)
        self.btn_details.setFlat(True)
        self.btn_details.toggled.connect(self._toggle_details)
        root.addWidget(self.btn_details, 0, Qt.AlignLeft)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        self.log.setVisible(False)
        self.log.setMaximumHeight(180)
        root.addWidget(self.log)

        line = QFrame()
        line.setFrameShape(QFrame.HLine)
        root.addWidget(line)

        btn_row = QHBoxLayout()
        self.btn_recheck = QPushButton(tr("update.btn_check"))
        self.btn_recheck.clicked.connect(self._check)
        btn_row.addWidget(self.btn_recheck)

        self.btn_github = QPushButton(tr("update.btn_releases"))
        self.btn_github.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(GITHUB_RELEASES_URL)))
        btn_row.addWidget(self.btn_github)

        btn_row.addStretch(1)

        self.btn_update = QPushButton(tr("update.btn_update_now"))
        self.btn_update.setDefault(True)
        self.btn_update.setEnabled(False)
        self.btn_update.clicked.connect(self._apply)
        btn_row.addWidget(self.btn_update)

        self.btn_close = QPushButton(tr("btn.close"))
        self.btn_close.clicked.connect(self.reject)
        btn_row.addWidget(self.btn_close)

        root.addLayout(btn_row)
        self._append(tr("update.hint_windows"))

        QTimer.singleShot(0, self._check)

    def _append(self, text: str) -> None:
        for line in str(text).splitlines():
            self.log.append(line)

    def _toggle_details(self, on: bool) -> None:
        self.log.setVisible(on)
        self.btn_details.setText(tr("update.hide_details") if on else tr("update.show_details"))

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.progress.setVisible(busy)
        self.btn_recheck.setEnabled(not busy)
        self.btn_update.setEnabled((not busy) and self._available)
        self.btn_close.setEnabled(not busy)

    def _check(self) -> None:
        if self._busy:
            return
        clear_check_result()
        self._available = False
        self.btn_update.setEnabled(False)
        self.lbl_status.setText(tr("update.status_checking"))
        self._append("$ " + " ".join(_entrypoint_cmd("updater.check_update") + ["--gui"]))
        self._set_busy(True)

        self._proc = QProcess(self)
        if not getattr(sys, "frozen", False):
            self._proc.setWorkingDirectory(str(Path(__file__).resolve().parents[1]))
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_output)
        self._proc.finished.connect(self._on_check_finished)
        cmd = _entrypoint_cmd("updater.check_update") + ["--gui"]
        self._proc.start(cmd[0], cmd[1:])

    def _on_output(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        if data:
            self._append(data)

    def _on_check_finished(self, exit_code: int, _status) -> None:
        self._proc = None
        self._set_busy(False)
        res = read_check_result()
        remote = res.get("remote") or ""
        if res.get("available") and res.get("staged"):
            self._available = True
            self.lbl_status.setText(trf("update.status_available", version=remote))
            self.btn_update.setEnabled(True)
            self.btn_update.setFocus()
        elif res.get("error"):
            self._available = False
            self.lbl_status.setText(trf("update.status_error", error=res.get("error")))
        elif res:
            self._available = False
            self.lbl_status.setText(trf("update.status_uptodate", version=res.get("current") or APP_VERSION))
        else:
            self._available = False
            self.lbl_status.setText(trf("update.status_check_failed", code=exit_code))

    def _apply(self) -> None:
        if not self._available:
            return
        if QMessageBox.question(
            self,
            tr("update.confirm_apply_title"),
            tr("update.confirm_apply_text"),
        ) != QMessageBox.Yes:
            return

        cmd = _entrypoint_cmd("updater.apply_update")
        self._append("$ " + " ".join(cmd))
        self._append(tr("update.status_applying"))
        try:
            if getattr(sys, "frozen", False):
                started = QProcess.startDetached(cmd[0], cmd[1:])
            else:
                started = QProcess.startDetached(cmd[0], cmd[1:], str(Path(__file__).resolve().parents[1]))
            if not started:
                raise RuntimeError("QProcess.startDetached lieferte False")
        except Exception as e:
            QMessageBox.critical(self, tr("msg.error"), trf("update.apply_start_failed", error=str(e)))
            return

        # WICHTIG: last_check.json hier NICHT loeschen. Der soeben abgekoppelt
        # gestartete apply_update-Prozess liest die Datei ueber
        # target_staged_version(), um genau die gepruefte Version anzuwenden.
        # Ein Loeschen an dieser Stelle ist ein Race: der EXE-Bootstrap des
        # Apply-Prozesses ist langsamer als dieser Aufruf, sodass die Datei vor
        # dem Lesen verschwindet und apply auf latest_staged_version() (evtl. ein
        # veralteter, hoeher nummerierter Staging-Ordner) zurueckfaellt.
        # Der naechste _check() setzt den Zustand ohnehin zurueck.
        self.lbl_status.setText(tr("update.status_applying"))

        if self.parent() is not None:
            try:
                self.parent().close()
            except Exception as e:
                logger.debug("parent().close(): %s", e)
        self.accept()
        app = QApplication.instance()
        if app is not None:
            QTimer.singleShot(0, app.quit)
