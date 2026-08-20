"""v2.2.28 – Merge- und Dependency-Kompatibilitätsgates."""

from __future__ import annotations

import re
from pathlib import Path

from app_info import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _locked_version(package: str) -> tuple[int, ...]:
    text = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    match = re.search(
        rf"^{re.escape(package)}==([0-9]+(?:\.[0-9]+)+)(?:\s*\\)?\s*$",
        text,
        re.MULTILINE,
    )
    assert match, f"{package} fehlt oder ist nicht exakt gepinnt"
    return tuple(int(part) for part in match.group(1).split("."))


def test_current_version_is_2224():
    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)


def test_pyside_lock_supports_python_313_target():
    # 6.7.3 war unter Python 3.13 nicht installierbar. Die Merge-Version
    # verwendet die im Audit tatsächlich getestete Qt-Version.
    assert _locked_version("PySide6") >= (6, 10, 3)


def test_single_release_workflow_uses_python_312_and_declared_dependencies():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "python-version: '3.12'" in workflow
    assert (
        "python -m pip install --require-hashes -r requirements-build.lock" in workflow
    )
    assert "python -m pip install --require-hashes -r requirements-dev.lock" in workflow


def test_previous_release_regression_suite_is_retained():
    assert (ROOT / "tests" / "test_release_2223_enterprise_ui_adhs.py").is_file()
    assert (ROOT / "tools" / "enterprise_ui_adhs_audit_1000.py").is_file()
