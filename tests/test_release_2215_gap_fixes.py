"""v2.2.15 – Schliessung der Rest-Luecken aus der Pre-Release-Tiefenanalyse.

B2+: Portable-ZIP-Updates muessen ein startfaehiges onedir-Bundle sein
     (Binary + nicht-leeres ``_internal/``); Installer genau eine Setup-EXE.
B5+: Schlaegt das Rollback-Backup fehl, wird das Update NICHT angewendet
     (vorher: Warnung und "fahre fort" – ohne Rettungsweg bei Abbruch).
M4:  CI-Workflow laeuft vor dem Release-Tag (push/PR), nicht erst danach.
M5:  Neue PIN >= 6 Ziffern, neues Passwort >= 10 Zeichen; Bestandskonten
     bleiben anmeldbar (Login validiert nicht ueber diese Funktion).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from updater.common import validate_staged_payload

ROOT = Path(__file__).resolve().parents[1]

def _erlaubte_workflows() -> list[str]:
    """Liest die erlaubte Liste aus dem Werkzeug, statt sie abzuschreiben.

    Sie stand hier viermal als ["build.yml"] und musste bei jeder Aenderung an
    vier Stellen nachgezogen werden - derselbe Fehler wie bei den Versionen in
    Loop 6.
    """
    import importlib.util

    pfad = ROOT / "tools" / "lint_procedure_check.py"
    spec = importlib.util.spec_from_file_location("lint_procedure_check", pfad)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return list(modul.ERLAUBTE_WORKFLOWS)



# ── B2+: onedir-Pflicht fuer ZIP-Assets ────────────────────────────────────
def test_portable_zip_without_internal_is_rejected(tmp_path):
    d = tmp_path / "st"
    d.mkdir()
    (d / "BudgetManager").write_text("bin")
    with pytest.raises(ValueError):
        validate_staged_payload(d, "portable-zip")


def test_portable_zip_with_empty_internal_is_rejected(tmp_path):
    d = tmp_path / "st"
    (d / "_internal").mkdir(parents=True)
    (d / "BudgetManager").write_text("bin")
    with pytest.raises(ValueError):
        validate_staged_payload(d, "portable-zip")


def test_portable_onedir_bundle_is_accepted(tmp_path):
    d = tmp_path / "st"
    (d / "_internal").mkdir(parents=True)
    (d / "BudgetManager").write_text("bin")
    (d / "_internal" / "lib.so").write_text("lib")
    validate_staged_payload(d, "portable-zip")  # darf nicht raisen


def test_source_tree_update_stays_accepted(tmp_path):
    """Der bewusst unterstuetzte Quelltext-Fall bleibt gueltig."""
    d = tmp_path / "st"
    d.mkdir()
    (d / "main.py").write_text("print()")
    (d / "app_info.py").write_text("APP_VERSION='x'")
    validate_staged_payload(d, "portable-zip")


def test_installer_staging_requires_exactly_one_setup_exe(tmp_path):
    d = tmp_path / "st"
    d.mkdir()
    (d / "BudgetManager_Setup_1.exe").write_text("s")
    validate_staged_payload(d, "installer")
    (d / "other.exe").write_text("s")
    # Eine eindeutige Setup-EXE bleibt akzeptiert, auch mit Beiwerk-EXE
    validate_staged_payload(d, "installer")
    (d / "BudgetManager_Setup_2.exe").write_text("s")
    with pytest.raises(ValueError):
        validate_staged_payload(d, "installer")


# ── B5+: Backup-Pflicht vor dem Anwenden ───────────────────────────────────
def test_apply_aborts_when_rollback_backup_fails_linux(monkeypatch, tmp_path):
    import updater.apply_update as apply_update
    import updater.common as common
    from updater.common import AssetInfo, Manifest, staged_tree_sha256

    updates = tmp_path / "updates"
    staging = updates / "staging" / "9.9.9"
    (staging / "_internal").mkdir(parents=True)
    (staging / "BudgetManager").write_bytes(b"bin")
    (staging / "_internal" / "lib.so").write_bytes(b"lib")

    # Gueltigen Marker mit Tree-Hash schreiben, damit die Verifikation passiert
    # und der Lauf wirklich erst am Backup scheitert.
    import json

    tree = staged_tree_sha256(staging)
    (staging / "_update_marker.json").write_text(
        json.dumps(
            {"version": "9.9.9", "asset_type": "portable-zip", "tree_sha256": tree}
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(apply_update, "updates_dir", lambda: updates)
    monkeypatch.setattr(common, "updates_dir", lambda: updates)
    monkeypatch.setattr(
        apply_update, "staging_dir_for", lambda v: updates / "staging" / v
    )
    monkeypatch.setattr(apply_update, "target_staged_version", lambda: "9.9.9")
    monkeypatch.setattr(apply_update, "is_windows", lambda: False)

    def boom(*_a, **_k):
        raise OSError(28, "No space left on device")

    monkeypatch.setattr(apply_update, "backup_current_zip", boom)

    rc = apply_update.main()
    assert rc == 12, f"Erwartet Abbruch (12) ohne Rollback-Backup, bekam {rc}"


def test_apply_source_has_no_continue_after_backup_failure():
    src = (ROOT / "updater" / "apply_update.py").read_text(encoding="utf-8")
    assert (
        "fahre fort" not in src
    ), "Backup-Fehlschlag darf nicht mehr 'fahre fort' sein"
    assert (
        src.count("return 12") >= 2
    ), "Abbruch muss in BEIDEN Pfaden (Win+Linux) greifen"


# ── M4: Qualitätschecks im einzigen Tag-Workflow ───────────────────────────
def test_single_tag_workflow_runs_quality_checks_before_packaging():
    workflows = ROOT / ".github" / "workflows"
    assert sorted(path.name for path in workflows.glob("*.yml")) == _erlaubte_workflows()
    text = (workflows / "build.yml").read_text(encoding="utf-8")
    for step in ("compileall", "sync_version.py --check", "pytest", "black", "mypy"):
        assert step in text, f"Release-Schritt fehlt: {step}"
    assert text.index("python -m pytest") < text.index("pyinstaller BudgetManager.spec")


# ── M5: Mindestlaengen fuer neue Geheimnisse ───────────────────────────────
def test_new_pin_requires_six_digits():
    from model.user_model import _validate_security_secret

    with pytest.raises(ValueError):
        _validate_security_secret("pin", "1234")
    with pytest.raises(ValueError):
        _validate_security_secret("pin", "12345")
    _validate_security_secret("pin", "123456")
    _validate_security_secret("pin", "12345678")
    with pytest.raises(ValueError):
        _validate_security_secret("pin", "123456789")  # > 8


def test_new_password_requires_ten_chars():
    from model.user_model import _validate_security_secret

    with pytest.raises(ValueError):
        _validate_security_secret("password", "kurz1234")  # 8
    _validate_security_secret("password", "LangGenug1")  # 10


def test_existing_short_pin_account_can_still_authenticate(tmp_path, monkeypatch):
    """Bestandskonto mit alter 4-stelliger PIN bleibt anmeldbar (M5-Zusage)."""
    import model.crypto as crypto
    import model.user_model as um

    monkeypatch.setattr(crypto, "PBKDF2_ITERATIONS", 1000)
    monkeypatch.setattr(um, "PBKDF2_ITERATIONS", 1000)
    monkeypatch.setattr(um, "_users_file_path", lambda: tmp_path / "users.json")
    monkeypatch.setattr(um, "data_dir", lambda: tmp_path)

    model = um.UserModel()
    # Bestand simulieren: Validierung wie vor v2.2.15 umgehen und ein Konto
    # mit 4-stelliger PIN anlegen.
    monkeypatch.setattr(um, "_validate_security_secret", lambda *_a, **_k: None)
    user, _rk = model.create_user("Alt", um.SECURITY_PIN, "4711")

    # Login (authenticate) laeuft NICHT ueber _validate_security_secret:
    assert model.authenticate(user.username, "4711") is not None
    assert model.authenticate(user.username, "0000") is None


def test_ui_dialogs_use_model_constants():
    for rel in (
        "views/login_dialog.py",
        "views/account_management_dialog.py",
        "views/startup_wizard.py",
    ):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "PIN_MIN_LENGTH" in src, f"{rel}: nutzt Model-Konstanten nicht"
        assert "4 <= len" not in src, f"{rel}: alte 4er-Grenze noch vorhanden"
