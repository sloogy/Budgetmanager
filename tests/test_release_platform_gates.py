"""Regressionsschutz für den einzigen, taggesteuerten Release-Workflow."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
WORKFLOW = WORKFLOW_DIR / "build.yml"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_exactly_one_tag_only_release_workflow_exists() -> None:
    files = sorted(
        path.name
        for pattern in ("*.yml", "*.yaml")
        for path in WORKFLOW_DIR.glob(pattern)
    )
    assert files == ["build.yml"]
    workflow = _workflow()
    assert "push:" in workflow
    assert "tags:" in workflow
    assert "- 'v*'" in workflow
    assert "pull_request:" not in workflow
    assert "workflow_call:" not in workflow


def test_single_workflow_builds_windows_linux_installer_and_release() -> None:
    workflow = _workflow()
    for marker in (
        "windows-latest",
        "ubuntu-latest",
        "BudgetManager-windows",
        "BudgetManager-linux",
        "pyinstaller BudgetManager.spec --noconfirm --clean",
        "Build Windows installer",
        "Test silent install, app start and uninstall",
        "--release-self-test",
        "unins000.exe",
        "choco install innosetup",
        "BudgetManager_Setup.exe",
        "tools/build_release_assets.py",
        "Verify updater manifest stays updater-safe",
        "softprops/action-gh-release@v2",
        "release_assets/*",
    ):
        assert marker in workflow


def test_single_workflow_runs_core_quality_checks_before_build() -> None:
    workflow = _workflow()
    for marker in (
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
    ):
        assert marker in workflow


def test_release_jobs_have_one_clear_dependency_chain() -> None:
    workflow = _workflow()
    installer = workflow.split("  installer:\n", 1)[1].split("\n  manifest:\n", 1)[0]
    manifest = workflow.split("  manifest:\n", 1)[1]
    assert "\n    needs: build\n" in "\n" + installer
    assert "\n    needs: [build, installer]\n" in "\n" + manifest


def test_release_asset_builder_works_without_signing_secrets(
    monkeypatch, tmp_path: Path
) -> None:
    from tools import build_release_assets

    windows = tmp_path / "windows"
    linux = tmp_path / "linux"
    for bundle in (windows, linux):
        (bundle / "_internal").mkdir(parents=True)
        (bundle / "_internal" / "runtime.dat").write_bytes(b"runtime")
    (windows / "BudgetManager.exe").write_bytes(b"windows")
    (windows / "BudgetManager_Setup.exe").write_bytes(b"installer")
    (linux / "BudgetManager").write_bytes(b"linux")
    out = tmp_path / "release_assets"

    monkeypatch.delenv("UPDATE_SIGNING_PRIVATE_KEY_B64", raising=False)
    monkeypatch.delenv("UPDATE_SIGNING_PUBLIC_KEY_B64", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        [
            "build_release_assets.py",
            "--version",
            "9.9.9",
            "--release-tag",
            "v9.9.9",
            "--base-url",
            "https://example.invalid/releases/download/v9.9.9",
            "--windows-build-dir",
            str(windows),
            "--linux-build-dir",
            str(linux),
            "--out-dir",
            str(out),
            "--require-installer",
        ],
    )

    assert build_release_assets.main() == 0
    assert (out / "BudgetManager-v9.9.9-portable-windows.zip").is_file()
    assert (out / "BudgetManager-v9.9.9-portable-linux.zip").is_file()
    assert (out / "BudgetManager_Setup_9.9.9.exe").is_file()
    assert (out / "BudgetManager_Setup_9.9.9.zip").is_file()
    assert (out / "latest.json").is_file()
    assert (out / "SHA256SUMS.txt").is_file()
    assert not (out / "latest.json.sig").exists()


def test_updater_self_test_remains_available() -> None:
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "--updater-self-test" in main


def test_find_staged_root_ignores_update_marker(tmp_path: Path) -> None:
    from updater.common import find_staged_root

    payload = tmp_path / "BudgetManager-update"
    payload.mkdir()
    (payload / "main.py").write_text("print('ok')", encoding="utf-8")
    (tmp_path / "_update_marker.json").write_text("{}", encoding="utf-8")
    assert find_staged_root(tmp_path) == payload


def test_updater_e2e_sandbox() -> None:
    from utils.updater_self_test import run_updater_self_test

    assert run_updater_self_test() == 0
