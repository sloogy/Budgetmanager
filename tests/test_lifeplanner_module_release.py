from __future__ import annotations

import base64
import json
import subprocess
import sys
import zipfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
)

ROOT = Path(__file__).resolve().parents[1]


def _private_key_b64() -> str:
    raw = Ed25519PrivateKey.generate().private_bytes(
        Encoding.Raw, PrivateFormat.Raw, NoEncryption()
    )
    return base64.b64encode(raw).decode("ascii")


def test_signed_dual_platform_builder_emits_checksum(tmp_path, monkeypatch) -> None:
    runtime = tmp_path / "dist" / "BudgetManager"
    runtime.mkdir(parents=True)
    (runtime / "BudgetManager.exe").write_bytes(b"MZ-test")
    output = tmp_path / "budgetmanager_2.2.60_Windows_x86_64.lpmodule"
    monkeypatch.setenv("LIFEPLANNER_UPDATE_PRIVATE_KEY_B64", _private_key_b64())
    subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools/build_lifeplanner_module.py"),
            "--runtime-dir",
            str(runtime),
            "--runtime-name",
            "BudgetManager",
            "--platform",
            "windows-x86_64",
            "--output",
            str(output),
        ],
        check=True,
        cwd=ROOT,
    )
    checksum = output.with_suffix(output.suffix + ".sha256")
    assert output.is_file() and checksum.is_file()
    with zipfile.ZipFile(output) as archive:
        assert "component.json.sig" in archive.namelist()
        assert "payload/module.json" in archive.namelist()
        metadata = json.loads(archive.read("component.json"))
    assert metadata["id"] == "budgetmanager"
    assert metadata["platforms"] == ["windows-x86_64"]
    assert metadata["version"] == "2.2.60"


def test_budgetmanager_tag_does_not_publish_lifeplanner_module_assets() -> None:
    workflows = ROOT / ".github" / "workflows"
    assert not (workflows / "lifeplanner-module-release.yml").exists()
    assert not (workflows / "lifeplanner-contract.yml").exists()

    workflow = (workflows / "build.yml").read_text(encoding="utf-8")
    assert "BudgetManager-v${VERSION}-portable" not in workflow
    assert ".lpmodule" not in workflow
    assert "LIFEPLANNER_UPDATE_PRIVATE_KEY_B64" not in workflow
