from __future__ import annotations

"""Regression v2.2.48: EN-Oberfläche und EN-Doku nutzen durchgängig
US-Schreibweise ("favorite"), passend zu locales/en.json und den
KILLCRITIC-Kernbegriffen (k4_guide_coverage)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

EN_SOURCES = [
    ROOT / "locales" / "en.json",
    ROOT / "docs" / "USER_GUIDE.en.md",
    ROOT / "docs" / "help" / "mindmap.en.html",
    ROOT / "docs" / "help" / "mindmap.en.mmd",
]


def test_en_texts_use_us_spelling_for_favorites():
    offenders: list[str] = []
    for path in EN_SOURCES:
        text = path.read_text(encoding="utf-8").lower()
        if "favourit" in text:
            offenders.append(str(path.relative_to(ROOT)))
    assert offenders == [], f"Britische Schreibweise gefunden in: {offenders}"


def test_en_guide_contains_killcritic_core_term_favorites():
    guide = (ROOT / "docs" / "USER_GUIDE.en.md").read_text(encoding="utf-8")
    assert "favorite" in guide.lower(), "Kernbegriff 'Favorites' fehlt im EN-Guide"
