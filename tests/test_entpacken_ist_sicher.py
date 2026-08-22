"""Ein Update-Archiv darf beim Entpacken nichts anrichten.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
BudgetManager hatte den vollstaendigsten Schutz - er ist hier die Vorlage.
"""

from __future__ import annotations

import zipfile

import pytest

from updater.common import (
    MAX_UPDATE_COMPRESSION_RATIO,
    MAX_UPDATE_FILES,
    MAX_UPDATE_MEMBER_BYTES,
    safe_extract_zip,
)


def _archiv(pfad, eintraege: dict[str, bytes]):
    with zipfile.ZipFile(pfad, "w", zipfile.ZIP_DEFLATED) as z:
        for name, inhalt in eintraege.items():
            z.writestr(name, inhalt)
    return pfad


def test_ein_harmloses_archiv_wird_entpackt(tmp_path):
    quelle = _archiv(tmp_path / "gut.zip", {"a.txt": b"x", "unter/b.txt": b"y"})
    ziel = tmp_path / "ziel"
    safe_extract_zip(quelle, ziel)
    assert (ziel / "unter" / "b.txt").read_bytes() == b"y"


@pytest.mark.parametrize(
    "name", ["../ausbruch.txt", "unter/../../ausbruch.txt", "/absolut.txt"]
)
def test_pfad_traversal_wird_abgewiesen(tmp_path, name):
    quelle = _archiv(tmp_path / "boese.zip", {name: b"x"})
    with pytest.raises(ValueError):
        safe_extract_zip(quelle, tmp_path / "ziel")
    assert not (tmp_path / "ausbruch.txt").exists()


def test_ein_symlink_wird_abgewiesen(tmp_path):
    quelle = tmp_path / "link.zip"
    with zipfile.ZipFile(quelle, "w") as z:
        eintrag = zipfile.ZipInfo("link")
        eintrag.external_attr = 0o120777 << 16
        z.writestr(eintrag, "/etc/passwd")
    with pytest.raises(ValueError):
        safe_extract_zip(quelle, tmp_path / "ziel")


def test_eine_zip_bombe_wird_abgewiesen(tmp_path):
    quelle = tmp_path / "bombe.zip"
    with zipfile.ZipFile(quelle, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.writestr("gross.bin", b"\0" * (MAX_UPDATE_COMPRESSION_RATIO * 4096))
    with pytest.raises(ValueError, match="Kompressionsrate"):
        safe_extract_zip(quelle, tmp_path / "ziel")


def test_die_grenzen_sind_gesetzt():
    assert MAX_UPDATE_FILES > 0
    assert MAX_UPDATE_MEMBER_BYTES > 0
    assert MAX_UPDATE_COMPRESSION_RATIO > 1
