#!/usr/bin/env python3
"""Fuehrt ein Pruefwerkzeug in genau der Version aus, die das Projekt pinnt.

Warum es das gibt: ``black`` formatiert von Nebenversion zu Nebenversion
unterschiedlich. Die CI nimmt die Version aus requirements-dev.txt, der
Entwicklerrechner die zuletzt installierte. Wer lokal formatiert, macht das
Gate dann rot, ohne dass der Code falsch waere - und sieht am eigenen
gruenen Lauf nicht, was der CI-Lauf sehen wird.

Die Version gehoert damit zum Projekt, nicht zum Rechner. Dieses Skript legt
beim ersten Aufruf eine Wegwerf-Umgebung unter ~/.cache an, installiert die
gepinnte Version und ruft sie auf. Ohne Netz und ohne passende Umgebung sagt
es das und bricht ab, statt still die falsche Version zu nehmen.

    python3 tools/gepinnte_werkzeuge.py black --check model/
    python3 tools/gepinnte_werkzeuge.py ruff check .

**Warum die Umgebung fuer mypy groesser ist** (Befund aus Loop 55): black und
ruff lesen nur Text - ihre Umgebung darf leer sein. ``mypy`` loest Importe
auf. Ohne PySide6 ist jeder Qt-Typ ``Any``, und ein Lauf ueber Qt-nahen Code
geht gruen durch, waehrend die CI mit installiertem PySide6 dieselben Dateien
ablehnt. Genau so entstand ein lokal gruener, in der CI roter Lauf.

Fuer mypy installiert das Skript darum die Projektabhaengigkeiten mit. Das
kostet beim ersten Aufruf einige Minuten und danach nichts mehr. Schlaegt es
fehl, bricht es ab, statt einen leeren Lauf gruen zu melden - ein Urteil ohne
die Abhaengigkeiten waere keines.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CACHE = (
    Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache"))
    / "budgetmanager-werkzeuge"
)

_PIN = re.compile(r"^(?P<name>[A-Za-z0-9_.-]+)==(?P<version>[^\s;#]+)")


def gepinnte_version(werkzeug: str) -> str:
    """Liest die Pinnung aus den requirements-Dateien des Projekts."""
    for datei in sorted(ROOT.glob("requirements*.txt")) + sorted(
        ROOT.glob("requirements*.in")
    ):
        for zeile in datei.read_text(encoding="utf-8").splitlines():
            treffer = _PIN.match(zeile.strip())
            if treffer and treffer.group("name").lower() == werkzeug.lower():
                return treffer.group("version")
    raise SystemExit(f"{werkzeug} ist in keiner requirements-Datei exakt gepinnt")


# Werkzeuge, die zum Urteilen die Abhaengigkeiten des Projekts brauchen.
#
# black und ruff lesen nur Text - ihre Umgebung darf leer sein. mypy loest
# Importe auf: Ohne PySide6 ist jeder Qt-Typ ``Any``, und ein Lauf ueber
# Qt-nahen Code geht gruen durch, waehrend die CI dieselben Dateien ablehnt.
# Genau das passierte in Loop 55.
BRAUCHT_ABHAENGIGKEITEN = {"mypy"}

# Was mitinstalliert wird. Nicht die ganze requirements-Datei: Der Lauf soll
# Minuten dauern, nicht eine Viertelstunde. Diese drei decken ab, was die
# gepruefte Schicht importiert.
LAUFZEIT_PAKETE = ("pyside6", "requests", "types-requests")


def _pip(ziel: Path, *pakete: str, leise: bool = True) -> int:
    befehl = [str(ziel / "bin" / "python"), "-m", "pip", "install"]
    if leise:
        befehl.append("--quiet")
    befehl.extend(pakete)
    return subprocess.run(befehl, check=False).returncode


def umgebung(werkzeug: str, version: str) -> Path:
    """Legt die Umgebung an, falls sie fehlt; sonst wird sie wiederverwendet."""
    ziel = CACHE / f"{werkzeug}-{version}"
    programm = ziel / "bin" / werkzeug
    marke = ziel / ".abhaengigkeiten-vollstaendig"
    braucht_pakete = werkzeug in BRAUCHT_ABHAENGIGKEITEN

    if programm.is_file() and (marke.is_file() or not braucht_pakete):
        return programm

    if not programm.is_file():
        ziel.parent.mkdir(parents=True, exist_ok=True)
        venv.EnvBuilder(with_pip=True, clear=True).create(ziel)
        if _pip(ziel, f"{werkzeug}=={version}") != 0 or not programm.is_file():
            raise SystemExit(
                f"{werkzeug}=={version} liess sich nicht bereitstellen - "
                "ohne Netz bitte die gepinnte Version von Hand installieren"
            )

    if braucht_pakete:
        print(
            f"+ {werkzeug} braucht die Projektabhaengigkeiten "
            f"({', '.join(LAUFZEIT_PAKETE)}) - einmalig, das dauert."
        )
        if _pip(ziel, *LAUFZEIT_PAKETE) != 0:
            # Kein Abbruch mit leerer Umgebung: Ein Lauf ohne diese Pakete
            # waere gruen und wertlos. Lieber deutlich sagen, was fehlt.
            raise SystemExit(
                f"{werkzeug} braucht {', '.join(LAUFZEIT_PAKETE)}, und sie "
                "liessen sich nicht installieren. Ein Lauf ohne sie waere "
                "gruen und wuerde nichts bedeuten - siehe Loop 55."
            )
        marke.write_text("ok\n", encoding="utf-8")

    return programm


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("werkzeug", help="black oder ruff")
    parser.add_argument("argumente", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    version = gepinnte_version(args.werkzeug)
    programm = umgebung(args.werkzeug, version)
    print(f"+ {args.werkzeug} {version} (gepinnt) {' '.join(args.argumente)}")
    return subprocess.run(
        [str(programm), *args.argumente], cwd=ROOT, check=False
    ).returncode


if __name__ == "__main__":
    sys.exit(main())
