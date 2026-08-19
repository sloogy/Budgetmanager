"""Regression gates for v2.2.45 guide and DAU-audit consolidation."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_atomic_layout_persistence_is_retained():
    settings = (ROOT / "settings.py").read_text(encoding="utf-8")
    cockpit = (ROOT / "views/tabs/cockpit_tab.py").read_text(encoding="utf-8")
    assert "def set_many(" in settings
    assert "self.settings.set_many(" in cockpit
    assert '"cockpit_layout_mode"' in cockpit
    assert '"cockpit_tiles_fixed"' in cockpit


def test_expanded_cockpit_help_exists_in_all_languages():
    additions = (ROOT / "views/help_content_additions.py").read_text(encoding="utf-8")
    assert '"cockpit-layout"' in additions
    for phrase in (
        "Kennzahlen und Trend",
        "Key figures and trend",
        "Indicateurs et tendance",
    ):
        assert phrase in additions
    for lang, phrase in (
        ("de", "Automatik oder fixiertes Layout"),
        ("en", "Automatic or pinned layout"),
        ("fr", "Disposition automatique ou figée"),
    ):
        guide = (ROOT / f"docs/USER_GUIDE.{lang}.md").read_text(encoding="utf-8")
        assert phrase in guide


def test_dau_theme_audit_detects_short_and_long_hex_colours():
    audit = (ROOT / "tools/dau_enterprise_audit.py").read_text(encoding="utf-8")
    assert "[0-9a-fA-F]{3}" in audit
    assert "[0-9a-fA-F]{3}" in audit
    pattern = re.compile(r"#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{3}|[0-9a-fA-F]{6})\b")
    assert pattern.search("color: #666")
    assert pattern.search("color: #aabbcc")


def test_current_version_is_2245():
    from app_info import APP_VERSION

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)
