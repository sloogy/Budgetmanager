"""Der Release-Lauf darf keine Workflow-Dateien schreiben.

Jeder Release-Versuch fuer 2.2.72 ist daran gescheitert: Der Prepare-Lauf
trug ``workflow_dispatch`` selbst in .github/workflows/build.yml ein, und
GitHub lehnt einen Push, der eine Workflow-Datei aendert, mit dem
GITHUB_TOKEN ab ("refusing to allow a GitHub App to create or update
workflow ... without `workflows` permission").

Der Eintrag steht jetzt fest in build.yml. Diese Tests halten beides fest -
dass er dort steht, und dass der Prepare-Lauf nicht wieder anfaengt, an
Workflow-Dateien zu schreiben.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github" / "workflows"


def test_build_workflow_kennt_workflow_dispatch() -> None:
    """Ohne diesen Trigger kann der Release-Lauf den Bau nicht anstossen."""
    inhalt = (WORKFLOWS / "build.yml").read_text(encoding="utf-8")
    assert "workflow_dispatch:" in inhalt


def test_prepare_schreibt_keine_workflow_dateien() -> None:
    inhalt = (WORKFLOWS / "release-prepare.yml").read_text(encoding="utf-8")
    schreibend = [
        zeile
        for zeile in inhalt.splitlines()
        if ".github/workflows" in zeile
        and ("write_text" in zeile or "Path(" in zeile or ">>" in zeile)
    ]
    assert not schreibend, f"Prepare-Lauf schreibt an Workflows: {schreibend}"


def test_prepare_bricht_bei_geaenderten_workflows_ab() -> None:
    """Die Vorabpruefung soll den Fehler benennen, bevor der Push ihn zeigt."""
    inhalt = (WORKFLOWS / "release-prepare.yml").read_text(encoding="utf-8")
    assert "git diff --cached --quiet -- .github/workflows" in inhalt
