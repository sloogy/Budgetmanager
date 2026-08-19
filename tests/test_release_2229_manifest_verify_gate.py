"""Regressionstests v2.2.29 (RELEASE_GATE_RESYNC).

Sichert Befund 1 des Enterprise-Audits v2.2.28 ab: Der Workflow-Step
"Verify updater manifest stays updater-safe" war beim Merge im Build-Step
aufgegangen; tools/release_logic_audit_100.py schlug dadurch fehl und die
explizite Nach-Build-Verifikation des GENERIERTEN latest.json entfiel.

Abgesichert wird:
1. Werkzeug tools/verify_release_manifest.py existiert und ist im Workflow
   unter dem historischen Step-Namen verdrahtet (nach dem Build-Step).
2. Das Audit pinnt beide Step-Namen UND den Werkzeug-Aufruf.
3. Das Gate akzeptiert einen vertragskonformen Manifest-Aufbau (wie ihn
   tools/build_release_assets._write_latest_json erzeugt) und lehnt jede
   bekannte Verletzung fail-closed ab.
4. Signaturpfad: fehlende/leere Signaturdatei => FAIL; gültige Ed25519-
   Signatur mit Public Key aus Env => PASS; manipulierte Signatur => FAIL.
"""

from __future__ import annotations

import base64
import copy
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.verify_release_manifest import (  # noqa: E402
    ManifestGateError,
    main as gate_main,
    verify_manifest_dict,
)

WORKFLOW = ROOT / ".github" / "workflows" / "build.yml"
AUDIT = ROOT / "tools" / "release_logic_audit_100.py"
STEP_NAME = "Verify updater manifest stays updater-safe"
BUILD_STEP_NAME = "Build signed release assets, updater manifest and SBOM"
TOOL_CALL = "tools/verify_release_manifest.py"


def _asset(url_suffix: str, a_type: str) -> dict:
    return {
        "type": a_type,
        "url": f"https://example.invalid/download/v9.9.9/{url_suffix}",
        "sha256": "ab" * 32,
    }


def _good_manifest() -> dict:
    return {
        "app": "Budgetmanager",
        "channel": "stable",
        "version": "9.9.9",
        "release_tag": "v9.9.9",
        "assets": {
            "windows": _asset(
                "BudgetManager-v9.9.9-portable-windows.zip", "portable-zip"
            ),
            "linux": _asset("BudgetManager-v9.9.9-portable-linux.zip", "portable-zip"),
            "portable_windows_zip": _asset(
                "BudgetManager-v9.9.9-portable-windows.zip", "portable-zip"
            ),
            "portable_linux_zip": _asset(
                "BudgetManager-v9.9.9-portable-linux.zip", "portable-zip"
            ),
            "portable_zip": _asset(
                "BudgetManager-v9.9.9-portable-windows.zip", "portable-zip"
            ),
            "windows_installer": _asset("BudgetManager_Setup_9.9.9.exe", "installer"),
            "windows_installer_zip": _asset(
                "BudgetManager_Setup_9.9.9.zip", "installer-zip"
            ),
        },
    }


def _expect_fail(manifest: dict, fragment: str) -> None:
    try:
        verify_manifest_dict(manifest)
    except ManifestGateError as exc:
        assert fragment in str(exc), (fragment, str(exc))
        return
    raise AssertionError(f"Gate hätte ablehnen müssen: {fragment}")


# ── 1) Verdrahtung im Workflow ───────────────────────────────────────────


def test_workflow_has_explicit_manifest_verify_step() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert STEP_NAME in text
    assert TOOL_CALL in text
    # Der Verifikations-Step läuft NACH dem Build-Step (Reihenfolge im YAML).
    assert text.index(BUILD_STEP_NAME) < text.index(STEP_NAME)
    # Der Step ruft das Gate mit dem generierten Manifest UND der Signatur auf.
    step_block = text[text.index(STEP_NAME) :]
    assert "release_assets/latest.json" in step_block
    assert "--signature release_assets/latest.json.sig" in step_block


def test_release_logic_audit_pins_both_step_names_and_tool() -> None:
    text = AUDIT.read_text(encoding="utf-8")
    assert f'"{STEP_NAME}"' in text
    assert f'"{BUILD_STEP_NAME}"' in text
    assert f'"{TOOL_CALL}"' in text


def test_gate_tool_exists_and_compiles() -> None:
    path = ROOT / "tools" / "verify_release_manifest.py"
    assert path.is_file()
    compile(path.read_text(encoding="utf-8"), str(path), "exec")


# ── 2) Vertragskonformes Manifest passiert ───────────────────────────────


def test_good_manifest_passes() -> None:
    verify_manifest_dict(_good_manifest())


def test_good_manifest_without_optional_installer_passes() -> None:
    m = _good_manifest()
    del m["assets"]["windows_installer"]
    del m["assets"]["windows_installer_zip"]
    verify_manifest_dict(m)


# ── 3) Bekannte Verletzungen werden fail-closed abgelehnt ────────────────


def test_direct_binary_keys_rejected() -> None:
    for bad in ("direct_windows_exe", "direct_linux_binary"):
        m = _good_manifest()
        m["assets"][bad] = _asset("BudgetManager.exe", "exe")
        _expect_fail(m, bad)


def test_wrong_platform_type_rejected() -> None:
    m = _good_manifest()
    m["assets"]["windows"]["type"] = "exe"
    _expect_fail(m, "'windows'")


def test_installer_type_must_stay_installer() -> None:
    # updater.check_update behandelt nur type=="installer" als Setup-EXE.
    m = _good_manifest()
    m["assets"]["windows_installer"]["type"] = "portable-zip"
    _expect_fail(m, "windows_installer")


def test_wrong_url_suffix_rejected() -> None:
    m = _good_manifest()
    m["assets"]["linux"]["url"] = "https://example.invalid/BudgetManager.exe"
    _expect_fail(m, "portable-linux.zip")


def test_non_https_url_rejected() -> None:
    m = _good_manifest()
    m["assets"]["windows"]["url"] = m["assets"]["windows"]["url"].replace(
        "https://", "http://"
    )
    _expect_fail(m, "https")


def test_invalid_sha256_rejected() -> None:
    m = _good_manifest()
    m["assets"]["windows"]["sha256"] = "nicht-hex"
    _expect_fail(m, "sha256")


def test_missing_required_asset_rejected() -> None:
    m = _good_manifest()
    del m["assets"]["linux"]
    _expect_fail(m, "'linux'")


def test_unknown_asset_key_rejected() -> None:
    m = _good_manifest()
    m["assets"]["mystery_blob"] = _asset("x.zip", "portable-zip")
    _expect_fail(m, "mystery_blob")


def test_missing_required_fields_rejected() -> None:
    for field in ("app", "channel", "version", "release_tag"):
        m = _good_manifest()
        m[field] = ""
        _expect_fail(m, field)


# ── 4) CLI + Signaturpfad ────────────────────────────────────────────────


def _write_manifest(tmp_path: Path, manifest: dict) -> Path:
    p = tmp_path / "latest.json"
    p.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return p


def test_cli_pass_and_fail(tmp_path, capsys) -> None:
    good = _write_manifest(tmp_path, _good_manifest())
    assert gate_main([str(good)]) == 0
    out = capsys.readouterr().out
    assert "BESTANDEN" in out

    bad_manifest = _good_manifest()
    bad_manifest["assets"]["direct_windows_exe"] = _asset("a.exe", "exe")
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(bad_manifest), encoding="utf-8")
    assert gate_main([str(bad)]) == 1
    err = capsys.readouterr().err
    assert "FEHLGESCHLAGEN" in err


def test_cli_missing_manifest_fails(tmp_path, capsys) -> None:
    assert gate_main([str(tmp_path / "fehlt.json")]) == 1
    assert "FEHLGESCHLAGEN" in capsys.readouterr().err


def test_cli_signature_required_when_flag_given(tmp_path, capsys) -> None:
    good = _write_manifest(tmp_path, _good_manifest())
    missing_sig = tmp_path / "latest.json.sig"
    assert gate_main([str(good), "--signature", str(missing_sig)]) == 1
    assert "Signaturdatei" in capsys.readouterr().err
    # Leere Signaturdatei ist ebenso ungültig.
    missing_sig.write_bytes(b"")
    assert gate_main([str(good), "--signature", str(missing_sig)]) == 1


def test_cli_valid_ed25519_signature_passes(tmp_path, monkeypatch, capsys) -> None:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    from cryptography.hazmat.primitives.serialization import (
        Encoding,
        PrivateFormat,
        PublicFormat,
        NoEncryption,
    )

    good = _write_manifest(tmp_path, _good_manifest())
    key = Ed25519PrivateKey.generate()
    signature = key.sign(good.read_bytes())
    sig_path = tmp_path / "latest.json.sig"
    sig_path.write_bytes(base64.b64encode(signature))
    pub_b64 = base64.b64encode(
        key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    ).decode("ascii")
    monkeypatch.setenv("UPDATE_SIGNING_PUBLIC_KEY_B64", pub_b64)

    assert gate_main([str(good), "--signature", str(sig_path)]) == 0
    assert "Ed25519" in capsys.readouterr().out

    # Manipuliertes Manifest bei gleicher Signatur => FAIL.
    tampered = copy.deepcopy(_good_manifest())
    tampered["version"] = "6.6.6"
    good.write_text(json.dumps(tampered), encoding="utf-8")
    assert gate_main([str(good), "--signature", str(sig_path)]) == 1
    assert "ungültig" in capsys.readouterr().err

    # Serialisierungs-Sanity: PrivateFormat/NoEncryption importiert lassen,
    # damit zukünftige Erweiterungen (Key-Dump-Tests) hier andocken können.
    assert PrivateFormat.Raw is not None and NoEncryption is not None


def test_cli_env_key_must_be_valid_base64(tmp_path, monkeypatch, capsys) -> None:
    good = _write_manifest(tmp_path, _good_manifest())
    sig_path = tmp_path / "latest.json.sig"
    sig_path.write_bytes(base64.b64encode(b"x" * 64))
    monkeypatch.setenv("UPDATE_SIGNING_PUBLIC_KEY_B64", "kein-base64!!")
    assert gate_main([str(good), "--signature", str(sig_path)]) == 1
    assert "Key" in capsys.readouterr().err
