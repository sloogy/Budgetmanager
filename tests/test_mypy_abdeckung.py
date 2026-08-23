"""Wieviel vom Projekt die Typprüfung abdeckt.

`mypy` lief bis Loop 55 nur über `model/`. Was daneben lag - die Helfer in
`utils/`, der ganze Updater - war ungeprüft, obwohl dort Code steht, der
Dateien schreibt und Signaturen prüft.

Die Ausweitung kostete zwei Funde: einen fehlenden Stub für `requests` und
ein Dict, aus dem heraus aufgerufen wird, ohne dass sein Typ beschrieben war
(`utils/rechner.py`, Loop 52). Beide sind behoben.

Wie beim black-Gate aus Loop 44 prüft dieser Test die **Abdeckung**, nicht die
Liste: Ein neues Verzeichnis fällt auf, weil kein Prüfziel es enthält.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Was heute geprüft wird. Die Liste wächst - sie darf nie schrumpfen.
GEPRUEFT = ("model", "utils", "updater")

# Was noch aussteht, mit Grund. Steht ein Verzeichnis hier, ist das eine
# bekannte Lücke und keine vergessene.
OFFEN = {
    "views": "Qt-lastig; mypy.ini schliesst es ausdruecklich aus",
    "tools": "generate_sbom.py kollidiert im Modulpfad (Loop 55)",
    "tests": "Testcode wird nicht typgeprueft",
    "installer": "Nur Skripte fuer den Paketbau",
    "locales": "keine Python-Dateien",
    "resources": "keine Python-Dateien",
    "docs": "keine Python-Dateien",
    "data": "keine Python-Dateien",
    "release_notes": "keine Python-Dateien",
    "audit_artifacts": "erzeugte Dateien",
}


def _mypy_ziele(pfad: Path) -> list[str]:
    """Die Verzeichnisse, die eine Workflow-Datei an mypy übergibt."""
    ziele: list[str] = []
    for zeile in pfad.read_text(encoding="utf-8").splitlines():
        if "mypy" not in zeile or zeile.strip().startswith("#"):
            continue
        for treffer in re.findall(r"\b([a-z_]+)/", zeile.split("mypy", 1)[1]):
            ziele.append(treffer)
    return ziele


def test_die_gates_pruefen_dieselben_verzeichnisse() -> None:
    """Zwei Workflows, ein Anspruch - sonst driftet einer davon."""
    for name in ("build.yml", "push-checks.yml"):
        ziele = _mypy_ziele(ROOT / ".github" / "workflows" / name)
        fehlend = set(GEPRUEFT) - set(ziele)
        assert not fehlend, f"{name} prueft {sorted(fehlend)} nicht"


def test_jedes_python_verzeichnis_ist_geprueft_oder_begruendet_offen() -> None:
    """Ein neues Verzeichnis faellt auf, weil es in keiner der beiden Listen steht."""
    unbekannt = []
    for eintrag in sorted(ROOT.iterdir()):
        if not eintrag.is_dir() or eintrag.name.startswith((".", "_")):
            continue
        if not any(eintrag.rglob("*.py")):
            continue
        if eintrag.name in GEPRUEFT or eintrag.name in OFFEN:
            continue
        unbekannt.append(eintrag.name)
    assert not unbekannt, "weder geprueft noch als offen vermerkt: " + ", ".join(
        unbekannt
    )


def test_die_offenen_luecken_tragen_einen_grund() -> None:
    """Ein Eintrag ohne Begruendung ist eine vergessene Luecke."""
    for name, grund in OFFEN.items():
        assert grund.strip(), f"{name} steht ohne Grund auf der Ausnahmeliste"
