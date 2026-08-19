"""v2.2.10 – Re-Authentifizierung vor Export/Import/Restore.

Sicherheitsregel:
* PIN- und Passwort-Konten müssen den Code bestätigen.
* Quick-Konten (kein Geheimnis) werden NICHT gefragt – bewusst, damit der
  schnelle Testbetrieb nicht ausgebremst wird.

Die Policy liegt Qt-frei in ``model/backup_auth.py`` und ist deshalb headless
prüfbar. Der Dialog selbst wird nur statisch auf die Einhängepunkte geprüft.
"""

from __future__ import annotations

from pathlib import Path

from model.backup_auth import (
    ACTION_EXPORT,
    ACTION_IMPORT,
    ACTION_RESTORE,
    requires_code,
    security_level,
    verify_secret,
)

ROOT = Path(__file__).resolve().parents[1]


class _User:
    def __init__(self, security, username="christian"):
        self.security = security
        self.username = username


class _FakeUserModel:
    """Akzeptiert genau ein Geheimnis und liefert dann einen db_key."""

    def __init__(self, expected: str):
        self.expected = expected
        self.calls: list[tuple[str, str]] = []

    def authenticate(self, username, secret):
        self.calls.append((username, secret))
        return b"\x01" * 32 if secret == self.expected else None


# ── Policy: wer muss einen Code eingeben? ─────────────────────────────────
def test_quick_account_requires_no_code():
    assert requires_code(_User("quick")) is False


def test_pin_and_password_accounts_require_code():
    assert requires_code(_User("pin")) is True
    assert requires_code(_User("password")) is True


def test_missing_user_requires_no_code():
    """Unverschlüsselter Legacy-Modus ohne User-Objekt: keine Abfrage."""
    assert requires_code(None) is False
    assert security_level(None) == "quick"


# ── Verifikation gegen UserModel.authenticate ─────────────────────────────
def test_verify_secret_accepts_correct_code():
    um = _FakeUserModel("1234")
    assert verify_secret(um, _User("pin"), "1234") is True
    assert um.calls == [("christian", "1234")]


def test_verify_secret_rejects_wrong_code():
    um = _FakeUserModel("1234")
    assert verify_secret(um, _User("pin"), "9999") is False


def test_verify_secret_rejects_empty_code_without_calling_model():
    um = _FakeUserModel("1234")
    assert verify_secret(um, _User("password"), "") is False
    assert um.calls == [], "Leerer Code darf das UserModel gar nicht erst befragen"


def test_verify_secret_passes_through_for_quick_account():
    um = _FakeUserModel("egal")
    # Quick: keine Prüfung, kein Modell-Aufruf.
    assert verify_secret(um, _User("quick"), "") is True
    assert um.calls == []


def test_verify_secret_survives_broken_user_model():
    class _Boom:
        def authenticate(self, username, secret):
            raise RuntimeError("users.json kaputt")

    assert verify_secret(_Boom(), _User("pin"), "1234") is False


def test_verify_secret_requires_username():
    um = _FakeUserModel("1234")
    user = _User("pin")
    user.username = ""
    assert verify_secret(um, user, "1234") is False


# ── Dialog: sind die Einhängepunkte wirklich verdrahtet? ──────────────────
def test_dialog_guards_export_import_and_restore():
    src = (ROOT / "views" / "backup_restore_dialog.py").read_text(encoding="utf-8")

    assert "def _require_auth" in src
    for action in (ACTION_EXPORT, ACTION_IMPORT, ACTION_RESTORE):
        assert f'self._require_auth("{action}")' in src, f"Guard fehlt für {action}"

    # Seit v2.2.16 (K4) liegt die Eingabemaske zentral in views/reauth.py –
    # der Dialog delegiert. Verdeckte Eingabe dort pruefen.
    reauth = (ROOT / "views" / "reauth.py").read_text(encoding="utf-8")
    assert "require_reauth" in src
    assert "QLineEdit.Password" in reauth


def test_dialog_uses_translated_auth_strings():
    src = (ROOT / "views" / "reauth.py").read_text(encoding="utf-8")
    for key in ("backup.auth_title", "backup.auth_text", "backup.auth_failed"):
        assert key in src, f"i18n-Key {key} nicht verwendet"
