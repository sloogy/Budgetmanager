"""
Kryptographie-Modul für den Budgetmanager.

Jede Benutzer-DB wird mit einem zufälligen db_key (32 Bytes) verschlüsselt.
Der db_key wird je nach Sicherheitsstufe unterschiedlich geschützt:

  Quick (ohne PW):  db_key wird base64-kodiert in users.json gespeichert
  PIN:              db_key wird mit PIN-abgeleitetem Key (PBKDF2) verschlüsselt
  Passwort:         db_key wird mit Passwort-abgeleitetem Key (PBKDF2) verschlüsselt

Restore-Key (nur PIN/PW): Der db_key als Hex-String — kann die .enc direkt
entschlüsseln. Wird einmalig angezeigt, nie gespeichert.

Dateiformat .enc:  [16 Bytes Salt][Fernet-Token]
"""

from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

import os
import base64
import hashlib
import hmac
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Callable


class CryptoUserError(ValueError):
    """Benutzer-sichtbarer Krypto-Fehler mit i18n-Key.

    Bleibt eine ``ValueError``-Subklasse, damit bestehende
    ``except ValueError``/``except Exception`` Pfade unverändert greifen.
    Über ``__str__`` wird der Text zur Anzeigezeit nach de/en/fr übersetzt;
    der deutsche ``fallback`` dient nur, falls der Key fehlt oder die i18n
    noch nicht initialisiert ist. Dadurch werden Restore-/Entschlüsselungs-
    Fehler in Dialogen lokalisiert statt hart auf Deutsch ausgegeben.
    """

    def __init__(self, key: str, fallback: str):
        super().__init__(fallback)
        self.key = key
        self.fallback = fallback

    def __str__(self) -> str:
        try:
            from utils.i18n import tr

            translated = tr(self.key)
            return (
                translated if translated and translated != self.key else self.fallback
            )
        except Exception:
            return self.fallback


# Lazy-Import: cryptography ist optional
_fernet_cls = None


def _ensure_crypto():
    """Importiert cryptography bei Bedarf."""
    global _fernet_cls
    if _fernet_cls is None:
        try:
            from cryptography.fernet import Fernet

            _fernet_cls = Fernet
        except ImportError:
            raise ImportError(
                "Das Paket 'cryptography' wird für die Verschlüsselung benötigt.\n"
                "Installiere es mit:  pip install cryptography"
            )
    return _fernet_cls


def is_crypto_available() -> bool:
    """Prüft ob cryptography installiert ist."""
    try:
        _ensure_crypto()
        return True
    except ImportError:
        return False


class AutosaveConnection(sqlite3.Connection):
    """SQLite-Connection mit optionalem Hook nach erfolgreichem COMMIT.

    Der BudgetManager nutzt im verschluesselten Modus eine In-Memory-DB.
    Ein normales ``conn.commit()`` schreibt dort nur in den RAM.  Bei einem
    nativen Qt/PySide-Absturz waeren die letzten Aenderungen sonst verloren,
    bis ``EncryptedSession.save()`` beim Schliessen laeuft.

    Diese Subklasse meldet erfolgreiche Commits an die Session, damit die
    verschluesselte ``.enc`` Datei sofort aktualisiert werden kann.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._after_commit_callback: Callable[[str], None] | None = None
        self._after_commit_suspended = 0
        self._after_commit_pending = False

    def set_after_commit_callback(self, callback: Callable[[str], None] | None) -> None:
        self._after_commit_callback = callback

    def suspend_after_commit(self) -> None:
        self._after_commit_suspended += 1

    def resume_after_commit(self) -> None:
        if self._after_commit_suspended > 0:
            self._after_commit_suspended -= 1
        if self._after_commit_suspended == 0 and self._after_commit_pending:
            self._after_commit_pending = False
            self._notify_after_commit("resume")

    def _notify_after_commit(self, reason: str) -> None:
        callback = self._after_commit_callback
        if callback is None:
            return
        if self._after_commit_suspended > 0:
            self._after_commit_pending = True
            return
        try:
            callback(reason)
        except Exception as exc:
            logger.error("Auto-Save nach DB-Commit fehlgeschlagen: %s", exc)

    def commit(self) -> None:
        super().commit()
        self._notify_after_commit("commit")

    def execute(self, sql, parameters=(), /):
        cursor = super().execute(sql, parameters)
        try:
            normalized = str(sql).strip().upper().rstrip(";")
            if normalized in {"COMMIT", "END"}:
                self._notify_after_commit("execute_commit")
        except Exception as fehler:
            # Die Benachrichtigung darf die Anweisung selbst nie scheitern
            # lassen - sie ist schon ausgefuehrt. Aber wer sich auf sie
            # verlaesst und nichts hoert, soll den Grund finden.
            logger.warning("Commit-Benachrichtigung fehlgeschlagen: %s", fehler)
        return cursor


@contextmanager
def coalesced_commits(conn: sqlite3.Connection):
    """Bündelt viele DB-Commits zu einem verschlüsselten Disk-Save.

    Im verschlüsselten Modus löst jeder erfolgreiche ``conn.commit()`` über
    :class:`AutosaveConnection` sofort eine vollständige Fernet-Neuverschlüsselung
    der In-Memory-DB plus ``.enc``-Schreibvorgang aus. Das ist für einzelne
    Nutzeraktionen wichtig, kann bei Massenoperationen aber stark ruckeln.

    Dieser Kontextmanager pausiert die commit-getriebene Persistenz für die Dauer
    des Blocks und führt beim Verlassen genau einen finalen Disk-Save aus, wenn
    innerhalb des Blocks Commits passiert sind. Für normale ``sqlite3.Connection``
    ohne Autosave-Hooks ist er ein sicherer No-op.
    """
    suspended = False
    try:
        suspend = getattr(conn, "suspend_after_commit", None)
        if callable(suspend):
            suspend()
            suspended = True
        yield conn
    finally:
        if suspended:
            try:
                resume = getattr(conn, "resume_after_commit", None)
                if callable(resume):
                    resume()
            except Exception as exc:  # pragma: no cover - defensiv
                logger.debug(
                    "coalesced_commits: resume_after_commit fehlgeschlagen: %s", exc
                )


@contextmanager
def suspend_after_commit_autosave(conn: sqlite3.Connection):
    """Rückwärtskompatibler Alias für :func:`coalesced_commits`."""
    with coalesced_commits(conn) as managed_conn:
        yield managed_conn


# ── Konstanten ──────────────────────────────────────────────────


def _secure_file(path) -> None:
    """0600 auf sensible Dateien. Lazy-Import haelt crypto.py abhaengigkeitsarm.

    Scheitern darf das - auf FAT/exFAT gibt es keine POSIX-Modi, und ein
    Stick soll deswegen nicht unbrauchbar sein. Schweigen darf es nicht:
    Bis Loop 25 blieb die Datei dann weltlesbar, und niemand erfuhr davon.
    Es sind dieselben Daten, die Loop 12 gerade zugesperrt hat.
    """
    try:
        from model.file_permissions import secure_file

        secure_file(path)
    except Exception as fehler:  # nie fatal, aber nie stumm
        logger.warning(
            "Zugriffsrechte auf %s nicht gesetzt - die Datei bleibt offen: %s",
            path, fehler,
        )


PBKDF2_ITERATIONS = 600_000  # OWASP-2023-Empfehlung (PBKDF2-HMAC-SHA256)
LEGACY_PBKDF2_ITERATIONS = (200_000,)
SALT_LENGTH = 16
DB_KEY_LENGTH = 32  # 32 Bytes → base64 = Fernet-Key


# ── Key-Erzeugung ──────────────────────────────────────────────


def generate_salt() -> bytes:
    """Erzeugt kryptographisch sicheren Salt (16 Bytes)."""
    return os.urandom(SALT_LENGTH)


def generate_db_key() -> bytes:
    """Erzeugt einen zufälligen DB-Schlüssel (32 Bytes raw → Fernet-Key)."""
    raw = os.urandom(DB_KEY_LENGTH)
    return base64.urlsafe_b64encode(raw)


def derive_key_from_secret(
    secret: str, salt: bytes, iterations: int | None = None
) -> bytes:
    """Leitet einen Fernet-Key aus einem Geheimnis (PIN/Passwort) + Salt ab."""
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        secret.encode("utf-8"),
        salt,
        int(iterations or PBKDF2_ITERATIONS),
        dklen=DB_KEY_LENGTH,
    )
    return base64.urlsafe_b64encode(raw)


# ── Key Wrapping (für PIN/PW-Modus) ────────────────────────────


def wrap_db_key(db_key: bytes, secret: str, salt: bytes) -> bytes:
    """Verschlüsselt den db_key mit einem aus secret abgeleiteten Key.

    Returns: Fernet-Token (bytes) der den db_key enthält.
    """
    Fernet = _ensure_crypto()
    wrapping_key = derive_key_from_secret(secret, salt)
    f = Fernet(wrapping_key)
    return f.encrypt(db_key)


def unwrap_db_key_with_iterations(
    wrapped: bytes, secret: str, salt: bytes
) -> tuple[bytes, int]:
    """Entschlüsselt den db_key und meldet die verwendete PBKDF2-Rundenzahl.

    Alte v2.0.23-Test-/Vorabdaten nutzten 200 000 Runden. Damit solche
    Konten nicht ausgesperrt werden, akzeptieren wir bekannte Legacy-Werte und
    verpacken den Schlüssel nach erfolgreichem Login automatisch neu.
    """
    Fernet = _ensure_crypto()
    from cryptography.fernet import InvalidToken

    last_error: Exception | None = None
    for iterations in (PBKDF2_ITERATIONS, *LEGACY_PBKDF2_ITERATIONS):
        wrapping_key = derive_key_from_secret(secret, salt, iterations=iterations)
        f = Fernet(wrapping_key)
        try:
            return f.decrypt(wrapped), int(iterations)
        except InvalidToken as exc:
            last_error = exc
            continue
        except Exception as e:
            logger.error("Unerwarteter Fehler beim Entschlüsseln des DB-Keys: %s", e)
            raise ValueError(f"Entschlüsselung fehlgeschlagen: {e}")
    raise ValueError("Falsches Passwort/PIN") from last_error


def unwrap_db_key(wrapped: bytes, secret: str, salt: bytes) -> bytes:
    """Entschlüsselt den db_key mit secret.

    Raises: ValueError bei falschem Secret.
    """
    db_key, _iterations = unwrap_db_key_with_iterations(wrapped, secret, salt)
    return db_key


def unwrap_db_key_with_restore(wrapped_restore: bytes, restore_key: str) -> bytes:
    """Entschlüsselt den db_key mit dem Restore-Key.

    Der Restore-Key ist der db_key selbst als Hex — also wird er direkt dekodiert.
    """
    try:
        raw = bytes.fromhex(restore_key.strip().replace(" ", "").replace("-", ""))
        return base64.urlsafe_b64encode(raw)
    except Exception:
        raise CryptoUserError(
            "account.ungueltiger_restorekey", "Ungültiger Restore-Key"
        )


# ── Restore-Key ────────────────────────────────────────────────


def db_key_to_restore_key(db_key: bytes) -> str:
    """Wandelt einen db_key in einen lesbaren Restore-Key um.

    Format: 8 Gruppen à 8 Hex-Zeichen, getrennt durch Bindestriche.
    Beispiel: A3F2B1C4-D5E6F7A8-...
    """
    raw = base64.urlsafe_b64decode(db_key)
    hex_str = raw.hex().upper()
    groups = [hex_str[i : i + 8] for i in range(0, len(hex_str), 8)]
    return "-".join(groups)


def restore_key_to_db_key(restore_key: str) -> bytes:
    """Wandelt einen Restore-Key zurück in einen db_key."""
    clean = restore_key.strip().replace(" ", "").replace("-", "")
    try:
        raw = bytes.fromhex(clean)
        if len(raw) != DB_KEY_LENGTH:
            raise ValueError(
                f"Restore-Key hat falsche Länge ({len(raw)} statt {DB_KEY_LENGTH})"
            )
        return base64.urlsafe_b64encode(raw)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Ungültiger Restore-Key: {e}")


# ── Passwort-Hash (für Verifikation ohne DB-Zugriff) ──────────
#
# SICHERHEIT (v2.0.41): Der Verifikations-Hash MUSS kryptographisch von der
# Schluessel-Ableitung getrennt sein. Frueher nutzten ``hash_password`` und
# ``derive_key_from_secret`` exakt dieselbe PBKDF2-Eingabe (Secret, Salt, 600k,
# dklen=32). Dadurch war der in ``users.json`` gespeicherte ``pw_hash`` byte-
# identisch zum Wrapping-Key (nur hex statt base64) – wer die Datei lesen
# konnte, konnte den db_key OHNE Passwort rekonstruieren und die .enc-DB
# entschluesseln. Die Domain-Trennung ueber ``PW_VERIFY_CONTEXT`` als
# Salt-Praefix macht den Hash nutzlos zur Schluesselrueckgewinnung; ein
# Angreifer muss wieder das Passwort gegen PBKDF2 600k brute-forcen.
PW_VERIFY_CONTEXT = b"budgetmanager-pw-verify-v2\x00"


def hash_password(password: str, salt: bytes, iterations: int | None = None) -> str:
    """Erzeugt Passwort-Hash zur schnellen Verifikation.

    Domain-getrennt von der Wrapping-Key-Ableitung (siehe SICHERHEIT oben):
    der Hash kann nicht zur Rekonstruktion des Wrapping-Keys verwendet werden.
    """
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        PW_VERIFY_CONTEXT + salt,
        int(iterations or PBKDF2_ITERATIONS),
        dklen=32,
    )
    return raw.hex()


def _legacy_hash_password(password: str, salt: bytes, iterations: int) -> str:
    """Alter, key-aequivalenter Hash – NUR zur Verifikation bestehender Accounts.

    Identisch zur Wrapping-Key-Eingabe. Wird nie mehr geschrieben; dient nur
    dazu, vor v2.0.41 angelegte Accounts noch zu erkennen und beim Login auf
    das domain-getrennte Format zu heben.
    """
    raw = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        int(iterations),
        dklen=32,
    )
    return raw.hex()


def _is_comparable_stored_hash(stored_hash: object) -> bool:
    """True, wenn ``stored_hash`` sicher mit ``hmac.compare_digest`` (str/str)
    vergleichbar ist.

    v2.2.30 (Deep-Audit Befund 2): Ein von Hand editierter oder korrupter
    ``pw_hash`` in users.json (z. B. Nicht-ASCII) liess ``compare_digest``
    mit ``TypeError`` abstürzen statt die Anmeldung abzulehnen. Beide
    gültigen Formate (domain-getrennt und legacy) sind Hex-Strings, also
    reines ASCII; alles andere ist per Definition kein gültiger Hash und
    wird fail-closed als ``False`` behandelt.
    """
    if not isinstance(stored_hash, str) or not stored_hash:
        return False
    try:
        stored_hash.encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def is_legacy_password_hash(password: str, salt: bytes, stored_hash: str) -> bool:
    """True, wenn ``stored_hash`` im alten, key-aequivalenten Format vorliegt.

    Wird beim Login genutzt, um betroffene Accounts (auch solche bereits bei
    600k Runden) auf das sichere Hash-Format zu migrieren.
    Korrupte ``stored_hash``-Werte (Nicht-ASCII, falscher Typ) gelten
    fail-closed als "kein Legacy-Hash" statt eine Exception auszulösen.
    """
    if not _is_comparable_stored_hash(stored_hash):
        return False
    for iterations in (PBKDF2_ITERATIONS, *LEGACY_PBKDF2_ITERATIONS):
        if hmac.compare_digest(
            _legacy_hash_password(password, salt, iterations), stored_hash
        ):
            return True
    return False


def verify_password(password: str, salt: bytes, stored_hash: str) -> bool:
    """Prüft Passwort gegen gespeicherten Hash.

    Akzeptiert das neue domain-getrennte Format und – fuer Bestandskonten –
    die alten key-aequivalenten Hashes (beide PBKDF2-Rundenzahlen).
    Korrupte oder nicht vergleichbare ``stored_hash``-Werte werden
    fail-closed abgelehnt statt eine Exception auszulösen.
    """
    if not _is_comparable_stored_hash(stored_hash):
        return False
    if hmac.compare_digest(hash_password(password, salt), stored_hash):
        return True
    return is_legacy_password_hash(password, salt, stored_hash)


# ── Encrypt / Decrypt Bytes ─────────────────────────────────────


def encrypt_bytes(data: bytes, db_key: bytes) -> bytes:
    """Verschlüsselt Bytes mit Fernet."""
    Fernet = _ensure_crypto()
    f = Fernet(db_key)
    return f.encrypt(data)


def decrypt_bytes(token: bytes, db_key: bytes) -> bytes:
    """Entschlüsselt Fernet-Token."""
    Fernet = _ensure_crypto()
    f = Fernet(db_key)
    return f.decrypt(token)


# ── SQLite DB Encrypt / Decrypt ─────────────────────────────────


def encrypt_db_to_file(
    conn: sqlite3.Connection, enc_path: str | Path, db_key: bytes, salt: bytes
) -> None:
    """Dumpt SQLite-Connection und verschlüsselt auf Disk.

    Dateiformat: [16 Bytes Salt][Fernet-Token]
    """
    dump_lines = list(conn.iterdump())
    dump_sql = "\n".join(dump_lines).encode("utf-8")

    encrypted = encrypt_bytes(dump_sql, db_key)

    enc_path = Path(enc_path)
    enc_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = enc_path.with_suffix(".tmp")
    try:
        with open(tmp_path, "wb") as f:
            f.write(salt)
            f.write(encrypted)
            f.flush()
            os.fsync(f.fileno())
        # SICHERHEIT (v2.2.11): Rechte vor dem Umbenennen setzen, damit die
        # verschluesselte DB nie kurzzeitig world-readable auf der Platte liegt.
        _secure_file(tmp_path)
        os.replace(str(tmp_path), str(enc_path))
        _secure_file(enc_path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def decrypt_db_from_file(enc_path: str | Path, db_key: bytes) -> sqlite3.Connection:
    """Entschlüsselt .enc-Datei in In-Memory-SQLite-DB.

    Returns: sqlite3.Connection auf :memory: DB
    Raises: FileNotFoundError, ValueError
    """
    enc_path = Path(enc_path)
    if not enc_path.exists():
        raise FileNotFoundError(f"Nicht gefunden: {enc_path}")

    with open(enc_path, "rb") as f:
        salt = f.read(SALT_LENGTH)
        if len(salt) < SALT_LENGTH:
            raise CryptoUserError(
                "crypto.corrupt_salt_short", "Korrupte Datei: Salt zu kurz"
            )
        token = f.read()

    try:
        dump_sql = decrypt_bytes(token, db_key).decode("utf-8")
    except Exception:
        raise CryptoUserError(
            "crypto.decrypt_failed_wrong_key",
            "Entschlüsselung fehlgeschlagen — falscher Schlüssel",
        )

    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.row_factory = sqlite3.Row
    conn.executescript(dump_sql)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    return conn


def read_salt_from_enc(enc_path: str | Path) -> bytes:
    """Liest Salt aus .enc-Datei (erste 16 Bytes)."""
    with open(enc_path, "rb") as f:
        salt = f.read(SALT_LENGTH)
    if len(salt) < SALT_LENGTH:
        raise ValueError("Korrupte Datei")
    return salt


def create_empty_encrypted_db(
    enc_path: str | Path, db_key: bytes, salt: bytes
) -> sqlite3.Connection:
    """Erstellt leere verschlüsselte DB.

    Returns: Offene In-Memory-Connection
    """
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    encrypt_db_to_file(conn, enc_path, db_key, salt)
    return conn


def save_memory_db(
    conn: sqlite3.Connection, enc_path: str | Path, db_key: bytes, salt: bytes
) -> None:
    """Speichert In-Memory-DB verschlüsselt auf Disk."""
    encrypt_db_to_file(conn, enc_path, db_key, salt)
