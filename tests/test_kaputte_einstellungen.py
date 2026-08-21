"""Eine unlesbare Einstellungsdatei wird gerettet, nicht ueberschrieben.

Bisher wurde der Fehler zwar protokolliert, die Datei aber beim naechsten
Speichern ueberschrieben - samt Datenpfad, Regionseinstellungen und
Cockpit-Aufteilung. Oft ist nur ein Zeichen falsch und sie liesse sich von
Hand retten; dafuer muss sie aber noch da sein.

Alle betroffenen Programme der Suite fuehren diesen Test unter demselben Namen.
"""

from __future__ import annotations

import json

import pytest

from settings import Settings


def _settings(pfad):
    s = Settings.__new__(Settings)
    s.settings_file = pfad
    return s


@pytest.mark.parametrize(
    "inhalt,beschreibung",
    [
        ("{nicht json", "abgeschnittenes JSON"),
        ("", "leere Datei"),
        ('{"currency": "CHF"', "fehlende Klammer"),
    ],
)
def test_eine_kaputte_datei_wird_beiseitegelegt(tmp_path, inhalt, beschreibung):
    pfad = tmp_path / "budgetmanager_settings.json"
    pfad.write_text(inhalt, encoding="utf-8")

    daten = _settings(pfad)._load()

    # Das Programm laeuft weiter, mit Standardwerten.
    assert isinstance(daten, dict) and daten, beschreibung
    # Und der alte Inhalt ist noch da.
    gerettet = list(tmp_path.glob("budgetmanager_settings.json.kaputt-*"))
    assert len(gerettet) == 1, beschreibung
    assert gerettet[0].read_text(encoding="utf-8") == inhalt


def test_eine_gueltige_datei_bleibt_unangetastet(tmp_path):
    pfad = tmp_path / "budgetmanager_settings.json"
    pfad.write_text(json.dumps({"currency": "EUR"}), encoding="utf-8")

    daten = _settings(pfad)._load()

    assert daten["currency"] == "EUR"
    assert not list(tmp_path.glob("*.kaputt-*"))


def test_eine_fehlende_datei_ist_kein_fehler(tmp_path):
    """Der erste Start - da gibt es noch nichts zu retten."""
    daten = _settings(tmp_path / "budgetmanager_settings.json")._load()
    assert isinstance(daten, dict) and daten
    assert not list(tmp_path.glob("*.kaputt-*"))
