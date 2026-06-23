from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_legacy_200k_wrapped_key_still_authenticates_and_upgrades(
    monkeypatch, tmp_path
):
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))

    import importlib
    import model.app_paths as ap
    import model.user_model as um
    import model.crypto as crypto

    importlib.reload(ap)
    importlib.reload(crypto)
    importlib.reload(um)
    monkeypatch.setattr(crypto, "PBKDF2_ITERATIONS", 1_000)
    monkeypatch.setattr(um, "PBKDF2_ITERATIONS", 1_000)

    secret = "1234"
    salt = crypto.generate_salt()
    db_key = crypto.generate_db_key()
    wrapped = crypto._ensure_crypto()(
        crypto.derive_key_from_secret(secret, salt, iterations=200_000)
    ).encrypt(db_key)

    user_payload = {
        "users": [
            {
                "username": "legacy",
                "display_name": "Legacy",
                "security": um.SECURITY_PIN,
                "salt_hex": salt.hex(),
                "db_filename": "legacy.enc",
                "created": "2026-01-01T00:00:00",
                "db_key_b64": "",
                "wrapped_db_key_b64": base64.urlsafe_b64encode(wrapped).decode("ascii"),
                "pw_hash": crypto.hash_password(secret, salt, iterations=200_000),
                "restore_key_offered": True,
                "is_default": True,
            }
        ]
    }
    users_file = ap.data_dir() / "users.json"
    users_file.write_text(json.dumps(user_payload), encoding="utf-8")

    model = um.UserModel()
    authenticated = model.authenticate("legacy", secret)
    assert authenticated == db_key

    data = json.loads(users_file.read_text(encoding="utf-8"))
    upgraded = data["users"][0]
    assert upgraded["kdf_iterations"] == crypto.PBKDF2_ITERATIONS
    assert upgraded["salt_hex"] != salt.hex()

    # Der neu verpackte Key darf nicht mehr nur mit 200k funktionieren.
    new_salt = bytes.fromhex(upgraded["salt_hex"])
    new_wrapped = base64.urlsafe_b64decode(upgraded["wrapped_db_key_b64"])
    assert crypto.unwrap_db_key(new_wrapped, secret, new_salt) == db_key
