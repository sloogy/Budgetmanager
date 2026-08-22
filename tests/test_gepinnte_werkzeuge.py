"""Die Pruefwerkzeuge gehoeren zum Projekt, nicht zum Entwicklerrechner.

Am 22. August 2026 machte eine lokal formatierte Datei die Push-Gates rot:
black formatiert von Nebenversion zu Nebenversion unterschiedlich, die CI
nahm 25.1.0 aus requirements-dev.txt, der Rechner hatte 26.5.1. Der Code war
nicht falsch - nur mit dem falschen Werkzeug angefasst.

Diese Tests halten fest, dass die Versionen exakt gepinnt bleiben und dass
tools/gepinnte_werkzeuge.py sie findet. Ausgefuehrt wird black damit ueber
das Skript, nicht ueber das, was gerade im PATH liegt.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from tools.gepinnte_werkzeuge import gepinnte_version

ROOT = Path(__file__).resolve().parents[1]

# Werkzeuge, deren Urteil einen CI-Lauf rot macht. Fuer Laufzeitabhaengigkeiten
# ist ein Bereich richtig; hier waere er ein Gate, das sich selbst rot macht.
GATE_WERKZEUGE = ("black", "ruff", "mypy")

_ZEILE = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)\s*(?P<rest>[^\s;#]*)")


@pytest.mark.parametrize("werkzeug", GATE_WERKZEUGE)
def test_gate_werkzeuge_sind_exakt_gepinnt(werkzeug: str) -> None:
    gesehen = False
    for datei in sorted(ROOT.glob("requirements*.txt")) + sorted(ROOT.glob("requirements*.in")):
        for rohzeile in datei.read_text(encoding="utf-8").splitlines():
            zeile = rohzeile.split("#", 1)[0].strip()
            treffer = _ZEILE.match(zeile)
            if not treffer or treffer.group("name").lower() != werkzeug:
                continue
            gesehen = True
            rest = treffer.group("rest")
            assert rest.startswith("=="), (
                f"{datei.name}: {werkzeug}{rest} ist ein Bereich. Eine neue "
                "Nebenversion macht das Gate rot, ohne dass sich Code geaendert hat."
            )
    assert gesehen, f"{werkzeug} steht in keiner requirements-Datei"


@pytest.mark.parametrize("werkzeug", GATE_WERKZEUGE)
def test_wrapper_findet_die_pinnung(werkzeug: str) -> None:
    version = gepinnte_version(werkzeug)
    assert re.fullmatch(r"\d+(\.\d+)*", version), f"unerwartete Version: {version!r}"


def test_pinnungen_sind_ueber_alle_dateien_gleich() -> None:
    """requirements-dev.in, .txt und .lock duerfen nicht auseinanderlaufen.

    Sonst installiert die CI eine andere Version als die, die hier steht -
    und der Lockfile-Check faellt erst auf, wenn das Release schon haengt.
    """
    for werkzeug in GATE_WERKZEUGE:
        versionen = set()
        for datei in sorted(ROOT.glob("requirements*")):
            for rohzeile in datei.read_text(encoding="utf-8").splitlines():
                zeile = rohzeile.split("#", 1)[0].strip().rstrip("\\").strip()
                treffer = re.fullmatch(rf"{werkzeug}==([^\s;]+)", zeile)
                if treffer:
                    versionen.add(treffer.group(1))
        assert len(versionen) <= 1, f"{werkzeug} ist uneinheitlich gepinnt: {sorted(versionen)}"
