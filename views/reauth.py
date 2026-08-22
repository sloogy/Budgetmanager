"""Gemeinsame Re-Authentifizierung fuer sicherheitsrelevante Dialog-Aktionen.

v2.2.16 (K4): Die Code-Abfrage aus v2.2.10 lebte nur im BackupRestoreDialog.
Der Datenbank-Reset war aber auch ueber den DatabaseManagementDialog erreichbar
und lief an der Abfrage vorbei. Statt die Logik zu kopieren, nutzen jetzt beide
Dialoge diese eine Funktion (Policy bleibt Qt-frei in ``model/backup_auth``).
"""

from __future__ import annotations

import logging

from PySide6.QtWidgets import QInputDialog, QLineEdit, QMessageBox

from utils.i18n import tr, trf
from utils.notifications import show_warning

logger = logging.getLogger(__name__)


def require_reauth(parent, active_user, action: str) -> bool:
    """Fragt den Benutzercode ab (nur PIN/Passwort; Quick laeuft durch).

    Drei Fehlversuche brechen ab. Gibt True zurueck, wenn die Aktion
    freigegeben ist. Session-Caching (einmal pro Dialog) ist Sache des
    Aufrufers, damit die Lebensdauer der Freigabe am Dialog haengt.
    """
    from model.backup_auth import requires_code, verify_secret

    if not requires_code(active_user):
        return True

    try:
        from model.user_model import UserModel

        user_model = UserModel()
    except Exception as e:
        logger.exception("UserModel fuer Re-Authentifizierung nicht ladbar")
        QMessageBox.critical(parent, tr("msg.error"), str(e))
        return False

    level = getattr(active_user, "security_label", "") or ""
    for _attempt in range(3):
        secret, ok = QInputDialog.getText(
            parent,
            tr("backup.auth_title"),
            trf("backup.auth_text", level=level),
            QLineEdit.Password,
        )
        if not ok:
            return False
        if verify_secret(user_model, active_user, (secret or "").strip()):
            logger.info("Sicherheitsrelevante Aktion '%s' freigegeben", action)
            return True
        show_warning(parent, tr("msg.error"), tr("backup.auth_failed"))

    show_warning(parent, tr("msg.info"), tr("backup.auth_aborted"))
    logger.warning("Aktion '%s' ohne gueltigen Code abgebrochen", action)
    return False
