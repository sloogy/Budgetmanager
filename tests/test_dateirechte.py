"""Persoenliche Daten liegen nicht offen auf der Platte.

BudgetManager hatte diesen Schutz als einziges Programm der Suite und war
darum die Vorlage: model/file_permissions.py entstand aus der
Sicherheitsanalyse zu v2.2.11, weil in users.json der Schluessel zur
verschluesselten Datenbank im Klartext steht.

Alle vier Programme der Suite fuehren diesen Test jetzt unter demselben Namen.
"""

from __future__ import annotations

import os
import stat

import pytest

from model.file_permissions import (
    OWNER_ONLY_DIR,
    OWNER_ONLY_FILE,
    is_world_accessible,
    secure_dir,
    secure_file,
)

posix_only = pytest.mark.skipif(
    os.name == "nt", reason="Windows kennt keine POSIX-Modi; dort greifen ACLs"
)


@posix_only
def test_secure_file_nimmt_gruppe_und_anderen_die_rechte(tmp_path):
    pfad = tmp_path / "users.json"
    pfad.write_text("{}", encoding="utf-8")
    os.chmod(pfad, 0o644)
    assert is_world_accessible(pfad)

    assert secure_file(pfad) is True
    assert stat.S_IMODE(pfad.stat().st_mode) == OWNER_ONLY_FILE
    assert not is_world_accessible(pfad)


@posix_only
def test_secure_dir_schliesst_den_ordner(tmp_path):
    ordner = tmp_path / "daten"
    ordner.mkdir(mode=0o755)
    assert secure_dir(ordner) is True
    assert stat.S_IMODE(ordner.stat().st_mode) == OWNER_ONLY_DIR


def test_eine_fehlende_datei_ist_kein_fehler(tmp_path):
    """Ein Backup auf einem FAT-Stick darf nicht am chmod scheitern."""
    assert secure_file(tmp_path / "gibtsnicht") is False


def test_der_inhalt_bleibt_lesbar(tmp_path):
    pfad = tmp_path / "datei.txt"
    pfad.write_text("inhalt", encoding="utf-8")
    secure_file(pfad)
    assert pfad.read_text(encoding="utf-8") == "inhalt"


# ── Die Bruecke zu FPM ──────────────────────────────────────────────────────


@posix_only
def test_der_brueckenordner_ist_geschlossen(tmp_path, monkeypatch):
    """Eigenstaendig liegt er offen im Benutzerverzeichnis. Was darin steht,
    sind Buchungen und Sparziele."""
    from pathlib import Path

    from model import lifeplanner_import_service as bridge

    monkeypatch.delenv("LIFEPLANNER_BRIDGE_DIR", raising=False)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))

    ordner = bridge.default_bridge_dir()

    assert ordner.is_dir()
    assert stat.S_IMODE(ordner.stat().st_mode) == OWNER_ONLY_DIR


@posix_only
def test_die_sparziel_datei_gehoert_nur_dem_eigentuemer(tmp_path):
    import sqlite3

    from model.lifeplanner_import_service import export_savings_goals
    from model.migrations import migrate_all

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)

    ergebnis = export_savings_goals(conn, tmp_path / "sparziele.jsonl")

    assert stat.S_IMODE(ergebnis.path.stat().st_mode) == OWNER_ONLY_FILE
    assert not is_world_accessible(ergebnis.path)
