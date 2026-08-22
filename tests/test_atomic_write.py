"""Schreiben, das einen Stromausfall uebersteht.

Loop 13 raeumte kaputte Einstellungsdateien auf, Loop 21 fand denselben Fall
in FPM noch einmal. Loop 27 geht an die Ursache: Wer eine Datei an Ort und
Stelle ueberschreibt, hinterlaesst bei einem Absturz die halbe.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


@pytest.fixture()
def schreiber():
    treffer = [
        p for p in sorted(WURZEL.rglob("atomic_write.py"))
        if "test" not in p.parts and "build" not in p.parts
    ]
    assert treffer, "atomic_write.py fehlt"
    spec = importlib.util.spec_from_file_location("atomic_write", treffer[0])
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def test_der_inhalt_kommt_an(schreiber, tmp_path: Path) -> None:
    ziel = tmp_path / "einstellungen.json"
    schreiber.atomar_schreiben(ziel, '{"a": 1}')
    assert json.loads(ziel.read_text(encoding="utf-8")) == {"a": 1}


def test_keine_zwischendatei_bleibt_liegen(schreiber, tmp_path: Path) -> None:
    schreiber.atomar_schreiben(tmp_path / "x.json", "{}")
    assert not list(tmp_path.glob("*.tmp*"))


def test_fehlende_ordner_entstehen(schreiber, tmp_path: Path) -> None:
    ziel = tmp_path / "tief" / "drin" / "x.json"
    schreiber.atomar_schreiben(ziel, "{}")
    assert ziel.is_file()


@pytest.mark.skipif(os.name != "posix", reason="POSIX-Modi")
def test_die_datei_ist_nur_fuer_den_besitzer_lesbar(schreiber, tmp_path: Path) -> None:
    """0600 wird auf der Zwischendatei gesetzt, vor dem Umbenennen.

    Danach waere die Datei fuer einen Augenblick mit dem Standard-umask
    sichtbar - und genau in dem Augenblick steht sie offen.
    """
    ziel = tmp_path / "geheim.json"
    schreiber.atomar_schreiben(ziel, "{}")
    assert ziel.stat().st_mode & 0o777 == 0o600


def test_der_alte_stand_bleibt_wenn_das_umbenennen_scheitert(
    schreiber, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ziel = tmp_path / "x.json"
    schreiber.atomar_schreiben(ziel, '{"stand": "alt"}')

    def bricht_ab(*args, **kwargs):
        raise OSError("Kein Platz")

    monkeypatch.setattr(schreiber.os, "replace", bricht_ab)
    with pytest.raises(OSError):
        schreiber.atomar_schreiben(ziel, '{"stand": "neu"}')

    assert json.loads(ziel.read_text(encoding="utf-8")) == {"stand": "alt"}
    assert not list(tmp_path.glob("*.tmp*")), "die halbe Datei muss weg sein"


def test_ein_abbruch_laesst_nichts_liegen(
    schreiber, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch Strg-C ist keine Ausnahme, die sich mit ``except`` fangen liesse."""
    ziel = tmp_path / "x.json"

    def bricht_ab(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(schreiber.os, "replace", bricht_ab)
    with pytest.raises(KeyboardInterrupt):
        schreiber.atomar_schreiben(ziel, "{}")

    assert not list(tmp_path.glob("*.tmp*"))
    assert not ziel.exists()


def test_zwei_prozesse_teilen_sich_keine_zwischendatei(schreiber, tmp_path: Path) -> None:
    """Die Instanzsperre aus Loop 14 deckt nur denselben Datenordner ab."""
    gesehen = []
    echtes_replace = schreiber.os.replace

    def merke(quelle, ziel):
        gesehen.append(Path(quelle).name)
        echtes_replace(quelle, ziel)

    schreiber.os.replace = merke
    try:
        schreiber.atomar_schreiben(tmp_path / "x.json", "{}")
    finally:
        schreiber.os.replace = echtes_replace
    assert str(os.getpid()) in gesehen[0]


def test_stueckweise_geschrieben_wird_erst_am_ende_sichtbar(
    schreiber, tmp_path: Path
) -> None:
    """Fuer Brueckendateien, in denen jede Zeile ein Datensatz ist."""
    ziel = tmp_path / "outbox.jsonl"
    with schreiber.atomar_offen(ziel) as datei:
        datei.write('{"a": 1}\n')
        assert not ziel.exists(), "vor dem Ende darf die Datei nicht da sein"
        datei.write('{"a": 2}\n')
    assert ziel.read_text(encoding="utf-8").splitlines() == ['{"a": 1}', '{"a": 2}']


def test_ein_abbruch_mittendrin_laesst_den_alten_stand_stehen(
    schreiber, tmp_path: Path
) -> None:
    """Sonst laege dort eine Datei mit abgeschnittener letzter Zeile - vom
    Empfaenger nicht von einer vollstaendigen zu unterscheiden."""
    ziel = tmp_path / "outbox.jsonl"
    schreiber.atomar_schreiben(ziel, '{"stand": "alt"}\n')

    with pytest.raises(ValueError):
        with schreiber.atomar_offen(ziel) as datei:
            datei.write('{"halb": ')
            raise ValueError("Abbruch")

    assert ziel.read_text(encoding="utf-8") == '{"stand": "alt"}\n'
    assert not list(tmp_path.glob("*.tmp*"))
