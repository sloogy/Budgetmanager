from __future__ import annotations

from pathlib import Path

import pytest

from tools.build_legacy_trust_bridge import render_bridge


PUBLIC_KEY = "5h/BG69V39sdDd9bz120pA+SB+mCtlB++1qH3B2vUQY="


def test_bridge_writes_key_to_path_supported_by_v2261() -> None:
    script = render_bridge(PUBLIC_KEY)
    assert "_internal\\resources" in script
    assert "update_signing_public_key.b64" in script
    assert PUBLIC_KEY in script
    assert "--check-update" in script
    assert "--gui" in script


def test_bridge_refuses_to_overwrite_different_trust_anchor() -> None:
    script = render_bridge(PUBLIC_KEY)
    assert "bereits ein anderer Update-Public-Key" in script
    assert "nicht ueberschrieben" in script


def test_bridge_never_contains_private_signing_key_variable() -> None:
    script = render_bridge(PUBLIC_KEY)
    assert "UPDATE_SIGNING_PRIVATE_KEY_B64" not in script


def test_invalid_public_key_is_rejected() -> None:
    with pytest.raises(SystemExit):
        render_bridge("not-base64")


def test_release_workflow_publishes_bridge_asset() -> None:
    workflow = Path(".github/workflows/build.yml").read_text(encoding="utf-8")
    assert "Build one-time v2.2.61 trust bridge" in workflow
    assert "BudgetManager-v2.2.61-Trust-Bridge.ps1" in workflow
    assert (
        "UPDATE_SIGNING_PUBLIC_KEY_B64: ${{ vars.UPDATE_SIGNING_PUBLIC_KEY_B64 }}"
        in workflow
    )
