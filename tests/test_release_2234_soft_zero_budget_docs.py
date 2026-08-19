"""Regressionstests v2.2.35 – Soft-0-Budget ist auffindbar und erklärt."""

from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_setting_names_soft_zero_budget_in_all_languages():
    expected = {
        "de": "Soft-0-Budget",
        "en": "Soft Zero Budget",
        "fr": "budget zéro souple",
    }
    for lang, needle in expected.items():
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        text = data["settings"]["zero_balance_rule"]
        assert needle.lower() in text.lower()
        assert data["settings"]["zero_balance_rule_summary"].strip()
        assert data["settings"]["zero_balance_open_help"].strip()


def test_settings_dialog_has_visible_summary_and_direct_help_button():
    src = (ROOT / "settings_dialog.py").read_text(encoding="utf-8")
    assert 'start_topic_id="soft-zero-budget"' in src
    assert "settings.zero_balance_rule_summary" in src
    assert "settings.zero_balance_open_help" in src


def test_in_app_help_has_dedicated_searchable_topic_and_core_rules():
    src = (ROOT / "views" / "help_content.py").read_text(encoding="utf-8")
    assert '"id": "soft-zero-budget"' in src
    for term in (
        "Einnahmen − Ausgaben − Ersparnisse",
        "Fixkosten",
        "POT/Rückstellungen",
        "Tracking-Lernmodus",
        "5’000 CHF",
    ):
        assert term in src


def test_user_guides_and_static_help_cover_soft_zero_budget():
    files = [
        ROOT / "docs" / "USER_GUIDE.de.md",
        ROOT / "docs" / "USER_GUIDE.en.md",
        ROOT / "docs" / "USER_GUIDE.fr.md",
        ROOT / "docs" / "help" / "index.html",
        ROOT / "docs" / "SOFT_ZERO_BUDGET.de.md",
        ROOT / "docs" / "SOFT_ZERO_BUDGET.en.md",
        ROOT / "docs" / "SOFT_ZERO_BUDGET.fr.md",
    ]
    for path in files:
        assert path.exists(), path
        assert len(path.read_text(encoding="utf-8")) > 300
