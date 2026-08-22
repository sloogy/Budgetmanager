from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_requirements_lock_header_matches_current_release():
    import app_info

    lock = (ROOT / "requirements.lock").read_text(encoding="utf-8")
    expected = f"# Stand: v{app_info.APP_VERSION} / {app_info.APP_RELEASE_DATE}"
    assert expected in lock.splitlines()[:5]


def test_github_workflow_cleans_and_verifies_lint_procedure_before_pyinstaller():
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    pytest_pos = workflow.index("python -m pytest tests/ -v -ra --tb=short")
    clean_pos = workflow.index("python tools/clean_release_tree.py")
    lint_pos = workflow.index("python tools/lint_procedure_check.py")
    build_pos = workflow.index("pyinstaller BudgetManager.spec --noconfirm")
    assert pytest_pos < clean_pos < lint_pos < build_pos


def test_release_checklist_contains_cleaner_and_lint_procedure_check():
    checklist = (ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")
    assert "python tools/clean_release_tree.py" in checklist
    assert "python tools/lint_procedure_check.py" in checklist
    assert "python -m pytest tests/ -v -ra --tb=short" in checklist
    # Ueber den Wrapper: die Checkliste soll die gepinnte Version aufrufen,
    # nicht die zufaellig installierte.
    assert (
        "python tools/gepinnte_werkzeuge.py black --check --workers 1 main.py"
        in checklist
    )
    assert "python tools/gepinnte_werkzeuge.py mypy model/" in checklist


def test_lint_procedure_script_exists_and_is_self_contained():
    src = (ROOT / "tools" / "lint_procedure_check.py").read_text(encoding="utf-8")
    assert "def check_workflow" in src
    assert "def check_generated_artifacts" in src
    assert "def check_security_lint" in src
    assert "python tools/clean_release_tree.py" in src
    assert "--force-reinstall" in src
    assert "requirements-dev.txt" in src


def test_lint_procedure_passes_after_clean_release_tree():
    subprocess.run(
        [sys.executable, "tools/clean_release_tree.py"], cwd=ROOT, check=True
    )
    result = subprocess.run(
        [sys.executable, "tools/lint_procedure_check.py"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "PASS" in result.stdout
