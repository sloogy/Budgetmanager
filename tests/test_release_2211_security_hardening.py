"""v2.2.11 – Sicherheitsanalyse: Regressionstests.

Die Datenbank ist immer verschlüsselt. Der Schutz steht und fällt daher mit
(a) dem Schlüsselmaterial auf der Platte und (b) der Frage, ob fremde Daten
ungeprüft in die Installation gelangen können.

Abgedeckt:
1. Dateirechte – ``users.json`` und ``.enc`` dürfen nicht world-readable sein.
2. Bundle-Integrität – SHA256 gegen das Manifest.
3. Zip-Slip – kein Name aus dem Archiv wird je als Pfad verwendet.
4. Zip-Bomb – harte Grössenlimits für die Metadateien.
"""

from __future__ import annotations

import sqlite3
import stat
import zipfile
from pathlib import Path

import pytest

import model.crypto as crypto
from model.file_permissions import (
    OWNER_ONLY_FILE,
    is_world_accessible,
    secure_file,
)
from model.restore_bundle import (
    MAX_SETTINGS_BYTES,
    BundleIntegrityError,
    create_bundle,
    verify_bundle,
)


def _mode(p: Path) -> int:
    return stat.S_IMODE(p.stat().st_mode)


@pytest.fixture
def bundle(tmp_path) -> Path:
    src = tmp_path / "source.enc"
    src.write_bytes(b"ENCRYPTED-DB" * 64)
    return create_bundle(
        source_db=src,
        out_path=tmp_path / "good.bmr",
        app="BudgetManager",
        app_version="2.2.11",
    )


def _rebuild(bundle: Path, out: Path, mutate) -> Path:
    with zipfile.ZipFile(bundle, "r") as src, zipfile.ZipFile(out, "w") as dst:
        mutate(src, dst)
    return out


# ── 1. Dateirechte ────────────────────────────────────────────────────────
def test_users_json_is_not_world_readable(tmp_path, monkeypatch):
    """users.json enthält bei Quick-Konten den db_key im Klartext."""
    import model.user_model as um

    monkeypatch.setattr(um, "PBKDF2_ITERATIONS", 1000)
    monkeypatch.setattr(crypto, "PBKDF2_ITERATIONS", 1000)
    users_file = tmp_path / "users.json"
    monkeypatch.setattr(um, "_users_file_path", lambda: users_file)
    # WICHTIG: create_user legt zusätzlich die .enc unter data_dir() an.
    # Ohne Umlenkung würde jeder Testlauf den Release-Baum verschmutzen.
    monkeypatch.setattr(um, "data_dir", lambda: tmp_path)

    model = um.UserModel()
    model.create_user("Tester", "quick")

    assert users_file.exists()
    assert _mode(users_file) == OWNER_ONLY_FILE, oct(_mode(users_file))
    assert is_world_accessible(users_file) is False

    # Der Schlüssel liegt bei Quick-Konten im Klartext – genau deshalb 0600.
    enc_files = list(tmp_path.glob("*.enc"))
    assert enc_files, "keine verschlüsselte DB angelegt"
    for enc in enc_files:
        assert _mode(enc) == OWNER_ONLY_FILE, oct(_mode(enc))


def test_encrypted_db_file_is_not_world_readable(tmp_path, monkeypatch):
    monkeypatch.setattr(crypto, "PBKDF2_ITERATIONS", 1000)
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE t(a)")
    conn.commit()

    enc = tmp_path / "db.enc"
    crypto.encrypt_db_to_file(
        conn, enc, crypto.generate_db_key(), crypto.generate_salt()
    )

    assert _mode(enc) == OWNER_ONLY_FILE, oct(_mode(enc))
    conn.close()


def test_backup_bundle_is_not_world_readable(bundle):
    assert _mode(bundle) == OWNER_ONLY_FILE, oct(_mode(bundle))


def test_secure_file_is_idempotent_and_safe_on_missing(tmp_path):
    p = tmp_path / "x"
    assert secure_file(p) is False  # existiert nicht → kein Absturz
    p.write_text("x")
    assert secure_file(p) is True
    assert secure_file(p) is True
    assert _mode(p) == OWNER_ONLY_FILE


# ── 2. Integrität (SHA256) ────────────────────────────────────────────────
def test_valid_bundle_verifies(bundle):
    assert verify_bundle(bundle) == "database.enc"


def test_tampered_database_is_rejected(bundle, tmp_path):
    def mutate(src, dst):
        for name in src.namelist():
            data = src.read(name)
            if name == "database.enc":
                data = b"EVIL" + data[4:]
            dst.writestr(name, data)

    bad = _rebuild(bundle, tmp_path / "bad.bmr", mutate)
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bad)


def test_truncated_database_is_rejected(bundle, tmp_path):
    def mutate(src, dst):
        for name in src.namelist():
            data = src.read(name)
            if name == "database.enc":
                data = data[: len(data) // 2]
            dst.writestr(name, data)

    bad = _rebuild(bundle, tmp_path / "trunc.bmr", mutate)
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bad)


def test_missing_manifest_is_rejected(bundle, tmp_path):
    def mutate(src, dst):
        for name in src.namelist():
            if name != "manifest.json":
                dst.writestr(name, src.read(name))

    bad = _rebuild(bundle, tmp_path / "nomani.bmr", mutate)
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bad)


def test_non_zip_file_is_rejected(tmp_path):
    p = tmp_path / "fake.bmr"
    p.write_bytes(b"definitely not a zip")
    with pytest.raises(BundleIntegrityError):
        verify_bundle(p)


def test_missing_bundle_is_rejected(tmp_path):
    with pytest.raises(BundleIntegrityError):
        verify_bundle(tmp_path / "does_not_exist.bmr")


# ── 3. Zip-Slip ───────────────────────────────────────────────────────────
def test_unexpected_member_is_rejected(bundle, tmp_path):
    """Ein Traversal-Name darf gar nicht erst akzeptiert werden."""

    def mutate(src, dst):
        for name in src.namelist():
            dst.writestr(name, src.read(name))
        dst.writestr("../../../../etc/cron.d/pwn", "* * * * * root evil\n")

    bad = _rebuild(bundle, tmp_path / "slip.bmr", mutate)
    with pytest.raises(BundleIntegrityError):
        verify_bundle(bad)


# ── 4. Zip-Bomb ───────────────────────────────────────────────────────────
def test_oversized_settings_is_rejected(bundle, tmp_path):
    out = tmp_path / "bomb.bmr"
    with zipfile.ZipFile(bundle, "r") as src, zipfile.ZipFile(
        out, "w", zipfile.ZIP_DEFLATED
    ) as dst:
        for name in src.namelist():
            dst.writestr(name, src.read(name))
        dst.writestr("settings.json", b"A" * (MAX_SETTINGS_BYTES + 1))

    with pytest.raises(BundleIntegrityError):
        verify_bundle(out)


# ── 5. Der Dialog nutzt die Prüfung auch wirklich ─────────────────────────
def test_dialog_verifies_bundle_before_restore():
    src = (
        Path(__file__).resolve().parents[1] / "views" / "backup_restore_dialog.py"
    ).read_text(encoding="utf-8")

    assert "verify_bundle" in src, "Restore prüft die Integrität nicht"
    assert src.count("verify_bundle(") >= 2, "Nicht beide Restore-Pfade geprüft"
    assert "secure_file" in src, "Wiederhergestellte Dateien werden nicht abgesichert"
