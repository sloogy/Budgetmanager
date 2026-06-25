"""Sicherheits-Regression v2.0.41 – Trennung Verifikations-Hash / Wrapping-Key.

Hintergrund:
Frueher nutzten ``hash_password`` und ``derive_key_from_secret`` exakt dieselbe
PBKDF2-Eingabe (Secret, Salt, 600k, dklen=32). Der in ``users.json`` gespeicherte
``pw_hash`` war damit byte-identisch zum Wrapping-Key (nur hex statt base64). Wer
die Datei lesen konnte, konnte aus ``pw_hash`` + ``wrapped_db_key_b64`` den db_key
OHNE Passwort rekonstruieren und die .enc-DB entschluesseln.

Abgedeckt:
1. Der gespeicherte Hash kann den Wrapping-Key NICHT mehr ergeben (PoC schlaegt fehl).
2. ``verify_password`` akzeptiert neues Format und (fuer Bestandskonten) das alte.
3. End-to-End: ein Account mit altem, key-aequivalentem Hash – auch bereits bei
   aktueller Rundenzahl – wird beim Login auf das sichere Format migriert
   (Salt-Rotation, Hash nicht mehr key-aequivalent).

Laeuft ohne Qt/PySide6.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import model.crypto as crypto  # noqa: E402
from cryptography.fernet import Fernet, InvalidToken  # noqa: E402


def test_stored_password_hash_cannot_reconstruct_wrapping_key():
    secret = "MeinGeheimesPasswort123"
    salt = crypto.generate_salt()
    db_key = crypto.generate_db_key()

    wrapped = crypto.wrap_db_key(db_key, secret, salt)
    pw_hash = crypto.hash_password(secret, salt)

    # Alter Angriff: pw_hash (hex) als rohe Wrapping-Key-Bytes interpretieren.
    forged = base64.urlsafe_b64encode(bytes.fromhex(pw_hash))
    try:
        recovered = Fernet(forged).decrypt(wrapped)
        assert recovered != db_key, "pw_hash darf den Wrapping-Key nicht ergeben"
    except InvalidToken:
        pass  # erwartet: geforgter Key ist falsch


def test_verify_password_accepts_new_and_legacy_rejects_wrong():
    secret = "pw"
    salt = crypto.generate_salt()

    new_hash = crypto.hash_password(secret, salt)
    legacy_hash = crypto._legacy_hash_password(secret, salt, crypto.PBKDF2_ITERATIONS)

    assert crypto.verify_password(secret, salt, new_hash) is True
    assert crypto.verify_password(secret, salt, legacy_hash) is True
    assert crypto.verify_password("falsch", salt, new_hash) is False

    assert crypto.is_legacy_password_hash(secret, salt, legacy_hash) is True
    assert crypto.is_legacy_password_hash(secret, salt, new_hash) is False


def test_login_migrates_legacy_key_equivalent_hash_even_at_current_iterations(monkeypatch, tmp_path):
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))

    import importlib
    import model.app_paths as ap
    import model.user_model as um
    import model.crypto as c

    importlib.reload(ap)
    importlib.reload(c)
    importlib.reload(um)
    monkeypatch.setattr(c, "PBKDF2_ITERATIONS", 1_000)
    monkeypatch.setattr(um, "PBKDF2_ITERATIONS", 1_000)

    secret = "1234"
    salt = c.generate_salt()
    db_key = c.generate_db_key()
    # Account auf AKTUELLER Rundenzahl, aber mit altem key-aequivalentem Hash:
    # genau die Luecke, die der reine Rundenzahl-Trigger verfehlt haette.
    wrapped = c.wrap_db_key(db_key, secret, salt)
    legacy_hash = c._legacy_hash_password(secret, salt, c.PBKDF2_ITERATIONS)

    payload = {
        "users": [
            {
                "username": "legacy_hash",
                "display_name": "LegacyHash",
                "security": um.SECURITY_PASSWORD,
                "salt_hex": salt.hex(),
                "db_filename": "lh.enc",
                "created": "2026-01-01T00:00:00",
                "db_key_b64": "",
                "wrapped_db_key_b64": base64.urlsafe_b64encode(wrapped).decode("ascii"),
                "pw_hash": legacy_hash,
                "restore_key_offered": True,
                "is_default": True,
                "kdf_iterations": c.PBKDF2_ITERATIONS,
            }
        ]
    }
    users_file = ap.data_dir() / "users.json"
    users_file.write_text(json.dumps(payload), encoding="utf-8")

    model = um.UserModel()
    assert model.authenticate("legacy_hash", secret) == db_key

    upgraded = json.loads(users_file.read_text(encoding="utf-8"))["users"][0]

    # Salt wurde rotiert ...
    assert upgraded["salt_hex"] != salt.hex()
    new_salt = bytes.fromhex(upgraded["salt_hex"])
    new_hash = upgraded["pw_hash"]

    # ... und der neue Hash ist NICHT mehr key-aequivalent.
    assert c.is_legacy_password_hash(secret, new_salt, new_hash) is False

    # Der neue gespeicherte Hash kann den neuen Wrapping-Key nicht ergeben.
    new_wrapped = base64.urlsafe_b64decode(upgraded["wrapped_db_key_b64"])
    forged = base64.urlsafe_b64encode(bytes.fromhex(new_hash))
    try:
        recovered = Fernet(forged).decrypt(new_wrapped)
        assert recovered != db_key
    except InvalidToken:
        pass

    # Login bleibt funktional.
    assert c.unwrap_db_key(new_wrapped, secret, new_salt) == db_key


def test_failed_legacy_upgrade_is_visible_in_security_report(monkeypatch, tmp_path):
    """Login bleibt möglich, aber ein nicht gespeichertes KDF-Upgrade wird sichtbar."""
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))

    import importlib
    import model.app_paths as ap
    import model.user_model as um
    import model.crypto as c

    importlib.reload(ap)
    importlib.reload(c)
    importlib.reload(um)

    # Tests sollen nicht wegen echter 600k-PBKDF2 mehrfach langsam werden; die
    # Regression prüft den Kontrollfluss, nicht die absolute Iterationszahl.
    monkeypatch.setattr(c, "PBKDF2_ITERATIONS", 1_000)
    monkeypatch.setattr(um, "PBKDF2_ITERATIONS", 1_000)

    secret = "1234"
    salt = c.generate_salt()
    db_key = c.generate_db_key()
    wrapped = c.wrap_db_key(db_key, secret, salt)
    legacy_hash = c._legacy_hash_password(secret, salt, c.PBKDF2_ITERATIONS)

    payload = {
        "users": [
            {
                "username": "legacy_pending",
                "display_name": "Legacy Pending",
                "security": um.SECURITY_PIN,
                "salt_hex": salt.hex(),
                "db_filename": "lp.enc",
                "created": "2026-01-01T00:00:00",
                "db_key_b64": "",
                "wrapped_db_key_b64": base64.urlsafe_b64encode(wrapped).decode("ascii"),
                "pw_hash": legacy_hash,
                "restore_key_offered": True,
                "is_default": True,
                "kdf_iterations": c.PBKDF2_ITERATIONS,
            }
        ]
    }
    users_file = ap.data_dir() / "users.json"
    users_file.write_text(json.dumps(payload), encoding="utf-8")

    model = um.UserModel()
    monkeypatch.setattr(um.UserModel, "_save", lambda self: False)

    assert model.authenticate("legacy_pending", secret) == db_key

    report = model.get_security_report()[0]
    assert report["security_upgrade_pending"] is True
    assert "users.json" in report["security_upgrade_error"]
