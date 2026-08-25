"""Einmalige Warnung, wenn der Datenordner in OneDrive liegt.

Bis v3.0.6 schlug der Windows-Installer den Dokumente-Ordner als Datenordner
vor. Mit aktivierter OneDrive-Ordnersicherung - Standard bei jedem
Microsoft-Konto - liegt der in OneDrive. Dort teilt sich die SQLite-Datenbank
den Ordner mit einem Synchronisierer, der Sperren haelt, die drei
zusammengehoerenden Dateien (.db, -wal, -shm) unabhaengig voneinander
hochlaedt, bei Konflikt Kopien anlegt und per Files-On-Demand dehydrieren kann.
Der geaenderte Installer-Default hilft nur Neuinstallationen; die bereits
ausgelieferten erfahren es ausschliesslich hier.

Ausgelagert aus ``views/main_window.py`` nach dem Muster von
``views/main_window_diagnostics.py``: freie Funktionen mit ``self`` als erstem
Argument, damit das Hauptfenster unter der 3500-Zeilen-Grenze des
Architektur-Gates bleibt.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from utils.i18n import tr, trf

logger = logging.getLogger(__name__)

# Fehler, die beim Aufbau des Hinweises realistisch auftreten koennen: ein
# unlesbarer/nicht anlegbarer Datenordner (OSError), ein bereits zerstoertes
# Qt-Objekt (RuntimeError) und ein unerwarteter Settings-Wert (ValueError,
# TypeError). Bewusst kein 'except Exception': der Ausnahmen-Ratchet in
# tools/exception_audit.py deckelt breite Handler, und ein echter
# Programmfehler soll hier sichtbar bleiben.
_ERWARTETE_FEHLER = (OSError, RuntimeError, ValueError, TypeError)


def schedule_warning(self, *, delay_ms: int = 2500) -> None:
    """Plant den Hinweis, falls der aktive Datenordner in OneDrive liegt.

    Der Hinweis erscheint genau einmal je Datenordner: Das Merkflag steht in
    der Settings-Datei, und die liegt im Datenordner selbst. Wer nach einem
    Wechsel erneut in OneDrive landet, wird dort wieder gewarnt.
    """
    if self.settings.get("onedrive_warning_shown", False):
        return

    from model.app_paths import data_dir_onedrive_root

    root = data_dir_onedrive_root()
    if not root:
        return

    timer = QTimer(self)
    timer.setSingleShot(True)

    def _show(root: str = root) -> None:
        try:
            if getattr(self, "_is_closing", False):
                return
            show_warning_dialog(self, root)
        except RuntimeError:
            logger.debug(
                "OneDrive-Hinweis uebersprungen: MainWindow wurde bereits zerstoert."
            )
        except _ERWARTETE_FEHLER:
            logger.exception("OneDrive-Hinweis konnte nicht angezeigt werden")
        finally:
            try:
                timer.deleteLater()
            except RuntimeError:
                logger.debug("OneDrive-Timer war bereits zerstoert.")

    timer.timeout.connect(_show)
    timer.start(max(0, int(delay_ms)))


def show_warning_dialog(self, onedrive_root: str) -> None:
    """Zeigt die Warnung und bietet den Wechsel ueber die Datenuebernahme an."""
    from model.app_paths import data_dir, recommended_local_data_dir

    aktuell = data_dir()
    ziel = recommended_local_data_dir()

    # Vor dem Dialog merken, nicht danach: Bricht der Nutzer den Wechsel ab
    # oder scheitert die Uebernahme, soll der Hinweis trotzdem nicht bei jedem
    # Start wiederkommen.
    self.settings.set("onedrive_warning_shown", True)

    box = QMessageBox(self)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle(tr("onedrive.title"))
    box.setText(tr("onedrive.text"))
    box.setInformativeText(
        trf(
            "onedrive.info",
            folder=str(aktuell),
            onedrive=str(onedrive_root),
            target=str(ziel) if ziel else "",
        )
    )
    move_button = box.addButton(tr("onedrive.move_now"), QMessageBox.AcceptRole)
    box.addButton(tr("onedrive.keep"), QMessageBox.RejectRole)
    box.exec()

    if box.clickedButton() is move_button and ziel is not None:
        # Derselbe Weg wie im Einstellungsdialog: fragt nach der Uebernahme,
        # legt vorher ein Sicherheits-Backup an, kopiert statt zu verschieben
        # und weist auf den noetigen Neustart hin.
        self._handle_data_directory_change(str(ziel))
