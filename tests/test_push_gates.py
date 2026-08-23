"""Bei jedem Push nach main laufen die Gates.

Bis Loop 22 lief bei einem gewoehnlichen main-Push in keinem der vier
Programme irgendetwas: Der Enterprise-Check haengt am Pull Request, der volle
Release-Lauf am Tag oder an einem [release]-Commit. Gearbeitet wird hier aber
direkt auf main. Ein Fehler waere also erst beim naechsten Release
aufgefallen - bis zu zehn Arbeitsrunden spaeter.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
WORKFLOW = WURZEL / ".github" / "workflows" / "push-checks.yml"


@pytest.fixture(scope="module")
def inhalt() -> str:
    assert WORKFLOW.is_file(), "der Push-Prueflauf fehlt"
    return WORKFLOW.read_text(encoding="utf-8")


def test_der_prueflauf_haengt_am_push_nach_main(inhalt: str) -> None:
    """main muss erfasst sein - weitere Zweige duerfen dazukommen.

    Geprueft wird die Zusicherung, nicht die Schreibweise. Vorher stand hier
    ein wortgenaues ``branches: [main]``; als der Bankimport-Zweig
    ``feature/**`` ergaenzte, schlug der Test an, obwohl main weiterhin
    geprueft wurde.
    """

    assert "push:" in inhalt
    liste = re.search(r"branches:\s*\[([^\]]*)\]", inhalt)
    assert liste, "der Push-Trigger nennt keine Branch-Liste"
    zweige = {eintrag.strip().strip("'\"") for eintrag in liste.group(1).split(",")}
    assert "main" in zweige, zweige


def test_er_reagiert_nicht_auf_tags(inhalt: str) -> None:
    """Sonst waere das Doppellauf-Problem zurueck, das den Push-Trigger im
    Release-Workflow ausschloss: main und Tag werden zusammen gepusht."""
    assert "tags:" not in inhalt


def test_er_faehrt_keine_builds(inhalt: str) -> None:
    """Er soll in zwei bis drei Minuten durch sein, sonst nutzt ihn niemand."""
    for teuer in ("pyinstaller", "PyInstaller", "innosetup", "upload-artifact"):
        assert teuer not in inhalt, f"{teuer} gehoert in den Release-Lauf"


def test_er_laeuft_den_ausnahmen_ratchet(inhalt: str) -> None:
    assert "exception_audit.py" in inhalt or "validate_release.py" in inhalt


def test_er_laeuft_die_tests(inhalt: str) -> None:
    assert "pytest" in inhalt or "validate_release.py" in inhalt


def test_release_commits_werden_uebersprungen(inhalt: str) -> None:
    """Die gehen ohnehin durch den vollen Lauf."""
    assert "[release]" in inhalt


def test_der_release_marker_muss_am_anfang_stehen(inhalt: str) -> None:
    """`contains` traf jede Erwaehnung im Fliesstext.

    Der Commit, der diesen Prueflauf einbaute, erklaerte in seiner Nachricht,
    dass Release-Commits uebersprungen werden - und wurde deshalb selbst
    uebersprungen. Im BudgetManager loeste derselbe Text sogar einen echten
    Release-Build aus, weil build.yml dieselbe Bedingung nutzt.
    """
    assert "contains(github.event.head_commit.message, '[release]')" not in inhalt
    assert "startsWith(github.event.head_commit.message, '[release]')" in inhalt


def test_black_gate_deckt_jede_python_datei_ab():
    """Die Formatpruefung darf keine Datei auslassen.

    Sie lief lange nur ueber ``model/``. ``tools/`` und ``tests/`` waren zwar
    formatiert, aber ungeprueft: Eine Aenderung dort brach die Formatierung,
    ohne dass ein Gate anschlug. Genau das passierte in Loop 43.

    Geprueft wird die Abdeckung, nicht die Zielliste selbst - sonst waere
    dieser Test nur eine zweite Kopie davon. Ein neues Verzeichnis faellt auf,
    weil keines der genannten Ziele es enthaelt.
    """
    import subprocess

    for datei in (WORKFLOW, WURZEL / ".github" / "workflows" / "build.yml"):
        zeile = next(
            (
                z
                for z in datei.read_text(encoding="utf-8").splitlines()
                if "black --check" in z
            ),
            None,
        )
        assert zeile is not None, f"{datei.name}: keine black-Pruefung"
        ziele = zeile.split("black --check", 1)[1].split()
        assert ziele, f"{datei.name}: black-Pruefung ohne Ziel"

        verfolgt = subprocess.run(
            ["git", "ls-files", "*.py"],
            cwd=WURZEL,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.split()
        ungedeckt = [
            pfad
            for pfad in verfolgt
            if not any(pfad == ziel or pfad.startswith(ziel) for ziel in ziele)
        ]
        assert not ungedeckt, f"{datei.name}: nicht von black geprueft: {ungedeckt}"
