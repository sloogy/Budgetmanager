"""Regression: Kein Brick-Loop beim Erststart-Restore mit falschem Code.

Wird beim Erststart ein Backup eingespielt und der Wiederherstellungscode ist
falsch (oder der Nutzer bricht ab), darf der Assistent NICHT auf der
Sicherheitsseite hängen bleiben. Stattdessen:
  - wird der eben angelegte Benutzer zurückgerollt,
  - kehrt der Assistent zur Auswahlseite zurück ("wieder von vorne":
    neuen Benutzer anlegen ODER Backup erneut einspielen),
  - und der Restore-Key des neuen Benutzers wird erst NACH erfolgreicher
    Entschlüsselung angezeigt (sonst gilt er für einen verworfenen Benutzer).

Reine Quelltextprüfung (kein Qt nötig) – analog test_startup_restore_regression.py.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _wizard_src() -> str:
    return (ROOT / "views" / "startup_wizard.py").read_text(encoding="utf-8")


def _finish_body() -> str:
    src = _wizard_src()
    body = src.split("    def _finish(self)", 1)[1]
    return body.split("\n    def ", 1)[0]


def test_restore_attempted_before_restore_key_is_shown():
    body = _finish_body()
    restore_pos = body.find("_restore_into_user(")
    showkey_pos = body.find("_show_restore_key(")
    assert restore_pos != -1, "Restore-Aufruf fehlt in _finish"
    assert showkey_pos != -1, "Restore-Key-Anzeige fehlt in _finish"
    assert restore_pos < showkey_pos, (
        "Restore muss VOR der Restore-Key-Anzeige erfolgen, damit der neue "
        "Key nicht für einen wieder verworfenen Benutzer angezeigt wird."
    )


def test_failed_restore_rolls_back_and_resets_to_start():
    body = _finish_body()
    assert "_rollback_created_user()" in body
    assert "_reset_to_start()" in body, (
        "Bei fehlgeschlagenem Restore muss der Assistent zum Anfang "
        "zurückkehren statt auf der Sicherheitsseite hängen zu bleiben."
    )


def test_reset_to_start_helper_returns_to_choice_and_clears_import():
    src = _wizard_src()
    assert "def _reset_to_start(self)" in src
    helper = src.split("    def _reset_to_start(self)", 1)[1].split("\n    def ", 1)[0]
    assert "self._import_src_path = None" in helper
    assert "self._goto(self._PAGE_CHOICE)" in helper


def test_retry_hint_key_present_and_referenced_in_all_locales():
    src = _wizard_src()
    assert 'tr("startup.restore_retry_from_start")' in src
    for loc in ("de", "en", "fr"):
        data = json.loads((ROOT / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
        val = data.get("startup", {}).get("restore_retry_from_start")
        assert val and val.strip(), f"{loc}: startup.restore_retry_from_start fehlt/leer"
