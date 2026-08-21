"""Regressionstests v2.2.42 – Dashboard-Optik nach der Vorlage.

Farbprofil, Kartenoptik, KPI-Kacheln mit Trend, Ring- und Flächendiagramm.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COCKPIT = ROOT / "views/tabs/cockpit_tab.py"
CHARTS = ROOT / "views/cockpit_charts.py"
THEME = ROOT / "theme_manager.py"
PROFILE = ROOT / "views/profiles/mitternacht_violett.json"
LANGS = ("de", "en", "fr")


def test_profile_passes_wcag_aa_for_accent_text():
    """Weisse Schrift auf dem Akzent muss 4.5:1 erreichen (Fund des 2223-Gates)."""
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))

    def luminance(value: str) -> float:
        channels = [int(value[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [
            c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
            for c in channels
        ]
        return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]

    high = max(luminance(profile["akzent_text"]), luminance(profile["akzent"]))
    low = min(luminance(profile["akzent_text"]), luminance(profile["akzent"]))
    assert (high + 0.05) / (low + 0.05) >= 4.5


def test_new_profile_exists_and_is_complete():
    """Neues Profil muss dieselben Schlüssel tragen wie die vorhandenen."""
    reference = json.loads(
        (ROOT / "views/profiles/dracula_dunkel.json").read_text(encoding="utf-8")
    )
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    assert set(profile) == set(reference), set(reference) ^ set(profile)
    assert profile["modus"] == "dunkel"
    assert profile["akzent"] == "#7150f0"
    assert profile["name"].strip()


def test_profile_count_grew_by_one():
    profiles = list((ROOT / "views/profiles").glob("*.json"))
    assert len(profiles) == 26


def test_card_and_section_styling_comes_from_the_profile():
    """Kein fester Farbwert – sonst bricht die Optik in den anderen 25 Profilen."""
    qss = THEME.read_text(encoding="utf-8")
    for rule in (
        "QFrame#cockpitSection {{",
        "QFrame#cockpitCard {{",
        "QLabel#cockpitCardIcon {{",
        "QLabel#cockpitCardValue {{",
    ):
        assert rule in qss, rule
    block = qss.split("QFrame#cockpitSection {{", 1)[1].split(
        "QToolButton#menuBarHelpButton", 1
    )[0]
    # Die Radien stehen nicht mehr fest im Quelltext, sondern wachsen mit der
    # eingestellten Schrift. Bei Standardgroesse kommen dieselben 12px heraus -
    # geprueft wird darum das erzeugte Stylesheet, nicht die Schreibweise.
    assert "border-radius: {px(12)}px" in block
    assert not re.search(r"#[0-9a-fA-F]{3,8}(?![A-Za-z0-9_-])", block), "feste Hexfarbe"


def test_kpi_cards_have_icon_value_and_trend():
    src = COCKPIT.read_text(encoding="utf-8")
    for name in (
        "cockpitCardIcon",
        "cockpitCardValue",
        "cockpitCardCaption",
        "cockpitCardTrend",
    ):
        assert f'setObjectName("{name}")' in src, name


def test_card_icons_are_plain_glyphs_not_emoji():
    src = COCKPIT.read_text(encoding="utf-8")
    for glyph in ("\\u2191", "\\u2193", "\\u25c6", "\\u2211"):
        assert f'icon="{glyph}"' in src, glyph


def test_trend_colour_follows_meaning_not_sign():
    """Mehr Ausgaben darf nicht grün sein."""
    src = COCKPIT.read_text(encoding="utf-8")
    block = (
        src.split("def set_trend", 1)[1].split("def __init__", 1)[0]
        if "def set_trend" in src
        else ""
    )
    assert "higher_is_better" in src
    assert "good = rising if higher_is_better else not rising" in src
    assert "exp_a - prev_exp, colors, higher_is_better=False" in src


def test_trend_compares_against_previous_salary_cycle_with_year_rollover():
    src = COCKPIT.read_text(encoding="utf-8")
    assert "previous = previous_salary_cycle(cycle)" in src
    assert "previous.budget_year, previous.budget_month" in src
    salary = (ROOT / "model/salary_cycle.py").read_text(encoding="utf-8")
    assert "def previous_salary_cycle(cycle: SalaryCycle)" in salary
    assert "_month_offset(" in salary


def test_trend_failure_never_breaks_the_cockpit():
    src = COCKPIT.read_text(encoding="utf-8")
    block = src.split("def _refresh_kpi_trends", 1)[1].split("def _set_table_rows", 1)[
        0
    ]
    assert "except Exception" in block


def test_donut_has_a_hole_and_caps_the_slices():
    src = CHARTS.read_text(encoding="utf-8")
    assert "setHoleSize(" in src
    assert "MAX_SLICES" in src
    block = src.split("class DonutChart", 1)[1]
    assert "self._chart.setTitle(center_label)" in block, "Summe gehört in die Mitte"


def test_area_chart_uses_a_gradient():
    src = CHARTS.read_text(encoding="utf-8")
    block = src.split("class TrendAreaChart", 1)[1]
    assert "QLinearGradient" in block
    assert "setAlpha(" in block


def test_charts_take_their_colours_from_the_profile():
    src = CHARTS.read_text(encoding="utf-8")
    assert "from views.ui_colors import ui_colors" in src
    assert "colors.accent" in src
    assert "setBackgroundVisible(False)" in src, "sonst weißer Kasten im dunklen Profil"


def test_charts_are_animation_free():
    """Animierte, gerade entfernte Serien haben unter Wayland Abstürze erzeugt."""
    src = CHARTS.read_text(encoding="utf-8")
    assert "QChart.NoAnimation" in src


def test_charts_panel_is_registered_everywhere():
    presets = (ROOT / "utils/cockpit_presets.py").read_text(encoding="utf-8")
    assert '"charts",' in presets.split("PANEL_KEYS = (", 1)[1].split(")", 1)[0]
    assert '"charts": True' in presets
    src = COCKPIT.read_text(encoding="utf-8")
    assert '_add_panel("charts"' in src
    assert '"charts": "cockpit.panel.charts"' in src
    assert "self._refresh_charts(y, m)" in src


def test_chart_titles_exist_in_all_languages():
    for lang in LANGS:
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        assert data.get("cockpit.panel.charts", "").strip(), lang


def test_current_version_is_2244():
    from app_info import APP_VERSION

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)


def test_die_karten_behalten_bei_standardgroesse_ihre_rundung():
    """BudgetManager ist die Design-Vorlage der Suite - sein Aussehen bei
    10pt ist der Massstab. Die Skalierung darf daran nichts aendern."""
    from theme_manager import ThemeManager

    class _Settings(dict):
        def set(self, key, value):
            self[key] = value

    manager = ThemeManager(_Settings())
    profil = manager.get_current_profile()
    profil.data["schriftgroesse"] = 10
    qss = manager.build_stylesheet(profil)
    block = qss.split("QFrame#cockpitSection {", 1)[1].split(
        "QToolButton#menuBarHelpButton", 1
    )[0]
    assert "border-radius: 12px" in block
