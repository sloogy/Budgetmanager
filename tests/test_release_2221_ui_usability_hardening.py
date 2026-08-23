from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_global_ui_usability_filter_is_installed():
    main = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "install_ui_usability(app)" in main
    utility = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
    assert "setAccessibleName" in utility
    assert "setAccessibleDescription" in utility
    assert "setAutoDefault(False)" in utility
    # Seit Loop 56 vollqualifiziert: In Qt6 gehoert ein Enum in seinen
    # Namensraum, und nur so ist es typisiert. Der Wert ist derselbe.
    assert "QEvent.Type.Show" in utility


def test_cockpit_has_three_density_presets():
    source = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    for preset in ("focus", "standard", "analysis"):
        assert f'"{preset}"' in source
    assert "cockpit_preset" in source
    assert "COCKPIT_PRESETS" in source


def test_focus_preset_reduces_visual_density():
    # v2.2.22: Presets leben zentral und Qt-frei in utils/cockpit_presets.py –
    # funktional pruefen statt Quelltextblock parsen.
    import sys

    sys.path.insert(0, str(ROOT))
    from utils.cockpit_presets import PRESETS

    focus = PRESETS["focus"]
    assert focus["quick_actions"] is True
    # v2.2.40: warnings/budget_warnings/missing sind ein Abschnitt.
    assert focus["action_needed"] is True
    assert focus["favorites"] is False
    assert focus["recent"] is False
    assert focus["recent"] is False
    assert sum(focus.values()) < sum(PRESETS["standard"].values())


def test_accessibility_i18n_keys_have_parity():
    import json

    locale_data = {
        lang: json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        for lang in ("de", "en", "fr")
    }
    keys = {
        "cockpit.preset_tip",
        "cockpit.preset_accessible",
        "cockpit.preset_focus",
        "cockpit.preset_standard",
        "cockpit.preset_analysis",
    }
    for key in keys:
        assert all(key in locale_data[lang] for lang in locale_data)


def test_existing_custom_cockpit_layout_is_not_overwritten():
    settings_source = (ROOT / "settings.py").read_text(encoding="utf-8")
    assert 'if "cockpit_preset" not in loaded' in settings_source
    assert 'merged["cockpit_preset"] = "custom"' in settings_source
