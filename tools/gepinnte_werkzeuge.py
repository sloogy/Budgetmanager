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


def umgebung(werkzeug: str, version: str) -> Path:
    """Legt die Umgebung an, falls sie fehlt; sonst wird sie wiederverwendet."""
    ziel = CACHE / f"{werkzeug}-{version}"
    programm = ziel / "bin" / werkzeug
    if programm.is_file():
        return programm
    ziel.parent.mkdir(parents=True, exist_ok=True)
    venv.EnvBuilder(with_pip=True, clear=True).create(ziel)
    ergebnis = subprocess.run(
        [
            str(ziel / "bin" / "python"),
            "-m",
            "pip",
            "install",
            "--quiet",
            f"{werkzeug}=={version}",
        ],
        check=False,
    )
    if ergebnis.returncode != 0 or not programm.is_file():
        raise SystemExit(
            f"{werkzeug}=={version} liess sich nicht bereitstellen - "
            "ohne Netz bitte die gepinnte Version von Hand installieren"
        )
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
