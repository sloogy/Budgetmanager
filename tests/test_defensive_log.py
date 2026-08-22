"""Der Melder fuer bewusst verschluckte Fehler drosselt, aber schweigt nicht.

Vor Loop 21 stand an diesen Stellen ``except Exception: pass``. Der Ablauf
stimmte, die Spur fehlte. Der Melder loest beides: Er haelt nichts auf und
meldet trotzdem - gedrosselt, weil die Stellen in Schleifen ueber viele
Objekte liegen.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""
from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]


def _modulpfad() -> Path:
    treffer = sorted(WURZEL.rglob("defensive_log.py"))
    treffer = [p for p in treffer if "test" not in p.parts and "build" not in p.parts]
    assert treffer, "defensive_log.py fehlt"
    return treffer[0]


@pytest.fixture()
def melder():
    spec = importlib.util.spec_from_file_location("defensive_log", _modulpfad())
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    modul.zuruecksetzen()
    return modul


def test_der_erste_fehler_wird_gemeldet(melder, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        melder.uebersprungen("Uebersetzungslauf", RuntimeError("Objekt weg"))
    assert "Uebersetzungslauf" in caplog.text
    assert "Objekt weg" in caplog.text


def test_dieselbe_ursache_wird_nur_einmal_gemeldet(melder, caplog) -> None:
    """Sonst flutet ein Lauf ueber hunderte Widgets das Log."""
    with caplog.at_level(logging.DEBUG):
        for _ in range(50):
            melder.uebersprungen("Uebersetzungslauf", RuntimeError("Objekt weg"))
    assert caplog.text.count("Uebersetzungslauf") == 1


def test_eine_andere_fehlerart_wird_wieder_gemeldet(melder, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        melder.uebersprungen("Uebersetzungslauf", RuntimeError("weg"))
        melder.uebersprungen("Uebersetzungslauf", AttributeError("fehlt"))
    assert caplog.text.count("Uebersetzungslauf") == 2


def test_eine_andere_stelle_wird_wieder_gemeldet(melder, caplog) -> None:
    with caplog.at_level(logging.DEBUG):
        melder.uebersprungen("Uebersetzungslauf", RuntimeError("weg"))
        melder.uebersprungen("Kontextmenue", RuntimeError("weg"))
    assert "Uebersetzungslauf" in caplog.text
    assert "Kontextmenue" in caplog.text


def test_die_stufe_laesst_sich_anheben(melder, caplog) -> None:
    """Wo ein Fehlschlag Folgen hat, soll er auffallen."""
    with caplog.at_level(logging.WARNING):
        melder.uebersprungen("Dateirechte", OSError("nur lesbar"), stufe=logging.WARNING)
    assert "Dateirechte" in caplog.text


def test_der_melder_reicht_nie_etwas_weiter(melder) -> None:
    """Das ist sein ganzer Zweck: Er darf den Ablauf nicht aufhalten."""
    melder.uebersprungen("Irgendwo", KeyboardInterrupt())
