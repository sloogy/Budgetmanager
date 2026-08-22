"""Das Bruecken-Register: mehrere Startarten, eine Bruecke.

Der Fall, den diese Tests festhalten: Wer FPM oder den BudgetManager mal
eigenstaendig und mal im LifePlanner startet, hat zwei getrennte Ordner.
Geschrieben wird weiterhin nur in den aktiven - gelesen aus allen.

Wortgleich in FPM, BudgetManager und LifePlanner.
"""

from __future__ import annotations

import json
import stat
import sys

import pytest

from model.bridge_registry import MAX_ORDNER, bekannte_ordner, eintragen, register_pfad


@pytest.fixture
def register(tmp_path, monkeypatch):
    ziel = tmp_path / "konfig" / "bridges.json"
    monkeypatch.setenv("FPM_SUITE_BRIDGE_REGISTRY", str(ziel))
    return ziel


def test_ein_eingetragener_ordner_taucht_beim_naechsten_start_auf(tmp_path, register):
    """Der Kern: Was der Host benutzt hat, findet der eigenstaendige Start."""
    host = tmp_path / "profil" / "bridge"
    host.mkdir(parents=True)
    allein = tmp_path / "fpm_budgetmanager_bridge"
    allein.mkdir()

    eintragen(host)

    assert bekannte_ordner(allein) == (host, allein)


def test_der_aktive_ordner_kommt_zuletzt(tmp_path, register):
    """Reihenfolge ist Vorrang: Der Aufrufer liest der Reihe nach ein, der
    letzte Stand gewinnt. Das muss der Ordner sein, der gerade gilt."""
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    eintragen(a)
    eintragen(b)

    assert bekannte_ordner(a)[-1] == a
    assert bekannte_ordner(b)[-1] == b


def test_derselbe_ordner_steht_nur_einmal_drin(tmp_path, register):
    ordner = tmp_path / "bridge"
    ordner.mkdir()
    eintragen(ordner)
    eintragen(ordner)

    assert bekannte_ordner(ordner) == (ordner,)


def test_ein_geloeschtes_profil_faellt_still_heraus(tmp_path, register):
    """Ein geloeschtes Profil soll keine Fehlermeldung erzeugen - der Ordner
    ist einfach weg, und die Bruecke laeuft weiter."""
    weg = tmp_path / "weg"
    weg.mkdir()
    aktiv = tmp_path / "aktiv"
    aktiv.mkdir()
    eintragen(weg)
    weg.rmdir()

    assert bekannte_ordner(aktiv) == (aktiv,)


def test_ein_kaputtes_register_haelt_die_bruecke_nicht_auf(tmp_path, register):
    """Das Register ist ein Verzeichnis von Ordnern, keine Datenquelle. Ist es
    unlesbar, bleibt der aktive Ordner - also genau der Stand von vorher."""
    register.parent.mkdir(parents=True, exist_ok=True)
    register.write_text("{kein json", encoding="utf-8")
    aktiv = tmp_path / "aktiv"
    aktiv.mkdir()

    assert bekannte_ordner(aktiv) == (aktiv,)


@pytest.mark.skipif(
    sys.platform.startswith("win"),
    reason="Windows kennt keine POSIX-Bits; os.chmod setzt dort nur den "
    "Schreibschutz. Der Schutz des Registers ist dort Sache der ACLs des "
    "Benutzerprofils - dieser Test wuerde 0o666 sehen und nichts aussagen.",
)
def test_das_register_liegt_nicht_offen(tmp_path, register):
    """Es enthaelt nur Pfade - aber die verraten Profilnamen und die
    Ordnerstruktur des Nutzers."""
    ordner = tmp_path / "bridge"
    ordner.mkdir()
    eintragen(ordner)

    assert register.is_file()
    assert stat.S_IMODE(register.stat().st_mode) == 0o600
    assert stat.S_IMODE(register.parent.stat().st_mode) == 0o700


def test_das_register_waechst_nicht_unbegrenzt(tmp_path, register):
    """Eine kaputt geschriebene Datei soll den Speicher nicht auffressen."""
    for i in range(MAX_ORDNER + 5):
        ordner = tmp_path / f"b{i}"
        ordner.mkdir()
        eintragen(ordner)

    daten = json.loads(register.read_text(encoding="utf-8"))
    assert len(daten["ordner"]) <= MAX_ORDNER


def test_der_pfad_folgt_der_umgebung(tmp_path, monkeypatch):
    """Ohne die Weiche schreiben Tests und ein Betrieb mit getrennten
    Benutzerdaten in dieselbe Datei."""
    monkeypatch.delenv("FPM_SUITE_BRIDGE_REGISTRY", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "cfg"))

    assert register_pfad() == tmp_path / "cfg" / "fpm-suite" / "bridges.json"
