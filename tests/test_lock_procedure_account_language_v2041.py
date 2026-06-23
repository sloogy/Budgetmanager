"""Regressionen fuer Release-Prozedur, Account-Management und Sprach-Hardening.

Diese Tests sind bewusst Qt-frei, damit sie in der normalen CI frueh laufen und
nicht von GUI/Display-Abhaengigkeiten blockiert werden.
"""
from __future__ import annotations

import importlib
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── Lock-in der Release-/Lint-Prozedur ────────────────────────────────


def test_lint_procedure_locks_required_regression_tests_into_release_gate():
    src = _read("tools/lint_procedure_check.py")
    assert "def check_required_regression_tests" in src
    assert "test_lock_procedure_account_language_v2041.py" in src
    assert "test_lint_release_procedure_v2041.py" in src
    assert "test_password_hash_keysep_v2041.py" in src


def test_lint_procedure_passes_with_locked_regression_tests():
    subprocess.run([sys.executable, "tools/clean_release_tree.py"], cwd=ROOT, check=True)
    result = subprocess.run(
        [sys.executable, "tools/lint_procedure_check.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout


def test_requirements_lock_header_matches_app_info_version_and_date():
    app_info = _read("app_info.py")
    version = re.search(r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", app_info, re.MULTILINE)
    date = re.search(r"^APP_RELEASE_DATE\s*=\s*['\"]([^'\"]+)['\"]", app_info, re.MULTILINE)
    assert version and date
    expected = f"# Stand: v{version.group(1)} / {date.group(1)}"
    first_lines = _read("requirements.lock").splitlines()[:5]
    assert expected in first_lines


# ── Account-Management / UserModel ────────────────────────────────────


@pytest.fixture()
def isolated_user_model(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    # Module neu laden, damit keine alte Umgebung aus anderen Tests durchscheint.
    import model.app_paths as app_paths
    import model.user_model as user_model

    importlib.reload(app_paths)
    importlib.reload(user_model)
    return user_model.UserModel(), user_model


def test_account_lifecycle_quick_pin_password_delete(isolated_user_model):
    model, user_model = isolated_user_model

    user, restore = model.create_user("Christian Test", user_model.SECURITY_QUICK)
    assert restore == ""
    assert user.is_default is True
    assert user.username == "christian_test"
    assert user.db_path.exists()
    assert model.authenticate_quick(user.username)

    assert model.change_display_name(user.username, "Christian Release") is True
    assert model.get(user.username).display_name == "Christian Release"

    ok, pin_restore = model.upgrade_security(user.username, user_model.SECURITY_PIN, "1234")
    assert ok is True
    assert pin_restore
    assert model.authenticate(user.username, "1234")
    assert model.authenticate(user.username, "9999") is None

    ok, pw_restore = model.change_secret(
        user.username,
        "1234",
        "release-safe-password",
        user_model.SECURITY_PASSWORD,
    )
    assert ok is True
    assert pw_restore
    assert model.authenticate(user.username, "release-safe-password")
    assert model.authenticate(user.username, "1234") is None

    db_path = model.get(user.username).db_path
    assert model.delete_user(user.username, delete_db=True) is True
    assert model.get(user.username) is None
    assert not db_path.exists()


def test_account_validation_rejects_weak_or_invalid_secrets(isolated_user_model):
    model, user_model = isolated_user_model

    with pytest.raises(ValueError, match="Namen"):
        model.create_user("   ", user_model.SECURITY_QUICK)
    with pytest.raises(ValueError, match="PIN"):
        model.create_user("Bad Pin", user_model.SECURITY_PIN, "12ab")
    with pytest.raises(ValueError, match="PIN"):
        model.create_user("Short Pin", user_model.SECURITY_PIN, "123")
    with pytest.raises(ValueError, match="Passwort"):
        model.create_user("Weak Password", user_model.SECURITY_PASSWORD, "abc")


def test_account_slug_collision_and_default_user_are_stable(isolated_user_model):
    model, user_model = isolated_user_model

    first, _ = model.create_user("Max Müller", user_model.SECURITY_QUICK)
    second, _ = model.create_user("Max Mueller", user_model.SECURITY_QUICK)

    assert first.username == "max_muller"
    assert second.username == "max_mueller"
    assert model.get_default_user().username == first.username

    model.set_default_user(second.username)
    assert model.get_default_user().username == second.username


# ── Language / Security-Label-Hardening ───────────────────────────────


def test_security_labels_are_localized_for_de_en_fr():
    from utils.i18n import display_secret_kind, display_security_label, set_language

    expectations = {
        "de": ("Passwort", "Ohne Passwort"),
        "en": ("Password", "No password"),
        "fr": ("Mot de passe", "Sans mot de passe"),
    }
    for lang, (password_label, quick_prefix) in expectations.items():
        set_language(lang)
        assert display_security_label("password") == password_label
        assert display_security_label("quick").startswith(quick_prefix)
        assert display_secret_kind("password").lower() in password_label.lower()

    set_language("de")


def test_views_do_not_use_german_model_security_labels_directly():
    for rel in [
        "views/account_management_dialog.py",
        "views/login_dialog.py",
        "views/main_window.py",
        "views/backup_restore_dialog.py",
    ]:
        src = _read(rel)
        assert "SECURITY_LABELS" not in src
        assert ".security_label" not in src
        assert "display_security_label(" in src


def test_account_dialog_has_no_hardcoded_secret_words_in_ui_logic():
    src = _read("views/account_management_dialog.py")
    forbidden = [
        'else "Passwort"',
        'else "Aktuelles Passwort:"',
        'else "Neues Passwort:"',
        '"Passwort eingeben"',
        '"Passwort wiederholen"',
        '"Willst du wirklich den Passwortschutz entfernen?',
    ]
    for token in forbidden:
        assert token not in src


def test_referenced_security_language_keys_exist_in_all_locales():
    required_keys = {
        "security.label.quick",
        "security.label.pin",
        "security.label.password",
        "security.secret.pin",
        "security.secret.password",
        "security.checklist_title",
        "security.mode",
        "security.loss_protection",
        "security.no_loss_protection",
        "security.restore_key",
        "security.db_exists",
        "account.confirm_remove_password_protection",
    }

    def flatten(obj: object, prefix: str = "") -> dict[str, str]:
        out: dict[str, str] = {}
        if isinstance(obj, dict):
            for key, value in obj.items():
                full = f"{prefix}.{key}" if prefix else str(key)
                if isinstance(value, dict):
                    out.update(flatten(value, full))
                else:
                    out[full] = str(value)
        return out

    for lang in ("de", "en", "fr"):
        values = flatten(json.loads(_read(f"locales/{lang}.json")))
        missing = sorted(required_keys - set(values))
        assert not missing, f"{lang} missing: {missing}"


def test_account_model_rejects_invalid_secret_changes_and_keeps_state(isolated_user_model):
    model, user_model = isolated_user_model

    user, _ = model.create_user("Guarded", user_model.SECURITY_QUICK)

    ok, restore = model.upgrade_security(user.username, user_model.SECURITY_PIN, "12ab")
    assert (ok, restore) == (False, "")
    assert model.get(user.username).security == user_model.SECURITY_QUICK
    assert model.authenticate_quick(user.username)

    ok, restore = model.upgrade_security(user.username, user_model.SECURITY_PASSWORD, "abc")
    assert (ok, restore) == (False, "")
    assert model.get(user.username).security == user_model.SECURITY_QUICK

    ok, restore = model.upgrade_security(user.username, "totally-invalid", "1234")
    assert (ok, restore) == (False, "")
    assert model.get(user.username).security == user_model.SECURITY_QUICK

    ok, restore = model.upgrade_security(user.username, user_model.SECURITY_PIN, "1234")
    assert ok is True and restore
    assert model.get(user.username).security == user_model.SECURITY_PIN

    ok, restore = model.change_secret(user.username, "1234", "12ab", user_model.SECURITY_PIN)
    assert (ok, restore) == (False, "")
    assert model.authenticate(user.username, "1234")
    assert model.authenticate(user.username, "12ab") is None

    ok, restore = model.change_secret(user.username, "1234", "abc", user_model.SECURITY_PASSWORD)
    assert (ok, restore) == (False, "")
    assert model.get(user.username).security == user_model.SECURITY_PIN
    assert model.authenticate(user.username, "1234")


def test_default_user_cannot_be_cleared_by_invalid_username_and_promotes_on_delete(isolated_user_model):
    model, user_model = isolated_user_model

    first, _ = model.create_user("Alpha", user_model.SECURITY_QUICK)
    second, _ = model.create_user("Beta", user_model.SECURITY_QUICK)
    assert model.get_default_user().username == first.username

    assert model.set_default_user("does-not-exist") is False
    assert model.get_default_user().username == first.username

    assert model.delete_user(first.username, delete_db=True) is True
    assert model.get_default_user().username == second.username
    assert model.get(second.username).is_default is True
