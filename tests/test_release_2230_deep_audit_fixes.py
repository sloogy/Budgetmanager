"""Regressionstests v2.2.30 (DEEP_AUDIT_FIXES).

Sichert die Befunde des unabhängigen Deep-Audits auf v2.2.29 ab:

Befund 2 (Robustheit Login): Ein korrupter ``pw_hash`` in users.json
(Nicht-ASCII, falscher Typ) liess ``hmac.compare_digest`` in
``verify_password``/``is_legacy_password_hash`` mit ``TypeError``
abstürzen; ``UserModel.authenticate`` fing nur ``ValueError``. Ergebnis:
Login-Crash statt sauberer Ablehnung.

Hinweis A (UI-Konsistenz): Theme-Editor-Bestätigungen für Löschen und
Zurücksetzen hatten keinen expliziten sicheren Default-Button; Qt macht
sonst implizit "Yes" zum Default (Enter löscht).

Hinweis B (Doku im UI): ``tags.action_text_label`` erwähnte die von
``TagsModel.render_action_text`` unterstützten Monats-Platzhalter
({month}/{monat}) in keiner Sprache.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import model.crypto as crypto  # noqa: E402
from model.crypto import (  # noqa: E402
    _is_comparable_stored_hash,
    generate_salt,
    hash_password,
    is_legacy_password_hash,
    verify_password,
)


def _fast_iterations(monkeypatch) -> None:
    monkeypatch.setattr(crypto, "PBKDF2_ITERATIONS", 1000)
    monkeypatch.setattr(crypto, "LEGACY_PBKDF2_ITERATIONS", (600,))


# ── Befund 2: verify_password / is_legacy_password_hash ──────────────────


def test_comparable_stored_hash_guard() -> None:
    assert _is_comparable_stored_hash("ab" * 32)
    assert _is_comparable_stored_hash("beliebiger-ascii-string")
    assert not _is_comparable_stored_hash("")
    assert not _is_comparable_stored_hash(None)
    assert not _is_comparable_stored_hash(b"bytes")
    assert not _is_comparable_stored_hash("nicht-ascii-ü" + "0" * 50)
    assert not _is_comparable_stored_hash(1234)


def test_verify_password_accepts_valid_and_rejects_wrong(monkeypatch) -> None:
    _fast_iterations(monkeypatch)
    salt = generate_salt()
    stored = hash_password("geheim", salt)
    assert verify_password("geheim", salt, stored) is True
    assert verify_password("falsch", salt, stored) is False


def test_verify_password_corrupt_hash_returns_false_not_raise(monkeypatch) -> None:
    _fast_iterations(monkeypatch)
    salt = generate_salt()
    # Vor v2.2.30: TypeError aus hmac.compare_digest (str vs. Nicht-ASCII/Typ).
    assert verify_password("geheim", salt, "ü" * 64) is False
    assert verify_password("geheim", salt, None) is False
    assert verify_password("geheim", salt, b"\x00" * 64) is False
    assert verify_password("geheim", salt, 1234) is False


def test_is_legacy_password_hash_corrupt_returns_false(monkeypatch) -> None:
    _fast_iterations(monkeypatch)
    salt = generate_salt()
    assert is_legacy_password_hash("geheim", salt, "käse" * 16) is False
    assert is_legacy_password_hash("geheim", salt, None) is False
    assert is_legacy_password_hash("geheim", salt, b"raw") is False


def test_legacy_detection_still_works_after_guard(monkeypatch) -> None:
    _fast_iterations(monkeypatch)
    salt = generate_salt()
    legacy = crypto._legacy_hash_password("geheim", salt, 1000)
    assert is_legacy_password_hash("geheim", salt, legacy) is True
    assert verify_password("geheim", salt, legacy) is True


def _isolated_user_model(monkeypatch, tmp_path):
    """UserModel vollständig in tmp_path isolieren (Hausstandard).

    Wie in test_lock_procedure_account_language_v2041: BUDGETMANAGER_APP_DIR
    setzen und app_paths/user_model neu laden, damit users.json UND die
    beim Anlegen erzeugte Konto-DB (data/<name>.enc) im Temp-Verzeichnis
    landen statt im Release-Baum.
    """
    import importlib

    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(tmp_path))
    import model.app_paths as app_paths
    import model.user_model as um

    importlib.reload(app_paths)
    importlib.reload(um)
    monkeypatch.setattr(um, "PBKDF2_ITERATIONS", 1000, raising=False)
    return um


def test_authenticate_survives_corrupt_pw_hash(monkeypatch, tmp_path) -> None:
    """Login mit intaktem wrapped_db_key, aber korruptem pw_hash:

    Der Key wird korrekt entpackt; die Legacy-Erkennung liefert dank Guard
    ``False`` statt ``TypeError``. Der Login liefert den db_key.
    """
    _fast_iterations(monkeypatch)
    um = _isolated_user_model(monkeypatch, tmp_path)
    model = um.UserModel()
    model.create_user("chris", "password", "geheim-und-lang")
    user = model._users["chris"]
    user.pw_hash = "ü" * 64  # von Hand korrumpiert

    key = model.authenticate("chris", "geheim-und-lang")
    assert isinstance(key, bytes) and len(key) > 0
    # Isolation nachgewiesen: Konto-DB liegt im Temp-Verzeichnis.
    assert list(tmp_path.rglob("*.enc"))


def test_authenticate_catches_typeerror(monkeypatch, tmp_path) -> None:
    """Selbst wenn tiefer im Pfad ein TypeError entsteht, wird abgelehnt."""
    _fast_iterations(monkeypatch)
    um = _isolated_user_model(monkeypatch, tmp_path)
    model = um.UserModel()
    model.create_user("chris", "password", "geheim-und-lang")

    def _boom(*_a, **_k):
        raise TypeError("synthetisch")

    monkeypatch.setattr(um, "is_legacy_password_hash", _boom)
    assert model.authenticate("chris", "geheim-und-lang") is None


# ── Hinweis A: Theme-Editor-Defaults ─────────────────────────────────────


def test_theme_editor_destructive_confirms_default_no() -> None:
    src = (ROOT / "views" / "theme_editor_dialog.py").read_text(encoding="utf-8")
    for key in ("theme.msg.delete_confirm", "theme.msg.reset_confirm"):
        m = re.search(
            re.escape(key)
            + r".*?QMessageBox\.Yes \| QMessageBox\.No,\s*QMessageBox\.No,",
            src,
            re.S,
        )
        assert m, f"Explizites No-Default fehlt bei {key}"


# ── Hinweis B: Platzhalter-Doku + Engine-Deckung ─────────────────────────


def test_action_text_label_mentions_month_placeholder_all_locales() -> None:
    expect = {"de": "{monat}", "en": "{month}", "fr": "{month}"}
    for lang, token in expect.items():
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        label = data["tags"]["action_text_label"]
        assert token in label, (lang, label)


def test_render_action_text_supports_documented_placeholders() -> None:
    from datetime import date

    from model.tags_model import TagsModel

    out = TagsModel.render_action_text(
        "{date}|{datum}|{tag}|{category}|{kategorie}|{month}|{monat}",
        tag_name="Urlaub",
        category="Reisen",
        booking_date=date(2026, 7, 15),
    )
    parts = out.split("|")
    assert parts[0] == parts[1] == "2026-07-15"
    assert parts[2] == "Urlaub"
    assert parts[3] == parts[4] == "Reisen"
    assert parts[5] == parts[6] and parts[5] != ""
    # Unbekannte Platzhalter bleiben sicher als Rohtext erhalten.
    raw = TagsModel.render_action_text("{unbekannt}", tag_name="t", category="c")
    assert raw == "{unbekannt}"
