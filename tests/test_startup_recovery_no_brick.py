"""Regression: Ein defektes/verwaistes Konto sperrt den Nutzer nicht aus.

Szenario aus dem Feld: Beim Erststart wird ein Backup eingespielt und der
Wiederherstellungscode falsch eingegeben. Bleibt dabei ein nicht öffenbares
Quick-Konto in data/ zurück, beendete sich die App bisher hart (return 1) und
man kam erst wieder hinein, NACHDEM man den data-Ordner manuell geleert hatte.

Diese Tests sichern zwei Dinge ab:
  1. Datenschicht: Das Entfernen eines (defekten) Quick-Kontos inkl. seiner
     .enc-Datei macht data/ wieder sauber – ``has_users()`` ist anschließend
     False, der nächste Start zeigt also wieder die Ersteinrichtung.
  2. Startfluss (Quelltext-Verankerung): main.py beendet sich bei einem nicht
     öffenbaren Konto nicht mehr bedingungslos, sondern bietet Selbstheilung an
     (``_recover_broken_account`` in einer wiederholbaren Schleife).

Läuft ohne Qt/PySide6 (UserModel und crypto sind Qt-frei).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_removing_broken_quick_account_clears_data_dir(monkeypatch):
    app_dir = tempfile.mkdtemp(prefix="bm_recovery_")
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", app_dir)

    # Importe erst NACH dem Setzen der Env, damit data_dir() korrekt auflöst.
    from model.user_model import UserModel, SECURITY_QUICK, data_dir
    from model.crypto import decrypt_db_from_file

    um = UserModel()
    user, _ = um.create_user("Feld Quick", SECURITY_QUICK, "")
    enc = user.db_path
    key = user.get_db_key("")
    assert enc.exists()

    # Konto "kaputt machen": .enc mit Müll überschreiben (simuliert verwaisten/
    # unvollständigen Restore-Rest).
    enc.write_bytes(b"not a valid fernet enc file")
    try:
        decrypt_db_from_file(enc, key)
        raised = False
    except Exception:
        raised = True
    assert raised, "Defekte .enc muss beim Öffnen einen Fehler werfen"

    # Selbstheilung = defektes Konto inkl. DB entfernen.
    ok = um.delete_user(user.username, delete_db=True)
    assert ok
    assert not enc.exists(), "Verwaiste .enc muss entfernt sein"

    # Nächster Start: keine Benutzer mehr -> Ersteinrichtung statt Lockout.
    um2 = UserModel()
    assert um2.has_users() is False


def _main_src() -> str:
    return (ROOT / "main.py").read_text(encoding="utf-8")


def test_startup_offers_recovery_instead_of_hard_exit():
    src = _main_src()
    assert "def _recover_broken_account(" in src, "Selbstheilungs-Helfer fehlt"
    assert 'tr("startup.recover_title")' in src
    assert "startup.recover_question" in src
    # Wiederholbarkeit: Benutzerauflösung steckt in einer Schleife, damit nach der
    # Selbstheilung erneut die Ersteinrichtung greifen kann.
    assert "while True:" in src


def test_recover_helper_deletes_user_and_db():
    src = _main_src()
    helper = src.split("def _recover_broken_account(", 1)[1].split("\n        while True:", 1)[0]
    assert "delete_user(" in helper
    assert "delete_db=True" in helper
    # Letzter Ausweg, falls der reguläre Löschweg scheitert: .enc direkt entfernen.
    assert ".db_path.unlink()" in helper


def test_recover_question_key_present_in_all_locales():
    for loc in ("de", "en", "fr"):
        data = json.loads((ROOT / "locales" / f"{loc}.json").read_text(encoding="utf-8"))
        startup = data.get("startup", {})
        for key in ("recover_title", "recover_question"):
            assert startup.get(key) and startup[key].strip(), f"{loc}: startup.{key} fehlt/leer"
        assert "{reason}" in startup["recover_question"], f"{loc}: Platzhalter {{reason}} fehlt"
