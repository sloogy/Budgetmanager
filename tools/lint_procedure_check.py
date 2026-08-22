#!/usr/bin/env python3
"""Prueft die Lint-/Release-Prozedur ohne externe Zusatzpakete.

Ziel: Fail-fast vor dem Packen/Bauen, wenn der Release-Baum oder die CI-Prozedur
inkonsistent ist. Dieser Check ersetzt nicht Black/Mypy/Pytest, sondern prueft,
dass diese Gates und der Release-Cleaner korrekt verdrahtet sind.
"""

from __future__ import annotations

import ast
import json
import os
import re
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    "build",
    "dist",
    "installer_output",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
}
EXCLUDED_DIR_PREFIXES = (".venv", "venv")
GENERATED_FILE_PATTERNS = (
    # v2.2.20 (Audit-Fix B): Laufzeit-Settings & Theme-Profile sind
    # Nutzerdaten und duerfen nie im Release-Baum liegen.
    "data/budgetmanager_settings.json",
    "data/theme_profiles/*",
    "*.pyc",
    "*.pyo",
    "*.log",
    "data/backups/*.bmr",
    "data/*.enc",
    "data/*.db",
    "data/*.sqlite",
    "data/*.sqlite3",
    "data/users.json",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _app_version_and_date() -> tuple[str, str]:
    text = _read(ROOT / "app_info.py")
    version_match = re.search(
        r"^APP_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE
    )
    date_match = re.search(
        r"^APP_RELEASE_DATE\s*=\s*['\"]([^'\"]+)['\"]", text, re.MULTILINE
    )
    if not version_match or not date_match:
        raise RuntimeError(
            "APP_VERSION oder APP_RELEASE_DATE in app_info.py nicht gefunden"
        )
    return version_match.group(1), date_match.group(1)


def _is_excluded_path(path: Path) -> bool:
    """Lokale Umgebungen und generierte Ordner nie als Release-Code werten."""
    parts = path.relative_to(ROOT).parts
    return any(
        part in EXCLUDED_DIRS or part.startswith(EXCLUDED_DIR_PREFIXES)
        for part in parts
    )


def _iter_project_paths(pattern: str) -> Iterable[Path]:
    """Iteriert nur durch Projektdateien und betritt lokale venvs nie."""
    for dirpath, dirnames, filenames in os.walk(ROOT):
        current = Path(dirpath)
        dirnames[:] = [
            dirname for dirname in dirnames if not _is_excluded_path(current / dirname)
        ]
        for filename in filenames:
            path = current / filename
            if path.match(pattern) and not _is_excluded_path(path):
                yield path


def _python_files() -> Iterable[Path]:
    yield from _iter_project_paths("*.py")


def _line_col(text: str, lineno: int, col: int) -> str:
    line = text.splitlines()[lineno - 1] if lineno > 0 else ""
    return f"line {lineno}, col {col}: {line.strip()}"


def check_versions() -> list[str]:
    errors: list[str] = []
    version, date = _app_version_and_date()

    lock = _read(ROOT / "requirements.lock")
    expected = f"# Stand: v{version} / {date}"
    if expected not in lock.splitlines()[:5]:
        errors.append(
            f"requirements.lock Header fehlt/ist veraltet: erwartet {expected!r}"
        )

    # v2.2.15 (M2): README enthaelt ein app_info-Codebeispiel; ein veraltetes
    # Datum/eine veraltete Version dort fiel bisher durch keinen Check.
    readme = _read(ROOT / "README.md")
    if f'APP_VERSION = "{version}"' not in readme:
        errors.append(f"README.md: APP_VERSION-Beispiel nicht auf {version}")
    if f'APP_RELEASE_DATE = "{date}"' not in readme:
        errors.append(f"README.md: APP_RELEASE_DATE-Beispiel nicht auf {date!r}")
    build_req = _read(ROOT / "requirements-build.txt")
    if "pyinstaller==" not in build_req:
        errors.append(
            "requirements-build.txt: pyinstaller ist nicht exakt gepinnt (==)"
        )

    version_json = json.loads(_read(ROOT / "version.json"))
    if version_json.get("version") != version:
        errors.append("version.json ist nicht mit app_info.py synchron")

    for rel in ("latest.json.template", "docs/latest.json.template"):
        data = json.loads(_read(ROOT / rel))
        if data.get("version") != version or data.get("release_tag") != f"v{version}":
            errors.append(f"{rel} ist nicht mit v{version} synchron")
    return errors


def check_generated_artifacts() -> list[str]:
    """Meldet generierte Verzeichnisse/Dateien, die nicht ins Release-ZIP gehoeren.

    v2.2.31 (Deep-Audit-Fix A): Dieser Check war bis v2.2.30 beweisbar tot.
    Er hat zuerst ``dirnames`` per ``_is_excluded_path()`` beschnitten – was
    exakt die Namen aus ``EXCLUDED_DIRS`` entfernt – und danach die bereits
    beschnittene Liste gegen ``EXCLUDED_DIRS - {".git"}`` geprueft. Die
    Bedingung konnte deshalb fuer keinen einzigen Namen mehr wahr werden, und
    ".git" war explizit ausgenommen. Ergebnis: ``__pycache__`` und
    ``.pytest_cache`` wurden im v2.2.30-ZIP ausgeliefert, obwohl das Gate PASS
    meldete.

    Fix: Erkennung strikt VOR dem Pruning. Das Pruning bleibt erhalten, damit
    nicht in die Ordner hinein abgestiegen und pro Unterordner erneut gemeldet
    wird – gemeldet wird also der oberste Treffer, nicht jeder Nachfahre.

    Zweiter toter Pfad: ``*.pyc``/``*.pyo``/``*.log`` wurden per
    ``ROOT.glob(pattern)`` gesucht – nicht rekursiv. ``.pyc`` liegt aber
    ausschliesslich in ``__pycache__``-Unterordnern und war damit ebenfalls
    unauffindbar. Muster ohne Pfadtrenner werden jetzt rekursiv geprueft.
    """
    errors: list[str] = []
    generated_dir_names = EXCLUDED_DIRS - {".git"}

    for dirpath, dirnames, _filenames in os.walk(ROOT):
        current = Path(dirpath)

        # 1) ERKENNEN (vor jedem Pruning!)
        for dirname in list(dirnames):
            if dirname in generated_dir_names:
                path = current / dirname
                errors.append(
                    f"generiertes Verzeichnis im Release-Baum: {path.relative_to(ROOT)}"
                )

        # 2) PRUNEN (nicht hineinsteigen: keine Doppelmeldung je Nachfahre,
        #    keine Laufzeit in fremden venvs)
        dirnames[:] = [
            dirname for dirname in dirnames if not _is_excluded_path(current / dirname)
        ]

    for pattern in GENERATED_FILE_PATTERNS:
        # Muster mit Pfadtrenner sind bewusst wurzelrelativ (z. B.
        # "data/users.json"); reine Namensmuster gelten baumweit.
        globber = ROOT.glob(pattern) if "/" in pattern else ROOT.rglob(pattern)
        for path in globber:
            if path.is_file() and not _is_excluded_path(path):
                errors.append(
                    f"generierte/private Datei im Release-Baum: {path.relative_to(ROOT)}"
                )
    return errors


def _dev_black_pin() -> str | None:
    for line in _read(ROOT / "requirements-dev.txt").splitlines():
        stripped = line.strip()
        if stripped.startswith("black=="):
            return stripped.split("==", 1)[1].split("#", 1)[0].strip()
    return None


# Feste Liste statt "genau einer": build.yml ist der Release-Weg,
# push-checks.yml der schnelle Lauf bei jedem main-Push. Die Regel bleibt
# scharf - ein dritter Workflow faellt weiterhin auf, und damit auch die
# Frage, welcher davon der massgebliche ist. Vier Tests lesen diese Liste,
# statt sie abzuschreiben; vorher stand ["build.yml"] viermal im Testbaum und
# musste bei jeder Aenderung an vier Stellen nachgezogen werden.
ERLAUBTE_WORKFLOWS = ["build.yml", "push-checks.yml"]

# Nur dieser Workflow darf am Tag haengen und veroeffentlichen.
RELEASE_WORKFLOW = "build.yml"


def check_workflow() -> list[str]:
    errors: list[str] = []
    workflow_dir = ROOT / ".github" / "workflows"
    workflow_path = workflow_dir / "build.yml"
    workflow = _read(workflow_path)

    workflow_files = sorted(
        path.name
        for pattern in ("*.yml", "*.yaml")
        for path in workflow_dir.glob(pattern)
    )
    if workflow_files != ERLAUBTE_WORKFLOWS:
        errors.append(
            "Erlaubt sind genau diese GitHub-Workflows: "
            + ", ".join(ERLAUBTE_WORKFLOWS)
            + "; gefunden: "
            + ", ".join(workflow_files)
        )

    # Eine zweite, harte Black-Version im Workflow ist ein Release-Risiko:
    # requirements-dev.txt ist die zentrale Quelle. Ein abweichendes
    # force-reinstall kann GitHub Actions brechen, obwohl lokale Checks grün sind.
    if "--force-reinstall" in workflow and "black==" in workflow:
        errors.append(
            "GitHub-Workflow darf Black nicht separat per --force-reinstall pinnen; "
            "requirements-dev.txt ist die zentrale Dev-Tool-Quelle"
        )
    black_pin = _dev_black_pin()
    if black_pin and f"black=={black_pin}" not in _read(ROOT / "requirements-dev.txt"):
        errors.append(
            "requirements-dev.txt Black-Pin konnte nicht sauber gelesen werden"
        )

    required_snippets = [
        "tags:\n      - 'v*'",
        "permissions:\n  contents: write",
        "python tools/verify_hashed_lock.py",
        "python -m pip install --require-hashes -r requirements-build.lock",
        "python -m pip install --require-hashes -r requirements-dev.lock",
        "python tools/sync_version.py --check",
        "python tools/verify_qt_translations.py",
        "python -m compileall -q .",
        "python -m black --check model/",
        "python -m mypy model/",
        "python -m pytest tests/ -v -ra --tb=short",
        "python tools/clean_release_tree.py",
        "python tools/lint_procedure_check.py",
        "pyinstaller BudgetManager.spec --noconfirm",
        "windows-latest",
        "ubuntu-latest",
        "Build Windows installer",
        "Test silent install, app start and uninstall",
        "--release-self-test",
        "tools/build_release_assets.py",
        "tools/build_lifeplanner_module.py",
        "--allow-unsigned",
        "release/*.lpmodule*",
        "Verify updater manifest stays updater-safe",
        "softprops/action-gh-release@v2",
    ]
    for snippet in required_snippets:
        if snippet not in workflow:
            errors.append(f"GitHub-Workflow fehlt Gate: {snippet}")

    pytest_pos = workflow.find("python -m pytest tests/ -v -ra --tb=short")
    clean_pos = workflow.find("python tools/clean_release_tree.py")
    lint_pos = workflow.find("python tools/lint_procedure_check.py")
    build_pos = workflow.find("pyinstaller BudgetManager.spec --noconfirm")
    if min(pytest_pos, clean_pos, lint_pos, build_pos) >= 0:
        if not (pytest_pos < clean_pos < lint_pos < build_pos):
            errors.append(
                "Workflow-Reihenfolge muss sein: pytest -> clean_release_tree -> lint_procedure_check -> PyInstaller"
            )
    else:
        errors.append("Workflow-Reihenfolge konnte nicht vollstaendig geprüft werden")
    return errors


def check_release_docs() -> list[str]:
    errors: list[str] = []
    checklist = _read(ROOT / "docs" / "release-checklist.md")
    required_commands = [
        "python tools/sync_version.py --check",
        "python -m compileall -q .",
        "python tools/i18n_audit.py",
        "python tools/dau_first_run_check.py",
        "python -m black --check --workers 1 main.py",
        "python -m mypy model/",
        "python tools/verify_hashed_lock.py",
        "python tools/architecture_quality_gate.py",
        "python tools/coverage_gate.py",
        "python tools/bandit_release_gate.py",
        "python -m pytest tests/ -v -ra --tb=short",
        "python tools/enterprise_release_audit_10000.py",
        "python tools/clean_release_tree.py",
        "python tools/lint_procedure_check.py",
    ]
    for command in required_commands:
        if command not in checklist:
            errors.append(f"Release-Checkliste fehlt Kommando: {command}")
    return errors


def check_required_regression_tests() -> list[str]:
    """Sichert ab, dass kritische Release-Hardening-Tests nicht versehentlich verschwinden."""
    errors: list[str] = []
    required_tests = {
        "tests/test_lint_release_procedure_v2041.py": [
            "test_lint_procedure_passes_after_clean_release_tree",
            "clean_release_tree.py",
            "lint_procedure_check.py",
        ],
        "tests/test_password_hash_keysep_v2041.py": [
            "test_login_migrates_legacy_key_equivalent_hash_even_at_current_iterations",
            "is_legacy_password_hash",
        ],
        "tests/test_lock_procedure_account_language_v2041.py": [
            "test_account_lifecycle_quick_pin_password_delete",
            "test_security_labels_are_localized_for_de_en_fr",
            "test_lint_procedure_locks_required_regression_tests_into_release_gate",
        ],
        "tests/test_release_2225_enterprise_audit_gate.py": [
            "test_tag_build_uses_only_the_single_release_workflow",
            'glob("*.yml")',
            '"build.yml"',
        ],
        "tests/test_release_2225_bandit_delta_gate.py": [
            "test_current_source_has_zero_medium_and_high_findings",
            "test_any_medium_finding_blocks_release",
            "bandit_release_gate.py",
        ],
        "tests/test_release_2261_overview_chart_lifetime.py": [
            "test_overview_refresh_never_calls_remove_all_series",
            "test_retired_chart_uses_deferred_cpp_deletion_and_strong_reference",
            "self._retired_charts[key] = chart",
            "chart.deleteLater()",
        ],
        "tests/test_release_2261_dependency_locks.py": [
            "test_release_locks_match_all_direct_and_included_pins",
            "test_lock_validator_rejects_direct_version_drift",
        ],
    }
    for rel, markers in required_tests.items():
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"kritischer Regressionstest fehlt: {rel}")
            continue
        text = _read(path)
        for marker in markers:
            if marker not in text:
                errors.append(
                    f"kritischer Regressionstest {rel} fehlt Marker: {marker}"
                )
    return errors


def check_security_lint() -> list[str]:
    errors: list[str] = []
    for path in _python_files():
        text = _read(path)
        try:
            tree = ast.parse(text, filename=str(path))
        except SyntaxError as exc:
            errors.append(f"Syntaxfehler in {path.relative_to(ROOT)}: {exc}")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.ExceptHandler) and node.type is None:
                errors.append(
                    f"bare except in {path.relative_to(ROOT)} ({_line_col(text, node.lineno, node.col_offset)})"
                )
            if isinstance(node, ast.Call):
                for kw in node.keywords:
                    if (
                        kw.arg == "shell"
                        and isinstance(kw.value, ast.Constant)
                        and kw.value.value is True
                    ):
                        errors.append(
                            f"shell=True in {path.relative_to(ROOT)} ({_line_col(text, node.lineno, node.col_offset)})"
                        )
                if isinstance(node.func, ast.Name) and node.func.id in {"eval", "exec"}:
                    errors.append(
                        f"{node.func.id}() in {path.relative_to(ROOT)} "
                        f"({_line_col(text, node.lineno, node.col_offset)})"
                    )
    return errors


def check_cleaner_scope() -> list[str]:
    errors: list[str] = []
    cleaner = _read(ROOT / "tools" / "clean_release_tree.py")
    required = [
        "data/backups/*.bmr",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        "build",
        "dist",
        "installer_output",
    ]
    for token in required:
        if token not in cleaner:
            errors.append(f"clean_release_tree.py entfernt {token!r} nicht")
    return errors


def main() -> int:
    checks = {
        "versions": check_versions,
        "generated_artifacts": check_generated_artifacts,
        "workflow": check_workflow,
        "release_docs": check_release_docs,
        "required_regression_tests": check_required_regression_tests,
        "security_lint": check_security_lint,
        "cleaner_scope": check_cleaner_scope,
    }
    errors: list[str] = []
    for name, func in checks.items():
        result = func()
        if result:
            errors.extend(f"[{name}] {item}" for item in result)

    if errors:
        print("Lint-/Release-Prozedur: FAIL")
        for item in errors:
            print(f"- {item}")
        return 1

    print("Lint-/Release-Prozedur: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
