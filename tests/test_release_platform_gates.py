"""Release-Regressionsschutz für Plattform-, Installer- und CVE-Gates."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_platform_workflow_covers_fedora_wayland_windows_and_accessibility() -> None:
    workflow = (ROOT / ".github/workflows/platform-release-gates.yml").read_text(
        encoding="utf-8"
    )
    for marker in (
        'fedora: ["42", "latest"]',
        "container: fedora:${{ matrix.fedora }}",
        "QT_QPA_PLATFORM=wayland",
        "BM_ALLOW_WAYLAND=1",
        'scale: ["1.0", "1.25", "1.5", "2.0"]',
        "windows-latest",
        'QT_QPA_PLATFORM = "windows"',
        "QT_LINUX_ACCESSIBILITY_ALWAYS_ON",
        "--release-self-test",
    ):
        assert marker in workflow


def test_installer_workflow_performs_real_silent_e2e() -> None:
    workflow = (ROOT / ".github/workflows/build.yml").read_text(encoding="utf-8")
    for marker in (
        "Silent install, launch and uninstall E2E",
        "/VERYSILENT",
        "/DATA_DIR=",
        "BudgetManager.exe",
        "--release-self-test",
        "unins*.exe",
    ):
        assert marker in workflow


def test_online_dependency_audit_and_dependabot_are_mandatory() -> None:
    workflow = (ROOT / ".github/workflows/dependency-audit.yml").read_text(
        encoding="utf-8"
    )
    dependabot = (ROOT / ".github/dependabot.yml").read_text(encoding="utf-8")
    dev_input = (ROOT / "requirements-dev.in").read_text(encoding="utf-8")
    dev_lock = (ROOT / "requirements-dev.lock").read_text(encoding="utf-8")
    assert "pip-audit==2.10.1" in dev_input
    assert "pip_audit==2.10.1" in dev_lock
    assert "--require-hashes -r requirements-dev.lock" in workflow
    assert "--requirement requirements.lock" in workflow
    assert "PIP_AUDIT_ONLINE.json" in workflow
    assert 'package-ecosystem: "pip"' in dependabot
    assert 'package-ecosystem: "github-actions"' in dependabot


def test_updater_self_test_is_wired_into_source_and_installed_build() -> None:
    root = Path(__file__).resolve().parents[1]
    main = (root / "main.py").read_text(encoding="utf-8")
    platform_workflow = (
        root / ".github/workflows/platform-release-gates.yml"
    ).read_text(encoding="utf-8")
    build_workflow = (root / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "--updater-self-test" in main
    assert "--updater-self-test" in platform_workflow
    assert "& $exe --updater-self-test" in build_workflow


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


def test_tag_build_is_blocked_by_platform_dependency_and_10000_loop_gates() -> None:
    root = Path(__file__).resolve().parents[1]
    platform = (root / ".github/workflows/platform-release-gates.yml").read_text(
        encoding="utf-8"
    )
    dependency = (root / ".github/workflows/dependency-audit.yml").read_text(
        encoding="utf-8"
    )
    build = (root / ".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "workflow_call:" in platform
    assert "workflow_call:" in dependency
    assert "uses: ./.github/workflows/platform-release-gates.yml" in build
    assert "uses: ./.github/workflows/dependency-audit.yml" in build
    assert (
        "needs: [platform-release-gates, dependency-security-gate, "
        "enterprise-release-audit-10000, killcritic-usability-audit-10000]"
    ) in build
