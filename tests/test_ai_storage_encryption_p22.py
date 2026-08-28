"""P2.2 - Wo der KI-Lernspeicher wirklich liegt und wer ihn lesen kann.

P2.1 hat den Lernspeicher schaltbar und loeschbar gemacht. Diese Datei
beantwortet die andere Haelfte: Ist das, was die KI ueber den Benutzer
angesammelt hat, auf der Platte tatsaechlich geschuetzt?

Geprueft wird die Architektur, nicht ihre Beschreibung. Die Tests legen
darum echte KI-Lerndaten an, speichern verschluesselt und durchsuchen
anschliessend *jede* entstandene Datei nach dem Klartext. Ein Test, der nur
``encrypt_bytes`` aufgerufen sieht, wuerde eine vergessene Debug-Kopie
daneben nie bemerken.

**Der unbequeme Befund, den diese Datei festhaelt.** Im Schnellzugang
(``quick``) liegt der db_key base64-kodiert in ``users.json`` - und
``users.json`` wandert in jede Sicherung. Ein .bmr eines Quick-Kontos traegt
damit Schloss und Schluessel nebeneinander: Wer die Datei hat, liest die
Lerndaten im Klartext, auch auf einem fremden Rechner.

Das ist kein Versehen, sondern der Preis des Modus - ohne den Schluessel
waere die Sicherung nach einem Plattentausch wertlos. Verboten ist nach
Architekturregel 1.6 aber, das *zu verschweigen*. Genau deshalb steht hier
neben dem technischen Nachweis auch ein Test auf den Anzeigetext: Er faellt,
sobald jemand die Sicherung wieder aus der Warnung streicht.

Eine zweite verschluesselte KI-Datei loest das ausdruecklich **nicht** und
ist nach Architekturregel 1.5 untersagt - sie verloere Backup, Restore und
die atomaren Transaktionen der Benutzer-Datenbank.
"""

from __future__ import annotations

import base64
import json
import os
import sqlite3
import zipfile
from pathlib import Path

from model.bank_import_ai import BankImportAI
from model.crypto import (
    create_empty_encrypted_db,
    decrypt_db_from_file,
    generate_db_key,
    generate_salt,
    save_memory_db,
    wrap_db_key,
)
from model.restore_bundle import create_bundle

ROOT = Path(__file__).resolve().parents[1]

#: Ein Buchungstext, wie ihn ``ai_feedback.raw_text`` speichert. Er ist
#: absichtlich unverwechselbar: Danach wird byteweise auf der Platte gesucht.
GEHEIMER_TEXT = "MIGROS ZUERICH GEHEIMER EINKAUF 4711"


def _konto_mit_lerndaten(ordner: Path) -> tuple[Path, bytes, bytes]:
    """Legt eine verschluesselte Benutzer-DB mit echten KI-Lerndaten an."""
    db_key = generate_db_key()
    salt = generate_salt()
    enc = ordner / "christian.enc"
    conn = create_empty_encrypted_db(enc, db_key, salt)
    try:
        BankImportAI(conn)  # legt die ai_*-Tabellen an
        conn.execute(
            "INSERT INTO ai_merchant_memory "
            "(fingerprint, typ, category, tags_json, confirmations, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            ("fp-migros", "Ausgaben", "Lebensmittel", "[]", 3, "2026-08-28"),
        )
        conn.execute(
            "INSERT INTO ai_feedback "
            "(fingerprint, typ, raw_text, category, tags_json, tokens_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "fp-migros",
                "Ausgaben",
                GEHEIMER_TEXT,
                "Lebensmittel",
                "[]",
                "[]",
                "2026-08-28",
            ),
        )
        conn.commit()
        save_memory_db(conn, enc, db_key, salt)
    finally:
        conn.close()
    return enc, db_key, salt


def _dateien_mit_klartext(ordner: Path, nadel: str) -> list[str]:
    """Namen aller Dateien unter ``ordner``, die ``nadel`` im Rohbyte tragen."""
    roh = nadel.encode("utf-8")
    treffer = []
    for pfad in ordner.rglob("*"):
        if pfad.is_file() and roh in pfad.read_bytes():
            treffer.append(pfad.name)
    return sorted(treffer)


# ── Die Architektur selbst ────────────────────────────────────────────


def test_ki_lerndaten_liegen_in_der_verschluesselten_benutzer_db(tmp_path):
    """Die ai_*-Tabellen sind Teil der .enc - und nur dort lesbar."""
    enc, db_key, _salt = _konto_mit_lerndaten(tmp_path)

    # Es entsteht genau eine Datei: die verschluesselte Benutzer-Datenbank.
    dateien = sorted(p.name for p in tmp_path.iterdir())
    assert dateien == ["christian.enc"], dateien

    # Mit Schluessel sind die Lerndaten da ...
    conn = decrypt_db_from_file(enc, db_key)
    try:
        gespeichert = conn.execute("SELECT raw_text FROM ai_feedback").fetchone()[0]
        assert gespeichert == GEHEIMER_TEXT
    finally:
        conn.close()

    # ... ohne Schluessel steht der Text nirgends auf der Platte.
    assert _dateien_mit_klartext(tmp_path, GEHEIMER_TEXT) == []


def test_speichern_hinterlaesst_keine_klartext_zwischendatei(tmp_path):
    """Auch der Schreibweg selbst darf nichts Lesbares liegen lassen.

    ``encrypt_db_to_file`` schreibt ueber eine ``.tmp``-Datei. Entscheidend
    ist, dass darin bereits der Fernet-Token steht und nicht der SQL-Dump -
    und dass sie danach verschwindet.
    """
    enc, db_key, salt = _konto_mit_lerndaten(tmp_path)

    conn = decrypt_db_from_file(enc, db_key)
    try:
        conn.execute(
            "INSERT INTO ai_feedback "
            "(fingerprint, typ, raw_text, category, tags_json, tokens_json, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "fp-2",
                "Ausgaben",
                GEHEIMER_TEXT,
                "Lebensmittel",
                "[]",
                "[]",
                "2026-08-28",
            ),
        )
        conn.commit()
        save_memory_db(conn, enc, db_key, salt)
    finally:
        conn.close()

    assert list(tmp_path.glob("*.tmp")) == []
    assert _dateien_mit_klartext(tmp_path, GEHEIMER_TEXT) == []


def test_keine_zweite_verschluesselungsarchitektur_fuer_die_ki():
    """Architekturregel 1.5: Die KI baut sich keine eigene Datei.

    Geprueft wird die Quelle statt eines Laufzeiteffekts: Ein eigener
    ``sqlite3.connect`` in einem KI-Modul waere genau der Einstieg in einen
    zweiten Speicher - mit eigener Verschluesselung, ohne Backup und ohne die
    Transaktionsklammer der Benutzer-Datenbank.
    """
    for modul in (
        "model/bank_import_ai.py",
        "model/twint_import_policy.py",
        "model/ai_learning_store.py",
        "model/bank_import_snapshot.py",
    ):
        quelle = (ROOT / modul).read_text(encoding="utf-8")
        assert "sqlite3.connect" not in quelle, modul
        assert "ai_container" not in quelle, modul


# ── Die Sicherung ─────────────────────────────────────────────────────


def test_quick_sicherung_enthaelt_den_schluessel_neben_den_daten(tmp_path):
    """Belegt den Befund, den der Anzeigetext benennen muss.

    Faellt dieser Test, weil der Schluessel nicht mehr mitwandert, ist das
    eine gute Nachricht - dann gehoert allerdings der Warntext angepasst und
    der Restore-Weg fuer Quick-Konten neu belegt.
    """
    enc, db_key, salt = _konto_mit_lerndaten(tmp_path)
    users = {
        "users": [
            {
                "username": "christian",
                "db_filename": "christian.enc",
                "security": "quick",
                "db_key_b64": db_key.decode("ascii"),
                "salt": salt.hex(),
            }
        ]
    }
    users_json = tmp_path / "users.json"
    users_json.write_text(json.dumps(users), encoding="utf-8")

    bundle = create_bundle(
        source_db=enc,
        out_path=tmp_path / "sicherung.bmr",
        app="BudgetManager",
        app_version="3.1.1",
        users_json_path=users_json,
    )

    with zipfile.ZipFile(bundle) as zf:
        eintrag = json.loads(zf.read("users.json"))["users"][0]
        mitgereister_key = eintrag.get("db_key_b64", "")
        assert mitgereister_key.encode("ascii") == db_key

        # Der Vollbeweis: allein aus dem Bundle, ohne den Rechner des
        # Benutzers, sind die Lerndaten im Klartext lesbar.
        kopie = tmp_path / "aus_bundle.enc"
        kopie.write_bytes(zf.read("database.enc"))

    conn = decrypt_db_from_file(kopie, mitgereister_key.encode("ascii"))
    try:
        gelesen = conn.execute("SELECT raw_text FROM ai_feedback").fetchone()[0]
    finally:
        conn.close()
    assert gelesen == GEHEIMER_TEXT


def test_pin_sicherung_gibt_den_schluessel_nicht_preis(tmp_path):
    """Die Gegenprobe: Mit PIN traegt die Sicherung nur den gewrappten Key."""
    enc, db_key, salt = _konto_mit_lerndaten(tmp_path)
    wrapped = wrap_db_key(db_key, "meine-pin-1234", salt)
    users = {
        "users": [
            {
                "username": "anna",
                "db_filename": "christian.enc",
                "security": "pin",
                "wrapped_db_key_b64": base64.urlsafe_b64encode(wrapped).decode("ascii"),
                "salt": salt.hex(),
            }
        ]
    }
    users_json = tmp_path / "users.json"
    users_json.write_text(json.dumps(users), encoding="utf-8")

    bundle = create_bundle(
        source_db=enc,
        out_path=tmp_path / "sicherung.bmr",
        app="BudgetManager",
        app_version="3.1.1",
        users_json_path=users_json,
    )

    with zipfile.ZipFile(bundle) as zf:
        roh = zf.read("users.json")
        eintrag = json.loads(roh)["users"][0]

    assert not eintrag.get("db_key_b64")
    assert eintrag.get("wrapped_db_key_b64")
    # Der echte Schluessel taucht auch sonst nirgends im Bundle auf.
    assert db_key not in roh
    assert db_key not in (tmp_path / "sicherung.bmr").read_bytes()


# ── Die Darstellung ───────────────────────────────────────────────────


def test_quick_warnung_benennt_auch_die_sicherung():
    """Architekturregel 1.6 in Textform - in allen drei Sprachen.

    Der Text sagte bis P2.2 nur, der Schluessel liege "auf diesem Rechner".
    Das stimmte, war aber die harmlosere Haelfte: Ueber jede Sicherung
    verlaesst er den Rechner. Diese Zusicherung faellt, sobald der Hinweis
    wieder verschwindet.
    """
    erwartete_woerter = {
        "de": ("Sicherung",),
        "en": ("backup",),
        "fr": ("sauvegarde",),
    }
    for sprache, woerter in erwartete_woerter.items():
        daten = json.loads(
            (ROOT / "locales" / f"{sprache}.json").read_text(encoding="utf-8")
        )
        text = daten["ai_settings"]["security_quick"]
        for wort in woerter:
            assert wort.lower() in text.lower(), (sprache, text)


def test_geschuetzte_modi_versprechen_keine_sicherung_die_es_nicht_gibt():
    """PIN/Passwort duerfen den Schluessel als geschuetzt bezeichnen - Quick nicht."""
    daten = json.loads((ROOT / "locales" / "de.json").read_text(encoding="utf-8"))
    ai = daten["ai_settings"]
    assert "Passwort" in ai["security_secret"] or "PIN" in ai["security_secret"]
    # Der Quick-Text darf sich nie zu einer Entwarnung entwickeln.
    assert "maximal" not in ai["security_quick"].lower()


def test_sqlite_connection_bleibt_die_der_benutzer_db():
    """BankImportAI nimmt die uebergebene Verbindung - und oeffnet keine eigene."""
    conn = sqlite3.connect(":memory:")
    try:
        ai = BankImportAI(conn)
        assert ai.conn is conn
        tabellen = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert {"ai_merchant_memory", "ai_feedback", "ai_tag_rules"} <= tabellen
    finally:
        conn.close()
    assert not os.path.exists("ai_container.enc")
