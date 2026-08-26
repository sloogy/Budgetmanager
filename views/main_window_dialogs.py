from __future__ import annotations

import os
from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QPlainTextEdit,
    QVBoxLayout,
)

from app_info import APP_NAME, APP_VERSION, app_version_label
from utils.branding import make_logo_label
from utils.i18n import tr, trf
from utils.notifications import show_warning
from views.update_dialog import UpdateDialog


class AboutDialog(QDialog):
    """Über-Dialog"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(
            trf("about.title", app_name=APP_NAME, version=app_version_label())
        )

        layout = QVBoxLayout()

        # Marken-Flaeche: das Logo traegt den Programmnamen bereits als Bild,
        # der Versionstext darunter bleibt unveraendert.
        logo = make_logo_label(self, 380)
        if logo is not None:
            layout.addWidget(logo)

        html = trf(
            "about.html",
            app_name=APP_NAME,
            version=app_version_label(),
            app_version=APP_VERSION,
        )

        info = QLabel(html)
        info.setTextFormat(Qt.RichText)
        info.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok)
        buttons.accepted.connect(self.accept)

        # Update-Button direkt im Info/Über-Dialog
        btn_updates = buttons.addButton(tr("update.title"), QDialogButtonBox.ActionRole)
        btn_updates.clicked.connect(self._open_updates)

        layout.addWidget(info)
        layout.addWidget(buttons)
        self.setLayout(layout)
        self.setMinimumWidth(450)

    def _open_updates(self):
        """Öffnet den Update-Dialog (portable/EXE kompatibel)."""
        try:
            if os.environ.get("LIFEPLANNER_CENTRAL_UPDATER", "").strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }:
                show_warning(
                    self,
                    tr("update.title"),
                    tr("lifeplanner_import.central_updater"),
                )
                return
            dlg = UpdateDialog(self.parent() or self)
            dlg.exec()
        except Exception as e:
            show_warning(
                self,
                tr("auto.views_main_window.100_update_81ab2a4e"),
                trf("lbl.updatedialog_konnte_nicht_geoeffnet", e=str(e)),
            )


class LogViewerDialog(QDialog):
    """Einfacher, robuster Log-Anzeiger für normale Nutzer."""

    def __init__(self, parent, *, title: str, path: Path, text: str):
        super().__init__(parent)
        self._path = Path(path)
        self.setWindowTitle(title)

        layout = QVBoxLayout(self)

        path_label = QLabel(str(self._path))
        path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        path_label.setWordWrap(True)
        layout.addWidget(path_label)

        viewer = QPlainTextEdit(self)
        viewer.setReadOnly(True)
        viewer.setPlainText(
            text or trf("diagnostics.file_not_found", path=str(self._path))
        )
        viewer.setLineWrapMode(QPlainTextEdit.NoWrap)
        layout.addWidget(viewer, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        btn_open_folder = buttons.addButton(
            tr("diagnostics.open_folder"), QDialogButtonBox.ActionRole
        )
        btn_refresh = buttons.addButton(
            tr("diagnostics.refresh"), QDialogButtonBox.ActionRole
        )

        def _open_folder() -> None:
            try:
                QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._path.parent)))
            except Exception as exc:
                show_warning(self, tr("msg.error"), str(exc))

        def _refresh() -> None:
            try:
                from model.diagnostics import read_text_tail

                viewer.setPlainText(read_text_tail(self._path))
            except Exception as exc:
                viewer.setPlainText(str(exc))

        btn_open_folder.clicked.connect(_open_folder)
        btn_refresh.clicked.connect(_refresh)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.resize(900, 600)
