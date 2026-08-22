"""
Benutzerverwaltung für den Budgetmanager.

Drei Sicherheitsstufen:
  "quick"    — Ohne Passwort, db_key lokal gespeichert (base64 in users.json)
  "pin"      — 4-8 Ziffern, db_key mit PIN-Key verschlüsselt, Restore-Key
  "password" — Passwort, db_key mit PW-Key verschlüsselt, Restore-Key

Jeder Benutzer hat eine eigene .enc-Datei (Fernet: AES-128-CBC + HMAC-SHA256).
DB ist IMMER verschlüsselt, auch bei Quick-Usern.

Benutzerdaten in data/users.json.
"""

from __future__ import annotations

from utils.atomic_write import atomar_schreiben
import logging

logger = logging.getLogger(__name__)

import json
import os
import re
from pathlib import Path
from dataclasses import dataclass, field, asdict, replace
from typing import Optional
from datetime import datetime

from model.app_paths import data_dir
from model.file_permissions import secure_file
from model.crypto import (
    generate_salt,
    generate_db_key,
    hash_password,
    verify_password,
    is_legacy_password_hash,
    wrap_db_key,
    unwrap_db_key,
    unwrap_db_key_with_iterations,
    db_key_to_restore_key,
    restore_key_to_db_key,
    create_empty_encrypted_db,
    decrypt_db_from_file,
    save_memory_db,
    encrypt_db_to_file,
    SALT_LENGTH,
    PBKDF2_ITERATIONS,
)

USERS_FILE = "users.json"

# Sicherheitsstufen
SECURITY_QUICK = "quick"  # Ohne Passwort
SECURITY_PIN = "pin"  # 4-8 Ziffern
SECURITY_PASSWORD = "password"  # Passwort

SECURITY_LABELS = {
    SECURITY_QUICK: "Ohne Passwort (Quick)",
    SECURITY_PIN: "PIN (4–8 Ziffern)",
    SECURITY_PASSWORD: "Passwort",
}

SECURITY_ICONS = {
    SECURITY_QUICK: "⚡",
    SECURITY_PIN: "🔢",
    SECURITY_PASSWORD: "🔒",
}


@dataclass
class User:
    username: str  # Eindeutiger Slug (a-z, 0-9, _, -)
    display_name: str  # Anzeigename frei wählbar ("Max Mustermann")
    security: str  # "quick" | "pin" | "password"
    salt_hex: str  # Salt als Hex
    db_filename: str  # z.B. "christian_kraemer.enc"
    created: str  # ISO-Datum
    # Für Quick: db_key direkt gespeichert (base64)
    db_key_b64: str = ""
    # Für PIN/PW: verschlüsselter db_key (base64 des Fernet-Tokens)
    wrapped_db_key_b64: str = ""
    # Für PIN/PW: Passwort-Hash zur schnellen Verifikation
    pw_hash: str = ""
    # Restore-Key wurde angeboten?
    restore_key_offered: bool = False
    # Standard-Benutzer (wird bei 1 User auto-login)
    is_default: bool = False
    # PBKDF2-Runden für PIN/PW-Key-Wrapping. Alte User ohne Feld werden
    # beim erfolgreichen Login automatisch auf PBKDF2_ITERATIONS gehoben.
    kdf_iterations: int = PBKDF2_ITERATIONS
    # Wird gesetzt, wenn ein Legacy-Konto erfolgreich einloggt, die lokale
    # Sicherheitsmigration aber nicht in users.json gespeichert werden konnte.
    security_upgrade_pending: bool = False
    security_upgrade_error: str = ""

    @property
    def salt(self) -> bytes:
        return bytes.fromhex(self.salt_hex)

    @property
    def db_path(self) -> Path:
        return data_dir() / self.db_filename

    @property
    def is_quick(self) -> bool:
        return self.security == SECURITY_QUICK

    @property
    def is_pin(self) -> bool:
        return self.security == SECURITY_PIN

    @property
    def is_password(self) -> bool:
        return self.security == SECURITY_PASSWORD

    @property
    def needs_auth(self) -> bool:
        """True wenn PIN oder Passwort nötig."""
        return self.security in (SECURITY_PIN, SECURITY_PASSWORD)

    @property
    def security_label(self) -> str:
        return SECURITY_LABELS.get(self.security, self.security)

    @property
    def security_icon(self) -> str:
        return SECURITY_ICONS.get(self.security, "")

    def get_db_key_and_iterations(self, secret: str = "") -> tuple[bytes, int]:
        """Gibt db_key und tatsächlich genutzte PBKDF2-Runden zurück."""
        import base64

        if self.is_quick:
            return self.db_key_b64.encode("ascii"), PBKDF2_ITERATIONS
        wrapped = base64.urlsafe_b64decode(self.wrapped_db_key_b64)
        return unwrap_db_key_with_iterations(wrapped, secret, self.salt)

    def get_db_key(self, secret: str = "") -> bytes:
        """Gibt den db_key zurück.

        Für Quick: direkt aus db_key_b64
        Für PIN/PW: unwrap mit secret

        Raises: ValueError bei falschem Secret
        """
        db_key, _iterations = self.get_db_key_and_iterations(secret)
        return db_key

    def get_db_key_with_restore(self, restore_key: str) -> bytes:
        """Gibt den db_key via Restore-Key zurück."""
        return restore_key_to_db_key(restore_key)


def _users_file_path() -> Path:
    return data_dir() / USERS_FILE


def _make_slug(name: str) -> str:
    """Erzeugt einen Dateinamen-sicheren Slug aus einem Display-Namen."""
    import unicodedata

    # Umlaute normalisieren
    nfkd = unicodedata.normalize("NFKD", name)
    ascii_str = nfkd.encode("ascii", "ignore").decode("ascii")
    # Nur alphanumerisch + Unterstrich
    clean = re.sub(r"[^a-zA-Z0-9]", "_", ascii_str.strip().lower())
    clean = re.sub(r"_+", "_", clean).strip("_")
    return clean[:40] or "user"


PIN_MIN_LENGTH = 6  # v2.2.15 (M5): vorher 4 – zu wenig fuer eine Finanz-DB
PIN_MAX_LENGTH = 8
PASSWORD_MIN_LENGTH = 10  # v2.2.15 (M5): vorher 4


def _validate_security_secret(security: str, secret: str = "") -> None:
    """Validiert Sicherheitsstufe und zugehöriges Secret zentral im Model.

    Wichtig: Die GUI validiert ebenfalls, aber das Model ist die letzte
    Schutzschicht. Dadurch können Tests, Scripts oder spätere Dialoge keine
    ungültige PIN/Passwort-Kombination in ``users.json`` speichern.

    v2.2.15 (M5): Gilt nur fuer NEUE Geheimnisse (Neuanlage und Wechsel).
    Bestehende Konten mit kuerzeren Secrets bleiben anmeldbar, da der Login
    diese Funktion nicht durchlaeuft.
    """
    if security not in (SECURITY_QUICK, SECURITY_PIN, SECURITY_PASSWORD):
        raise ValueError(f"Ungültige Sicherheitsstufe: {security}")
    if security == SECURITY_PIN:
        if not secret.isdigit() or not (
            PIN_MIN_LENGTH <= len(secret) <= PIN_MAX_LENGTH
        ):
            raise ValueError(
                f"PIN muss {PIN_MIN_LENGTH}–{PIN_MAX_LENGTH} Ziffern lang sein"
            )
    elif security == SECURITY_PASSWORD:
        if len(secret) < PASSWORD_MIN_LENGTH:
            raise ValueError(
                f"Passwort muss mindestens {PASSWORD_MIN_LENGTH} Zeichen lang sein"
            )


class UserModel:
    """Verwaltet Benutzerkonten."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._load()

    def _load(self) -> None:
        path = _users_file_path()
        if not path.exists():
            self._users = {}
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._users = {}
            valid_fields = set(User.__dataclass_fields__)
            for entry in data.get("users", []):
                filtered = {k: v for k, v in dict(entry).items() if k in valid_fields}
                u = User(**filtered)
                self._users[u.username] = u
        except Exception as e:
            logger.error("Fehler beim Laden der Benutzerdatei: %s", e)
            self._users = {}

    def _save(self) -> bool:
        path = _users_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            data = {"users": [asdict(u) for u in self._users.values()]}
            # SICHERHEIT (v2.2.11): users.json enthaelt bei Quick-Konten den
            # db_key im Klartext und sonst wrapped_db_key + pw_hash. Die
            # Rechte werden BEVOR dem Umbenennen gesetzt - sonst existiert
            # ein Zeitfenster, in dem die Datei mit umask-Rechten (typisch
            # 0644) lesbar ist. Genau das macht der Helfer; seit Loop 29
            # traegt er zusaetzlich den Verzeichnis-fsync und eine
            # Zwischendatei mit Prozessnummer bei, damit zwei gleichzeitig
            # laufende Instanzen sich nicht dieselbe teilen.
            atomar_schreiben(
                path, json.dumps(data, indent=2, ensure_ascii=False)
            )
            return True
        except Exception as e:
            logger.error("Fehler beim Speichern der Benutzerdatei: %s", e)
            return False

    # ── Abfragen ─────────────────────────────────

    def has_users(self) -> bool:
        return len(self._users) > 0

    def user_count(self) -> int:
        return len(self._users)

    def list_users(self) -> list[User]:
        return sorted(self._users.values(), key=lambda u: u.display_name.lower())

    def get(self, username: str) -> Optional[User]:
        return self._users.get(username)

    def username_exists(self, username: str) -> bool:
        return username in self._users

    def get_quick_users(self) -> list[User]:
        return [u for u in self._users.values() if u.is_quick]

    def get_auth_users(self) -> list[User]:
        return [u for u in self._users.values() if u.needs_auth]

    def get_default_user(self) -> Optional[User]:
        """Gibt den Standard-Benutzer zurück (falls gesetzt)."""
        for u in self._users.values():
            if u.is_default:
                return u
        return None

    def set_default_user(self, username: str) -> bool:
        """Setzt einen Benutzer als Standard.

        Gibt ``False`` zurück, wenn der Benutzer nicht existiert. In diesem Fall
        bleibt die bisherige Standard-Auswahl unverändert, damit ein Tippfehler
        oder stale UI-Status nicht alle Defaults entfernt.
        """
        if username not in self._users:
            logger.warning("Standard-Benutzer nicht gefunden: %s", username)
            return False
        for u in self._users.values():
            u.is_default = u.username == username
        self._save()
        return True

    # ── Erstellen ────────────────────────────────

    def create_user(
        self, display_name: str, security: str, secret: str = ""
    ) -> tuple[User, str]:
        """Erstellt einen neuen Benutzer.

        Args:
            display_name: Anzeigename ("Max Mustermann")
            security: "quick" | "pin" | "password"
            secret: PIN oder Passwort (leer bei Quick)

        Returns:
            (User, restore_key) — restore_key ist "" bei Quick

        Raises:
            ValueError: Ungültiger Name, existiert bereits, etc.
        """
        import base64

        display_name = display_name.strip()
        if not display_name:
            raise ValueError("Bitte einen Namen eingeben")

        slug = _make_slug(display_name)

        # Slug eindeutig machen
        base_slug = slug
        counter = 1
        while slug in self._users:
            slug = f"{base_slug}_{counter}"
            counter += 1

        _validate_security_secret(security, secret)

        salt = generate_salt()
        db_key = generate_db_key()
        restore_key = ""

        user = User(
            username=slug,
            display_name=display_name,
            security=security,
            salt_hex=salt.hex(),
            db_filename=f"{slug}.enc",
            created=datetime.now().isoformat(),
        )

        if security == SECURITY_QUICK:
            # db_key direkt speichern (base64-String)
            user.db_key_b64 = db_key.decode("ascii")
        else:
            # db_key mit Secret verschlüsseln
            wrapped = wrap_db_key(db_key, secret, salt)
            user.wrapped_db_key_b64 = base64.urlsafe_b64encode(wrapped).decode("ascii")
            user.pw_hash = hash_password(secret, salt)
            user.kdf_iterations = PBKDF2_ITERATIONS
            restore_key = db_key_to_restore_key(db_key)

        # Leere verschlüsselte DB erstellen
        conn = create_empty_encrypted_db(user.db_path, db_key, salt)
        conn.close()

        # Wenn erster User: automatisch als Default setzen
        if len(self._users) == 0:
            user.is_default = True

        self._users[slug] = user
        self._save()

        logger.info("Benutzer '%s' erstellt (Modus: %s)", display_name, security)
        return user, restore_key

    # ── Bearbeiten ───────────────────────────────

    def change_display_name(self, username: str, new_name: str) -> bool:
        """Ändert den Anzeigenamen eines Benutzers.

        Returns: True bei Erfolg
        """
        new_name = new_name.strip()
        if not new_name:
            return False

        user = self._users.get(username)
        if not user:
            return False

        user.display_name = new_name
        self._users[username] = user
        self._save()
        logger.info("Anzeigename für '%s' geändert zu '%s'", username, new_name)
        return True

    # ── Löschen ──────────────────────────────────

    def delete_user(self, username: str, delete_db: bool = True) -> bool:
        user = self._users.get(username)
        if not user:
            return False

        if delete_db and user.db_path.exists():
            try:
                user.db_path.unlink()
            except Exception as e:
                logger.error(
                    "DB-Datei löschen fehlgeschlagen — Benutzer wird nicht entfernt: %s",
                    e,
                )
                return False

        was_default = user.is_default
        del self._users[username]
        if (
            was_default
            and self._users
            and not any(u.is_default for u in self._users.values())
        ):
            # Stabiler Fallback: Wenn der Default-User gelöscht wird, bekommt
            # der alphabetisch erste verbleibende Benutzer den Default-Status.
            # Damit bleibt der Start-/Login-Pfad konsistent.
            next_default = sorted(
                self._users.values(), key=lambda u: u.display_name.lower()
            )[0]
            next_default.is_default = True
        self._save()
        logger.info("Benutzer '%s' gelöscht", username)
        return True

    def _upgrade_user_kdf(self, user: User, db_key: bytes, secret: str) -> None:
        """Hebt alte PIN/PW-Accounts nach erfolgreichem Login auf aktuelle PBKDF2-Runden.

        Die Datenbankverschlüsselung selbst nutzt den zufälligen db_key; geändert
        wird nur die lokale Verpackung dieses Schlüssels in users.json.
        """
        if user.is_quick:
            return
        try:
            import base64

            new_salt = generate_salt()
            wrapped = wrap_db_key(db_key, secret, new_salt)
            upgraded = replace(user)
            upgraded.wrapped_db_key_b64 = base64.urlsafe_b64encode(wrapped).decode(
                "ascii"
            )
            upgraded.pw_hash = hash_password(secret, new_salt)
            upgraded.salt_hex = new_salt.hex()
            upgraded.kdf_iterations = PBKDF2_ITERATIONS
            upgraded.security_upgrade_pending = False
            upgraded.security_upgrade_error = ""
            self._users[user.username] = upgraded
            if self._save():
                logger.info(
                    "PBKDF2-Parameter für Benutzer '%s' aktualisiert", user.username
                )
                return
            raise OSError(
                "users.json konnte nach PBKDF2-Upgrade nicht gespeichert werden"
            )
        except Exception as e:
            # Login darf nicht scheitern, nur weil die Härtungs-Migration nicht speichern konnte.
            warning_user = replace(user)
            warning_user.security_upgrade_pending = True
            warning_user.security_upgrade_error = str(e)
            self._users[user.username] = warning_user
            logger.warning(
                "PBKDF2-Upgrade für Benutzer '%s' fehlgeschlagen: %s", user.username, e
            )

    # ── Authentifizierung ────────────────────────

    def authenticate(self, username: str, secret: str) -> Optional[bytes]:
        """Authentifiziert und gibt den db_key zurück.

        Returns: db_key bei Erfolg, None bei Fehler
        """
        user = self._users.get(username)
        if not user:
            return None

        try:
            db_key, used_iterations = user.get_db_key_and_iterations(secret)
            # Bestandskonten auf aktuelle Haertung heben:
            # - alte PBKDF2-Rundenzahl, ODER
            # - alter, key-aequivalenter pw_hash (Sicherheits-Fix v2.0.41), auch
            #   wenn die Rundenzahl bereits aktuell ist.
            needs_upgrade = (not user.is_quick) and (
                used_iterations != PBKDF2_ITERATIONS
                or is_legacy_password_hash(secret, user.salt, user.pw_hash)
            )
            if needs_upgrade:
                self._upgrade_user_kdf(user, db_key, secret)
            return db_key
        except (ValueError, TypeError):
            # v2.2.30: TypeError zusätzlich – korrupte users.json-Werte
            # (z. B. manipulierter pw_hash) dürfen den Login nicht crashen,
            # sondern führen zur normalen Ablehnung.
            logger.warning("Authentifizierung fehlgeschlagen für '%s'", username)
            return None

    def authenticate_quick(self, username: str) -> Optional[bytes]:
        """Quick-Login ohne Secret."""
        user = self._users.get(username)
        if not user or not user.is_quick:
            return None
        try:
            return user.get_db_key()
        except Exception as e:
            logger.warning("Quick-Login fehlgeschlagen für '%s': %s", username, e)
            return None

    def authenticate_restore(self, username: str, restore_key: str) -> Optional[bytes]:
        """Authentifiziert mit Restore-Key."""
        user = self._users.get(username)
        if not user:
            return None
        try:
            db_key = user.get_db_key_with_restore(restore_key)
            # Verifizieren: versuche die DB zu öffnen
            if user.db_path.exists():
                conn = decrypt_db_from_file(user.db_path, db_key)
                conn.close()
            return db_key
        except Exception as e:
            logger.warning(
                "Restore-Key Authentifizierung fehlgeschlagen für '%s': %s", username, e
            )
            return None

    # ── Passwort/PIN ändern ──────────────────────

    def change_secret(
        self, username: str, old_secret: str, new_secret: str, new_security: str = ""
    ) -> tuple[bool, str]:
        """Ändert PIN/Passwort und optional die Sicherheitsstufe.

        Returns: (success, new_restore_key)
        """
        import base64

        user = self._users.get(username)
        if not user:
            return False, ""

        # Alten db_key holen
        try:
            if user.is_quick:
                db_key = user.get_db_key()
            else:
                db_key = user.get_db_key(old_secret)
        except ValueError:
            return False, ""

        new_security = new_security or user.security
        try:
            _validate_security_secret(new_security, new_secret)
        except ValueError as exc:
            logger.warning(
                "Ungültige neue Sicherheitsdaten für '%s': %s", username, exc
            )
            return False, ""

        new_salt = generate_salt()
        restore_key = ""

        if new_security == SECURITY_QUICK:
            user.db_key_b64 = db_key.decode("ascii")
            user.wrapped_db_key_b64 = ""
            user.pw_hash = ""
            user.kdf_iterations = PBKDF2_ITERATIONS
        else:
            wrapped = wrap_db_key(db_key, new_secret, new_salt)
            user.wrapped_db_key_b64 = base64.urlsafe_b64encode(wrapped).decode("ascii")
            user.pw_hash = hash_password(new_secret, new_salt)
            user.db_key_b64 = ""
            user.kdf_iterations = PBKDF2_ITERATIONS
            restore_key = db_key_to_restore_key(db_key)

        user.security = new_security
        user.salt_hex = new_salt.hex()
        if restore_key:
            user.restore_key_offered = True

        self._users[username] = user
        self._save()

        logger.info("Sicherheit für '%s' geändert → %s", username, new_security)
        return True, restore_key

    # ── Upgrade Quick → PIN/PW ───────────────────

    def upgrade_security(
        self, username: str, new_security: str, new_secret: str
    ) -> tuple[bool, str]:
        """Upgraded einen Quick-User zu PIN oder Passwort.

        Returns: (success, restore_key)
        """
        user = self._users.get(username)
        if not user or not user.is_quick:
            return False, ""
        return self.change_secret(username, "", new_secret, new_security)

    # ── Sicherheits-Check ────────────────────────

    def get_security_report(self) -> list[dict]:
        """Gibt einen Sicherheitsreport für alle Benutzer zurück."""
        report = []
        for u in self.list_users():
            report.append(
                {
                    "username": u.username,
                    "display_name": u.display_name,
                    "security": u.security,
                    "security_label": u.security_label,
                    "security_icon": u.security_icon,
                    "restore_offered": u.restore_key_offered,
                    "db_exists": u.db_path.exists(),
                    "needs_auth": u.needs_auth,
                    "kdf_iterations": u.kdf_iterations,
                    "security_upgrade_pending": u.security_upgrade_pending,
                    "security_upgrade_error": u.security_upgrade_error,
                }
            )
        return report
