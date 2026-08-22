from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def _erlaubte_workflows() -> list[str]:
    """Liest die erlaubte Liste aus dem Werkzeug, statt sie abzuschreiben.

    Sie stand hier viermal als ["build.yml"] und musste bei jeder Aenderung an
    vier Stellen nachgezogen werden - derselbe Fehler wie bei den Versionen in
    Loop 6.
    """
    import importlib.util

    pfad = ROOT / "tools" / "lint_procedure_check.py"
    spec = importlib.util.spec_from_file_location("lint_procedure_check", pfad)
    assert spec and spec.loader
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return list(modul.ERLAUBTE_WORKFLOWS)



def test_release_workflow_is_single_tag_pipeline_with_release_permission() -> None:
    workflow_dir = ROOT / ".github" / "workflows"
    assert sorted(path.name for path in workflow_dir.glob("*.yml")) == _erlaubte_workflows()
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "permissions:\n  contents: write" in workflow
    assert "tags:\n      - 'v*'" in workflow
    for line in workflow.splitlines():
        if "uses:" in line:
            ref = line.split("@", 1)[1].split()[0]
            assert ref in {"v2", "v4", "v5"}


def test_manifest_gate_is_fail_closed_without_public_key() -> None:
    source = (ROOT / "tools/verify_release_manifest.py").read_text(encoding="utf-8")
    assert "kryptografische Prüfung erfolgt clientseitig" not in source
    assert "Kein vertrauenswürdiger Update-Public-Key verfügbar" in source


def test_responsive_dialog_hardening_is_applied_to_large_dialogs() -> None:
    required = [
        "settings_dialog.py",
        "views/recurring_bookings_dialog.py",
        "views/category_manager_dialog.py",
        "views/help_dialog.py",
        "views/shortcuts_dialog.py",
        "views/setup_assistant_dialog.py",
        "views/budget_fill_dialog.py",
        "views/global_search_dialog.py",
        "views/favorites_dashboard_dialog.py",
        "views/tags_manager_dialog.py",
    ]
    for rel in required:
        text = (ROOT / rel).read_text(encoding="utf-8")
        assert "harden_dialog_for_screen(self)" in text, rel


def test_architecture_gate_has_explicit_bounded_legacy_exception() -> None:
    source = (ROOT / "tools/architecture_quality_gate.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert "LEGACY_FUNCTION_LIMITS" in source
    assert "continue" not in source[source.index("for node in ast.walk") :]
    assert "explizit budgetierte Legacy-Ausnahmen" in source
