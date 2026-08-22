"""Re-Authentifizierung für sicherheitsrelevante Backup-Aktionen.

Hintergrund (v2.2.10)
---------------------
Export, Import und Wiederherstellen von Backups sind sicherheitsrelevant:

* **Export** schreibt die (u.U. verschlüsselte) Datenbank – und optional
  ``users.json`` – an einen frei wählbaren Ort ausserhalb des Programms.
* **Import/Restore** *überschreibt* die aktive Datenbank.

Bisher liefen diese Aktionen ohne jede Code-Abfrage. Wer kurz an einem
entsperrten Fenster sass, konnte die Daten ausleiten oder ersetzen.

Absichtliche Ausnahme: **Quick-Konten** (ohne PIN/Passwort) werden *nicht*
abgefragt. Dort existiert schlicht kein Geheimnis – eine Abfrage wäre reines
Theater und würde nur den schnellen Testbetrieb ausbremsen. Der db_key liegt
bei Quick-Konten ohnehin base64-kodiert in ``users.json``.

Dieses Modul ist bewusst **Qt-frei**, damit die Policy headless testbar ist.
Die eigentliche Eingabemaske liegt im Dialog (``views/backup_restore_dialog.py``).
"""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

# Sicherheitsstufen, die eine Code-Abfrage erfordern.
SECURITY_QUICK = "quick"
SECURITY_PIN = "pin"
SECURITY_PASSWORD = "password"

_SECRET_SECURITY_LEVELS = frozenset({SECURITY_PIN, SECURITY_PASSWORD})

# Sicherheitsrelevante Aktionen (nur zur Protokollierung/Beschriftung).
ACTION_EXPORT = "export"
ACTION_IMPORT = "import"
ACTION_RESTORE = "restore"


class _Authenticator(Protocol):
    """Minimale Sicht auf ``UserModel`` – erleichtert das Testen."""

    def authenticate(self, username: str, secret: str) -> bytes | None: ...


def security_level(user) -> str:
    """Liest die Sicherheitsstufe robust aus einem User-Objekt."""
    if user is None:
        return SECURITY_QUICK
    level = getattr(user, "security", None)
    if not level:
        # Fallback über die Convenience-Properties, falls vorhanden.
        if getattr(user, "is_password", False):
            return SECURITY_PASSWORD
        if getattr(user, "is_pin", False):
            return SECURITY_PIN
        return SECURITY_QUICK
    return str(level)


def requires_code(user) -> bool:
    """True, wenn für ``user`` vor Backup-Aktionen ein Code nötig ist.

    Nur PIN- und Passwort-Konten. Quick-Konten (und ein fehlendes User-Objekt,
    z.B. im unverschlüsselten Legacy-Modus) laufen ohne Abfrage durch.
    """
    return security_level(user) in _SECRET_SECURITY_LEVELS


def verify_secret(user_model: _Authenticator, user, secret: str) -> bool:
    """Prüft ``secret`` gegen das Konto. Leerer Code ist immer ungültig.

    Nutzt ``UserModel.authenticate`` (liefert den db_key oder ``None``) und
    damit exakt denselben Pfad wie der Login – kein zweiter Krypto-Code.
    """
    if not requires_code(user):
        return True
    if not secret:
        return False
    username = getattr(user, "username", None)
    if not username:
        return False
    try:
        return user_model.authenticate(username, secret) is not None
    except Exception:
        logger.exception("Backup-Re-Authentifizierung fehlgeschlagen")
        return False
