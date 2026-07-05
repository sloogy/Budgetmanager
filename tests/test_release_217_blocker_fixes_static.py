"""Statische Regressionen v2.1.7 (Qt-frei): Release-Blocker-Fixes.

1. Erststart: Bei aktivem Lernmodus darf der Budget-Ausfüllschritt nicht
   blockieren ("erst tracken, Budget später lernen") – der Setup-Assistent
   wertet die Lernmodus-Checkbox in _recompute_budget_done aus und zeigt
   einen eigenen Hinweistext.
2. Übersichts-Banner: Neue Lernbudgets (direction="initial") bekommen ein
   eigenes Symbol statt des fälschlichen Defizit-Symbols 📉.
3. i18n: setup.budget_learning_skip_ok existiert in de/en/fr, Parität bleibt.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_budget_step_unblocked_by_learning_mode():
    src = _src("views/setup_assistant_dialog.py")
    # Checkbox-Toggle triggert Neubewertung des Schritts
    assert "cb_setup_learning_enabled.toggled.connect" in src
    # Freigabe-Logik: Budgetwert ODER aktiver Lernmodus
    assert "has_val or learning_active" in src
    # Eigener Hinweistext statt "fehlt"-Meldung
    assert "setup.budget_learning_skip_ok" in src


def test_banner_uses_dedicated_icon_for_initial_suggestions():
    src = _src("views/tabs/overview_budget_panel.py")
    assert 'if s.direction == "initial"' in src
    # initial darf nicht mehr in den 📉-Else-Zweig fallen
    assert '"📈" if s.direction == "surplus" else "📉"' not in src


def _flat(d, p=""):
    out = set()
    for k, v in d.items():
        if isinstance(v, dict):
            out |= _flat(v, p + k + ".")
        else:
            out.add(p + k)
    return out


def test_i18n_setup_skip_key_present_and_parity():
    keys = {}
    for lang in ("de", "en", "fr"):
        data = json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8"))
        keys[lang] = _flat(data)
        assert "setup.budget_learning_skip_ok" in keys[lang], lang
    assert keys["de"] == keys["en"] == keys["fr"]


def test_schema_version_not_regressed():
    from model.migrations import CURRENT_VERSION

    assert CURRENT_VERSION >= 15
