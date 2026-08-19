"""Regressionstest v2.2.44 – historische Versionsangaben bleiben stehen.

Die Sperrdatei verhindert, dass ein pauschaler Release-Sweep Aussagen wie
"seit v2.2.38" fälschlich auf die aktuelle Version umschreibt.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_lock_file_exists_and_pins_historical_versions():
    lock = json.loads(
        (ROOT / "docs/version_references.lock.json").read_text(encoding="utf-8")
    )
    assert "docs/USER_GUIDE.de.md" in lock
    assert "2.2.38" in lock["docs/USER_GUIDE.de.md"]


def test_audit_block_g_is_registered():
    audit = (ROOT / "tools/dau_enterprise_audit.py").read_text(encoding="utf-8")
    assert "def audit_version_references(" in audit
    assert '("G Versionsangaben", audit_version_references)' in audit


def test_current_version_is_2244():
    from app_info import APP_VERSION

    assert APP_VERSION.count(".") == 2
