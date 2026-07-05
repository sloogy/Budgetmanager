"""Statische Regressionen v2.1.4 (Qt-frei).

1. Tabellenbreiten-Bug: utils/table_autosize.py darf den Horizontal-Header
   nicht mehr anfassen. setDefaultSectionSize() dort steuert die
   Standard-SPALTENBREITE und setzte bei jeder Theme-/Schriftänderung alle
   Spalten auf ~Zeilenhöhe zurück; setSectionResizeMode(Interactive)
   überschrieb pro Tabelle konfigurierte Modi.
2. Chart-Theme: CompactChart muss _apply_theme_colors besitzen und in jedem
   create_*-Builder aufrufen (QChart ignoriert Stylesheets).
3. i18n: suggestion.suggestion_initial existiert in de/en/fr und alle drei
   Locales bleiben key-paritätisch.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_table_autosize_does_not_touch_horizontal_header():
    src = _src("utils/table_autosize.py")
    # Kein Zugriff mehr auf horizontalHeader() im Anpassungscode
    assert "horizontalHeader()" not in src
    # Kein globales Überschreiben der ResizeModes
    assert "setSectionResizeMode" not in src
    # Zeilenhöhe (Vertikal-Header) wird weiterhin angepasst
    assert "verticalHeader()" in src
    assert "setDefaultSectionSize" in src


def test_compact_chart_applies_theme_colors_in_every_builder():
    src = _src("views/tabs/overview_widgets.py")
    assert "def _apply_theme_colors" in src
    builders = [
        "create_pie_chart",
        "create_nested_donut",
        "create_line_chart",
        "create_colored_bar_chart",
        "create_grouped_bar_chart",
    ]
    for name in builders:
        m = re.search(
            rf"def {name}\(.*?(?=\n    def |\Z)", src, flags=re.S
        )
        assert m, f"Builder {name} nicht gefunden"
        assert "_apply_theme_colors()" in m.group(0), (
            f"{name} ruft _apply_theme_colors() nicht auf"
        )
    # Hintergrund transparent (Theme scheint durch) + Margins > 0 für Labels
    assert "setBackgroundVisible(False)" in src
    assert "QMargins(4, 4, 4, 4)" in src


def _flat_keys(d, prefix=""):
    out = set()
    for k, v in d.items():
        key = f"{prefix}{k}"
        if isinstance(v, dict):
            out |= _flat_keys(v, key + ".")
        else:
            out.add(key)
    return out


def test_i18n_tracking_learning_keys_present_and_parity():
    keys = {}
    for lang in ("de", "en", "fr"):
        data = json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8"))
        keys[lang] = _flat_keys(data)
        for dotted in (
            "suggestion.suggestion_tracking_projection",
            "suggestion.suggestion_tracking_stable",
            "budget_adjustment.new_budget_label",
        ):
            assert dotted in keys[lang], (lang, dotted)
        for name in ("suggestion_tracking_projection", "suggestion_tracking_stable"):
            node = data["suggestion"][name]
            for ph in ("{typ}", "{cat}", "{n}", "{suggested}"):
                assert ph in node, (lang, name, ph)
    assert keys["de"] == keys["en"] == keys["fr"]


def test_tracking_learning_messages_are_not_hardcoded():
    src = _src("model/budget_overview_model.py")
    assert "suggestion.suggestion_tracking_projection" in src
    assert "suggestion.suggestion_tracking_stable" in src
    assert "stabiler Lernvorschlag aus" not in src
    dlg = _src("views/budget_adjustment_dialog.py")
    assert "budget_adjustment.new_budget_label" in dlg
    assert 'QTableWidgetItem("neu")' not in dlg
