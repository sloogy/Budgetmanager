from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_tag_build_requires_enterprise_10000_audit():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "enterprise-release-audit-10000:" in workflow
    assert "python tools/enterprise_release_audit_10000.py" in workflow
    assert "--loops 10000" in workflow
    assert "--seed 20260718" in workflow
    assert "enterprise-release-audit-10000" in workflow.split("needs:", 1)[1]
    assert "if-no-files-found: error" in workflow


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
