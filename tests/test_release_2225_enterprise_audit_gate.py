from __future__ import annotations

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


def test_tag_build_uses_only_the_single_release_workflow():
    workflow_dir = ROOT / ".github" / "workflows"
    assert (
        sorted(path.name for path in workflow_dir.glob("*.yml"))
        == _erlaubte_workflows()
    )
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "build:" in workflow
    assert "installer:" in workflow
    assert "manifest:" in workflow
    assert "enterprise-release-audit-10000:" not in workflow


def test_release_checklist_requires_enterprise_10000_audit():
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    assert "python tools/enterprise_release_audit_10000.py" in checklist
    assert "--loops 10000" in checklist
    assert "10.000" in checklist


def test_ui_audit_uses_current_version_for_evidence_filename():
    source = (ROOT / "tools" / "enterprise_ui_adhs_audit_1000.py").read_text(
        encoding="utf-8"
    )
    assert "from app_info import APP_VERSION" in source
    assert "APP_VERSION.replace" in source
    assert "UI_USABILITY_ADHS_1000_LOOP_MATRIX_v2_2_24.csv" not in source
