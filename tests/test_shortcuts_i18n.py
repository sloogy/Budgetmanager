from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from model.shortcuts_config import (  # noqa: E402
    SHORTCUT_DEFS,
    group_for,
    label_for,
    shortcut_display_name,
)
from utils.i18n import set_language  # noqa: E402


def test_shortcut_catalog_is_localized_in_all_release_languages():
    forbidden_by_lang = {
        "en": ["Hilfe", "Wissensdatenbank", "Einstellungen öffnen", "Zum Budget-Tab", "Allgemein", "Funktionen", "Strg", "Umschalt"],
        "fr": ["Hilfe", "Wissensdatenbank", "Einstellungen öffnen", "Zum Budget-Tab", "Allgemein", "Funktionen", "Strg", "Umschalt"],
    }

    for lang in ("de", "en", "fr"):
        set_language(lang)
        labels = [label_for(aid) for aid, *_ in SHORTCUT_DEFS]
        groups = [group_for(aid) for aid, *_ in SHORTCUT_DEFS]
        display = shortcut_display_name("Ctrl+Shift+Z")
        text = "\n".join(labels + groups + [display])

        assert all(not label.startswith("shortcut.") for label in labels)
        assert all(not group.startswith("shortcut.") for group in groups)

        for forbidden in forbidden_by_lang.get(lang, []):
            assert forbidden not in text

    set_language("de")
    assert shortcut_display_name("Ctrl+Shift+Z") == "Strg+Umschalt+Z"
    set_language("en")
    assert shortcut_display_name("Ctrl+Shift+Z") == "Ctrl+Shift+Z"
    set_language("fr")
    assert shortcut_display_name("Ctrl+Shift+Z") == "Ctrl+Maj+Z"
