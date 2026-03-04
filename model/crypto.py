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
import secrets
import sqlite3
from pathlib import Path

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


# ── Konstanten ──────────────────────────────────────────────────

PBKDF2_ITERATIONS = 200_000
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


def derive_key_from_secret(secret: str, salt: bytes) -> bytes:
    """Leitet einen Fernet-Key aus einem Geheimnis (PIN/Passwort) + Salt ab."""
    raw = hashlib.pbkdf2_hmac(
        "sha256", secret.encode("utf-8"), salt,
        PBKDF2_ITERATIONS, dklen=DB_KEY_LENGTH,
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


def unwrap_db_key(wrapped: bytes, secret: str, salt: bytes) -> bytes:
    """Entschlüsselt den db_key mit secret.

    Raises: ValueError bei falschem Secret.
    """
    Fernet = _ensure_crypto()
    from cryptography.fernet import InvalidToken
    wrapping_key = derive_key_from_secret(secret, salt)
    f = Fernet(wrapping_key)
    try:
        return f.decrypt(wrapped)
    except InvalidToken:
        raise ValueError("Falsches Passwort/PIN")
    except Exception as e:
        logger.error("Unerwarteter Fehler beim Entschlüsseln des DB-Keys: %s", e)
        raise ValueError(f"Entschlüsselung fehlgeschlagen: {e}")


def unwrap_db_key_with_restore(wrapped_restore: bytes, restore_key: str) -> bytes:
    """Entschlüsselt den db_key mit dem Restore-Key.

    Der Restore-Key ist der db_key selbst als Hex — also wird er direkt dekodiert.
    """
    try:
        raw = bytes.fromhex(restore_key.strip().replace(" ", "").replace("-", ""))
        return base64.urlsafe_b64encode(raw)
    except Exception:
        raise ValueError("Ungültiger Restore-Key")


# ── Restore-Key ────────────────────────────────────────────────

def db_key_to_restore_key(db_key: bytes) -> str:
    """Wandelt einen db_key in einen lesbaren Restore-Key um.

    Format: 8 Gruppen à 8 Hex-Zeichen, getrennt durch Bindestriche.
    Beispiel: A3F2B1C4-D5E6F7A8-...
    """
    raw = base64.urlsafe_b64decode(db_key)
    hex_str = raw.hex().upper()
    groups = [hex_str[i:i + 8] for i in range(0, len(hex_str), 8)]
    return "-".join(groups)


def restore_key_to_db_key(restore_key: str) -> bytes:
    """Wandelt einen Restore-Key zurück in einen db_key."""
    clean = restore_key.strip().replace(" ", "").replace("-", "")
    try:
        raw = bytes.fromhex(clean)
        if len(raw) != DB_KEY_LENGTH:
            raise ValueError(f"Restore-Key hat falsche Länge ({len(raw)} statt {DB_KEY_LENGTH})")
        return base64.urlsafe_b64encode(raw)
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Ungültiger Restore-Key: {e}")


# ── Passwort-Hash (für Verifikation ohne DB-Zugriff) ──────────

def hash_password(password: str, salt: bytes) -> str:
    """Erzeugt Passwort-Hash zur schnellen Verifikation."""
    raw = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt,
        PBKDF2_ITERATIONS, dklen=32,
    )
    return raw.hex()


def verify_password(password: str, salt: bytes, stored_hash: str) -> bool:
    """Prüft Passwort gegen gespeicherten Hash."""
    return hash_password(password, salt) == stored_hash


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

def encrypt_db_to_file(conn: sqlite3.Connection, enc_path: str | Path,
                       db_key: bytes, salt: bytes) -> None:
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
        os.replace(str(tmp_path), str(enc_path))
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
            raise ValueError("Korrupte Datei: Salt zu kurz")
        token = f.read()

    try:
        dump_sql = decrypt_bytes(token, db_key).decode("utf-8")
    except Exception:
        raise ValueError("Entschlüsselung fehlgeschlagen — falscher Schlüssel")

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.executescript(dump_sql)
    conn.execute("PRAGMA foreign_keys = ON;")
    conn.execute("PRAGMA busy_timeout = 5000;")
    return conn


def read_salt_from_enc(enc_path: str | Path) -> bytes:
    """Liest Salt aus .enc-Datei (erste 16 Bytes)."""
    with open(enc_path, "rb") as f:
        salt = f.read(SALT_LENGTH)
    if len(salt) < SALT_LENGTH:
        raise ValueError("Korrupte Datei")
    return salt


def create_empty_encrypted_db(enc_path: str | Path, db_key: bytes,
                              salt: bytes) -> sqlite3.Connection:
    """Erstellt leere verschlüsselte DB.

    Returns: Offene In-Memory-Connection
    """
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    encrypt_db_to_file(conn, enc_path, db_key, salt)
    return conn


def save_memory_db(conn: sqlite3.Connection, enc_path: str | Path,
                   db_key: bytes, salt: bytes) -> None:
    """Speichert In-Memory-DB verschlüsselt auf Disk."""
    encrypt_db_to_file(conn, enc_path, db_key, salt)
