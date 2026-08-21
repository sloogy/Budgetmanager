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
