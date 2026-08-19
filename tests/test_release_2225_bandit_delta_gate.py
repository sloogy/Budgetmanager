from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools.bandit_release_gate import evaluate

ROOT = Path(__file__).resolve().parents[1]


def _item(*, severity: str = "MEDIUM", line: int = 10) -> dict[str, object]:
    return {
        "filename": "model/example.py",
        "test_id": "B608",
        "issue_severity": severity,
        "issue_text": "Possible SQL injection vector.",
        "line_number": line,
    }


def test_any_medium_finding_blocks_release():
    result = evaluate({"results": [_item()]})
    assert result["status"] == "FAIL"
    assert len(result["blocking_findings"]) == 1


def test_any_high_finding_blocks_release():
    result = evaluate({"results": [_item(severity="HIGH")]})
    assert result["status"] == "FAIL"


def test_low_findings_are_reported_but_do_not_block():
    result = evaluate({"results": [_item(severity="LOW")]})
    assert result["status"] == "PASS"
    assert result["severity_counts"]["LOW"] == 1


def test_current_source_has_zero_medium_and_high_findings(tmp_path: Path):
    pytest.importorskip(
        "bandit", reason="bandit nicht installiert – Gate läuft nur in CI/Dev-Umgebung"
    )
    current = tmp_path / "bandit.json"
    summary = tmp_path / "summary.json"
    completed = subprocess.run(
        [
            sys.executable,
            "tools/bandit_release_gate.py",
            "--bandit-json",
            str(current),
            "--summary-json",
            str(summary),
        ],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    payload = json.loads(summary.read_text(encoding="utf-8"))
    assert payload["status"] == "PASS"
    assert payload["blocking_findings"] == []


def test_bandit_tooling_remains_available_for_local_audits():
    assert (ROOT / "tools" / "bandit_release_gate.py").is_file()
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8")
    assert "bandit==" in requirements
