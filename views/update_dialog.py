"""Update-Dialog (Portable).

Ziele
- Update-Check & Download aus der GUI (manuell)
- Installieren über denselben Entry-Point wie die App (funktioniert auch im PyInstaller-Fall)

Technik
- `main.py --check-update` lädt + staged das Update
- `main.py --apply-update` wendet es an (App muss geschlossen werden)
"""

from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QProcess, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QLabel,
    QMessageBox,
    QCheckBox,
)

from app_info import app_version_label
from updater.common import updates_dir


def _entrypoint_cmd() -> list[str]:
    """Baut einen Aufruf, der in DEV und im PyInstaller-Fall funktioniert."""
    if getattr(sys, "frozen", False):
        # PyInstaller: sys.executable ist die .exe
        return [sys.executable]
    # DEV: python + main.py
    root = Path(__file__).resolve().parents[1]
    return [sys.executable, str(root / "main.py")]


class UpdateDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("⬆️ Updates")
        self.setMinimumSize(760, 460)

        self._proc: QProcess | None = None
        self._has_staged_update = False

        self.lbl_info = QLabel(
            f"Aktuell installiert: <b>{app_version_label()}</b><br>"
            "Updates werden nur bei Klick geprüft."
        )
        self.lbl_info.setTextFormat(Qt.RichText)

        self.log = QTextEdit()
        self.log.setReadOnly(True)

        self.chk_autoclose = QCheckBox("Nach erfolgreichem Download schließen")
        self.chk_autoclose.setChecked(False)

        # Buttons
        self.btn_check = QPushButton("🔎 Prüfen & herunterladen")
        self.btn_check.clicked.connect(self._check)

        self.btn_apply = QPushButton("⚠️ Installieren (App schließt)")
        self.btn_apply.clicked.connect(self._apply)
        self.btn_apply.setEnabled(False)

        self.btn_open_updates = QPushButton("📁 Updates-Ordner öffnen")
        self.btn_open_updates.clicked.connect(self._open_updates_folder)

        self.btn_close = QPushButton("Schließen")
        self.btn_close.clicked.connect(self.reject)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.lbl_info)
        layout.addWidget(self.chk_autoclose)
        layout.addWidget(self.log)

        row = QHBoxLayout()
        row.addWidget(self.btn_check)
        row.addWidget(self.btn_apply)
        row.addStretch(1)
        row.addWidget(self.btn_open_updates)
        row.addWidget(self.btn_close)
        layout.addLayout(row)
        self.setLayout(layout)

        # Initialer Hinweis
        self._append("Hinweis: 'Prüfen & herunterladen' lädt ein Update und legt es in 'updates/staging/' ab.")
        self._append("Zum Installieren muss die App geschlossen werden.")
        self._refresh_state_from_disk()

    # --- UI helpers ---
    def _append(self, text: str) -> None:
        self.log.append(text)

    def _set_busy(self, busy: bool) -> None:
        self.btn_check.setEnabled(not busy)
        self.btn_open_updates.setEnabled(not busy)
        # Install ist nur möglich, wenn staged
        self.btn_apply.setEnabled((not busy) and self._has_staged_update)

    def _refresh_state_from_disk(self) -> None:
        # Wenn staging existiert (irgendein Unterordner), aktivieren wir Install.
        staging_root = Path(updates_dir()) / "staging"
        self._has_staged_update = staging_root.exists() and any(p.is_dir() for p in staging_root.iterdir())
        self.btn_apply.setEnabled(self._has_staged_update)

    def _open_updates_folder(self) -> None:
        p = Path(updates_dir())
        p.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(p.as_uri())

    # --- Process handling ---
    def _start_process(self, args: list[str]) -> None:
        if self._proc is not None:
            try:
                self._proc.kill()
            except Exception:
                pass
            self._proc = None

        self._proc = QProcess(self)
        self._proc.setProcessChannelMode(QProcess.MergedChannels)
        self._proc.readyReadStandardOutput.connect(self._on_proc_output)
        self._proc.finished.connect(self._on_proc_finished)

        cmd = _entrypoint_cmd() + args
        self._append(f"$ {' '.join(cmd)}")

        # Windows: verhindert extra Konsole beim Start, wenn möglich
        env = self._proc.processEnvironment()
        # env bleibt default; nur placeholder (falls später nötig)
        self._proc.setProcessEnvironment(env)

        self._set_busy(True)
        self._proc.start(cmd[0], cmd[1:])

    def _on_proc_output(self) -> None:
        if not self._proc:
            return
        data = bytes(self._proc.readAllStandardOutput()).decode(errors="replace")
        if not data:
            return
        # einfache Darstellung
        for line in data.splitlines():
            self._append(line)

        # grobe Heuristik: staged update -> Install button aktivieren
        if "Staged:" in data or "Bereits staged" in data or "Update verfügbar" in data:
            # nach dem Lauf prüfen wir auf Disk
            pass

    def _on_proc_finished(self, exit_code: int, _status) -> None:
        self._append(f"\nProzess beendet (Code {exit_code}).")
        self._refresh_state_from_disk()
        self._set_busy(False)

        if exit_code == 0 and self.chk_autoclose.isChecked():
            self.accept()

    # --- Actions ---
    def _check(self) -> None:
        self._append("\n=== Update prüfen ===")
        self._start_process(["--check-update"])

    def _apply(self) -> None:
        self._refresh_state_from_disk()
        if not self._has_staged_update:
            QMessageBox.information(
                self,
                "Kein Update bereit",
                "Es ist kein 'staged' Update vorhanden. Bitte zuerst 'Prüfen & herunterladen' ausführen.",
            )
            return

        if QMessageBox.question(
            self,
            "Update installieren",
            "Zum Installieren muss die App geschlossen werden.\n\nFortfahren?",
        ) != QMessageBox.Yes:
            return

        # Updater in eigenem Prozess starten
        cmd = _entrypoint_cmd() + ["--apply-update"]
        self._append(f"\n$ {' '.join(cmd)}")

        try:
            if getattr(sys, "frozen", False):
                # PyInstaller: exe neu starten
                QProcess.startDetached(cmd[0], cmd[1:])
            else:
                QProcess.startDetached(cmd[0], cmd[1:])
        except Exception as e:
            QMessageBox.critical(self, "Fehler", f"Updater konnte nicht gestartet werden:\n{e}")
            return

        # App schließen
        if self.parent() is not None:
            try:
                self.parent().close()
            except Exception:
                pass
        self.accept()
