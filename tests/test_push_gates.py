"""Bei jedem Push nach main laufen die Gates.

Bis Loop 22 lief bei einem gewoehnlichen main-Push in keinem der vier
Programme irgendetwas: Der Enterprise-Check haengt am Pull Request, der volle
Release-Lauf am Tag oder an einem [release]-Commit. Gearbeitet wird hier aber
direkt auf main. Ein Fehler waere also erst beim naechsten Release
aufgefallen - bis zu zehn Arbeitsrunden spaeter.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
WORKFLOW = WURZEL / ".github" / "workflows" / "push-checks.yml"


@pytest.fixture(scope="module")
def inhalt() -> str:
    assert WORKFLOW.is_file(), "der Push-Prueflauf fehlt"
    return WORKFLOW.read_text(encoding="utf-8")


def test_der_prueflauf_haengt_am_push_nach_main(inhalt: str) -> None:
    assert "push:" in inhalt
    assert "branches: [main]" in inhalt


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
