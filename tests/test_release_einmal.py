"""Ein Release baut und veroeffentlicht genau einmal.

Beim Release werden main und Tag zusammen gepusht. Wo der Bau an beidem
haengt - am Tag *und* an einem [release]-Commit auf main -, laeuft er zweimal
fuer denselben Stand. Beide Laeufe laden unter denselben Tag hoch, und die
Assets sind signiert: Das Manifest traegt die Hashes der Pakete. Kommen
Manifest und Paket aus verschiedenen Builds, passt die Signatur nicht mehr,
und der Updater lehnt fail-closed ab - genau der Schutz aus Loop 3,
ausgehebelt durch einen Wettlauf.

Gefunden beim Release in Loop 30: BudgetManager und LifePlanner bauten
tatsaechlich doppelt.

Alle vier Programme der Suite fuehren diesen Test unter demselben Namen.
"""
from __future__ import annotations

from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parents[1]
WORKFLOWS = WURZEL / ".github" / "workflows"


def _bauende_workflows() -> list[Path]:
    """Workflows, die Pakete bauen oder veroeffentlichen."""
    treffer = []
    for pfad in sorted(WORKFLOWS.glob("*.yml")):
        text = pfad.read_text(encoding="utf-8")
        if any(
            wort in text
            for wort in ("action-gh-release", "gh release create", "pyinstaller", "PyInstaller")
        ):
            treffer.append(pfad)
    return treffer


def test_es_gibt_einen_release_workflow() -> None:
    assert _bauende_workflows(), "kein bauender Workflow gefunden"


@pytest.mark.parametrize("pfad", _bauende_workflows(), ids=lambda p: p.name)
def test_der_bau_haengt_nicht_zugleich_am_commit_text(pfad: Path) -> None:
    """Sonst baut derselbe Stand zweimal: einmal fuer main, einmal fuer den Tag."""
    text = pfad.read_text(encoding="utf-8")
    assert "head_commit.message, '[release]'" not in text, (
        f"{pfad.name} baut auch bei einem [release]-Commit auf main. "
        "Beim Release werden main und Tag zusammen gepusht - das sind zwei "
        "Laeufe fuer denselben Stand, die beide unter denselben Tag hochladen."
    )


@pytest.mark.parametrize("pfad", _bauende_workflows(), ids=lambda p: p.name)
def test_zwei_laeufe_fuer_denselben_stand_koennen_sich_nicht_ueberholen(
    pfad: Path,
) -> None:
    """Die Sperre faengt ab, was die Bedingung oben nicht abdeckt."""
    text = pfad.read_text(encoding="utf-8")
    assert "concurrency:" in text, f"{pfad.name} ohne concurrency-Sperre"
