"""v2.2.22 – Enterprise-UI-/Usability-/ADHS-Audit: Findings und Absicherung.

Vorher-Lauf von tools/ui_adhs_audit_1000.py auf v2.2.21: 252 Findings.
Behoben wurden:

F1  Screenreader-Hinweis für Tabellen/Listen war hartkodiert deutsch
    (Bruch der de=en=fr-Regel) → i18n-Key ``a11y.itemview_hint``.
F2  Der Show-Eventfilter lief bei JEDEM Show über den ganzen Widgetbaum
    (auch Combo-Popups/Menüs) → Einmal-Marker ``_bm_ui_enhanced`` +
    Popup-/Menü-Skip.
F3  Destruktiv-Erkennung: Substring-Matching und Lücken in der Wortliste
    (``réinitialiser``/``retirer``/``clear``/``verwerfen`` fehlten; "Preset"
    hätte über "reset" gematcht) → Qt-freie ``is_destructive_text`` mit
    Wortgrenzen (utils/ui_text_rules.py).
F4  Fokus-Timer konnte auf bereits zerstörten Dialog feuern →
    RuntimeError-Guard + Sichtbarkeitsprüfung.
F5  Neuinstallation startete NICHT im Fokus-Preset: die v2014-Migration
    materialisierte im Konstruktor die ALL-TRUE-Defaults; die Preset-Combo
    zeigte "Fokus", sichtbar war alles → utils/cockpit_presets.py als eine
    Wahrheit; Migration nur noch für custom-Bestand.
F6  Panel-Toggle im Fokus-Modus mischte die ALL-TRUE-Basis ein (ein Klick
    liess alle Panels aufpoppen) → Basis ist der wirksame Zustand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from utils.ui_text_rules import is_destructive_text  # noqa: E402
from utils import cockpit_presets as cp  # noqa: E402


class _MemSettings:
    def __init__(self, initial=None):
        self.d = dict(initial or {})

    def get(self, k, default=None):
        return self.d.get(k, default)

    def set(self, k, v):
        self.d[k] = v


# ── F3: Destruktiv-Erkennung (Qt-frei, Golden-Set) ─────────────────────────
def test_destructive_detection_covers_three_languages():
    for text in (
        "Löschen",
        "Zurücksetzen…",
        "Verwerfen",
        "Delete",
        "Clear list",
        "Discard changes",
        "Supprimer",
        "Réinitialiser",
        "Retirer",
        "Vider la liste",
    ):
        assert is_destructive_text(text), text


def test_destructive_detection_has_no_substring_false_positives():
    for text in (
        "Preset speichern",
        "Apply preset",
        "Préréglages",
        "Speichern",
        "Exportieren",
        "Wiederherstellen",
        "OK",
    ):
        assert not is_destructive_text(text), text


def test_ui_usability_reuses_qt_free_rules():
    src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
    assert "from utils.ui_text_rules import" in src
    # keine zweite Wortliste im Qt-Modul
    assert src.count("_DESTRUCTIVE_WORDS = {") == 0


# ── F1: lokalisierter A11y-Hinweis ─────────────────────────────────────────
def test_itemview_hint_key_exists_in_all_locales():
    for lang in ("de", "en", "fr"):
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        assert data.get("a11y", {}).get("itemview_hint"), lang


def test_no_hardcoded_german_a11y_sentence():
    src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
    assert "Mit Pfeiltasten navigieren" not in src
    assert "a11y.itemview_hint" in src


# ── F2/F4: Filter-Hygiene ─────────────────────────────────────────────────
def test_filter_has_marker_popup_skip_and_safe_timer():
    src = (ROOT / "utils" / "ui_usability.py").read_text(encoding="utf-8")
    assert "_bm_ui_enhanced" in src, "Einmal-Marker fehlt"
    assert "_is_transient_window" in src and "Popup" in src, "Popup-Skip fehlt"
    assert "except RuntimeError" in src, "zerstörungssicherer Timer fehlt"
    assert "isVisible()" in src


# ── F5/F6: Preset-Logik (echte Läufe) ─────────────────────────────────────
def test_fresh_install_really_starts_in_focus():
    s = _MemSettings({"cockpit_preset": "focus"})
    cp.materialize_initial(s)
    cp.migrate_v2014(s)
    assert cp.effective_panels(s) == cp.PRESETS["focus"]
    assert s.get("cockpit_preset") == "focus"


def test_existing_custom_layout_is_never_touched():
    own = {k: (i % 2 == 0) for i, k in enumerate(cp.PANEL_KEYS)}
    s = _MemSettings(
        {
            "cockpit_visible_panels": dict(own),
            "cockpit_preset": "custom",
            "cockpit_warnings_visible_migrated_v2014": True,
        }
    )
    cp.materialize_initial(s)
    assert s.get("cockpit_visible_panels") == own


def test_legacy_user_without_preset_keeps_all_panels():
    s = _MemSettings({"cockpit_preset": "custom"})
    cp.materialize_initial(s)
    assert all(cp.effective_panels(s).values())


def test_toggle_in_focus_changes_exactly_one_panel():
    s = _MemSettings({"cockpit_preset": "focus"})
    cp.materialize_initial(s)
    before = cp.effective_panels(s)
    cp.set_panel(s, "favorites", not before["favorites"])
    after = cp.effective_panels(s)
    changed = [k for k in cp.PANEL_KEYS if before[k] != after[k]]
    assert changed == ["favorites"]
    assert s.get("cockpit_preset") == "custom"


def test_v2014_migration_never_flips_a_preset():
    s = _MemSettings({"cockpit_preset": "focus"})
    cp.materialize_initial(s)
    cp.migrate_v2014(s)
    assert cp.effective_panels(s)["recent"] is False


def test_v2014_migration_still_helps_custom_users():
    s = _MemSettings(
        {
            "cockpit_preset": "custom",
            "cockpit_visible_panels": {k: False for k in cp.PANEL_KEYS},
        }
    )
    cp.migrate_v2014(s)
    eff = cp.effective_panels(s)
    assert eff["action_needed"] and not eff["kpis"]


def test_settings_default_equals_focus_preset():
    src = (ROOT / "settings.py").read_text(encoding="utf-8")
    assert 'dict(_COCKPIT_PRESETS["focus"])' in src
    assert "from utils.cockpit_presets import PRESETS" in src


def test_cockpit_tab_delegates_to_central_logic():
    src = (ROOT / "views" / "tabs" / "cockpit_tab.py").read_text(encoding="utf-8")
    assert "COCKPIT_PRESETS = _cp.PRESETS" in src
    assert "_cp.materialize_initial(self.settings)" in src
    assert "_cp.migrate_v2014(self.settings)" in src
    assert "_cp.effective_panels(self.settings)" in src
    assert "_cp.set_panel(self.settings" in src
    # der alte ALL-TRUE-Merge darf nicht zurückkehren
    assert "{**self.PANEL_DEFAULTS, **cfg}" not in src


# ── Werkzeug ist Teil der Batterie ────────────────────────────────────────
def test_ui_audit_tool_present_with_all_domains():
    tool = ROOT / "tools" / "ui_adhs_audit_1000.py"
    assert tool.is_file()
    src = tool.read_text(encoding="utf-8")
    for dom in (
        "d1_destructive",
        "d2_a11y_i18n",
        "d3_filter_hygiene",
        "d5_cockpit_presets",
        "d6_placeholders",
        "d7_refs",
        "d8_scaling",
        "d9_icon_buttons",
        "d10_enter_defaults",
    ):
        assert dom in src, dom
