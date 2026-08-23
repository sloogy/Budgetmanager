import ast
import json
from pathlib import Path

from app_info import APP_VERSION
from model import app_paths
from model.lifeplanner_import_service import default_bridge_dir

ROOT = Path(__file__).resolve().parents[1]


def test_manifest_and_host_paths(monkeypatch, tmp_path):
    manifest = json.loads((ROOT / "module.json").read_text(encoding="utf-8"))
    assert manifest["schema"] == "lifeplanner.module.v2"
    assert manifest["id"] == "budgetmanager"
    assert manifest["version"] == APP_VERSION
    assert manifest["requires_host"] == ">=0.5.15,<1.0"
    monkeypatch.setenv("BUDGETMANAGER_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("LIFEPLANNER_BRIDGE_DIR", str(tmp_path / "bridge"))
    assert app_paths.data_dir() == (tmp_path / "data").resolve()
    assert default_bridge_dir() == (tmp_path / "bridge").resolve()


def _methodenquelle(pfad: Path, name: str) -> str:
    """Gibt den Quelltext genau einer Methode zurueck.

    Vorher wurde von einem ``def`` bis zum naechsten geschnitten - das band
    den Test an die Reihenfolge der Methoden und brach, sobald eine dazwischen
    kam oder umzog.
    """
    baum = ast.parse(pfad.read_text(encoding="utf-8"))
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.FunctionDef) and knoten.name == name:
            return (
                ast.get_source_segment(pfad.read_text(encoding="utf-8"), knoten) or ""
            )
    raise AssertionError(f"{name} nicht in {pfad.name} gefunden")


def test_central_updater_suppresses_internal_startup_check():
    quelle = ROOT / "views" / "main_window_update.py"
    schedule = _methodenquelle(quelle, "schedule_startup_update_check")
    manual = _methodenquelle(quelle, "_show_update_dialog")
    assert "LIFEPLANNER_CENTRAL_UPDATER" in schedule
    assert "LIFEPLANNER_CENTRAL_UPDATER" in manual
