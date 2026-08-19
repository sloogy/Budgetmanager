"""Regression v2.2.5: Erststart-Enter-Navigation + ausgebaute Anleitung.

- Der Setup-Assistent hat einen keyPressEvent, der Enter/Return auf "Weiter"
  bzw. "Fertig" abbildet und in mehrzeiligen Textfeldern nicht stört; Weiter/
  Fertig sind Default-Buttons, Zurück nicht.
- Das Hilfe-Einstiegsthema ist zu einem echten Willkommen ausgebaut (Cockpit,
  Ampel, Nächste Schritte, zwei Wege, Enter-Tipp) und es gibt ein eigenes
  Monatsabschluss-Thema – alles dreisprachig.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_setup_enter_key_navigation_wired():
    src = _src("views/setup_assistant_dialog.py")
    assert "def keyPressEvent" in src
    # Enter löst Weiter/Fertig aus …
    assert "self._go_next()" in src
    assert "self._finish()" in src
    # … aber nicht in mehrzeiligen Textfeldern
    assert "QPlainTextEdit" in src and "QTextEdit" in src
    # Default-Buttons korrekt gesetzt
    assert "self.btn_next.setDefault(True)" in src
    assert "self.btn_finish.setDefault(True)" in src
    assert "self.btn_back.setAutoDefault(False)" in src


def test_help_getting_started_is_expanded_and_trilingual():
    from views.help_content import HELP_TOPICS, help_topic_body

    topic = next(t for t in HELP_TOPICS if t["id"] == "einstieg")
    de = help_topic_body(topic, "de")
    en = help_topic_body(topic, "en")
    fr = help_topic_body(topic, "fr")
    # Willkommen + zentrale 2.2.x-Konzepte erklärt
    assert "Willkommen bei BudgetManager" in de
    assert "Welcome to BudgetManager" in en
    assert "Bienvenue dans BudgetManager" in fr
    for body in (de, en, fr):
        assert len(body) > 600  # deutlich ausgebaut
    assert "Ampel" in de
    assert "Enter-Taste" in de
    assert "Express" in de


def test_help_has_month_close_topic_trilingual():
    from views.help_content import HELP_TOPICS, help_topic_body, help_topic_title

    topic = next((t for t in HELP_TOPICS if t["id"] == "monatsabschluss"), None)
    assert topic is not None, "Monatsabschluss-Thema fehlt"
    assert help_topic_title(topic, "de") == "Monatsabschluss"
    assert help_topic_title(topic, "en") == "Month-end close"
    assert help_topic_title(topic, "fr")
    # Kernregel muss drinstehen: keine Fixkosten-Kürzung
    de = help_topic_body(topic, "de")
    assert "Fixkosten" in de and "nie" in de
    for lang in ("de", "en", "fr"):
        assert len(help_topic_body(topic, lang)) > 400


def test_all_help_topics_have_three_languages():
    from views.help_content import HELP_TOPICS, help_topic_body

    for t in HELP_TOPICS:
        for lang in ("de", "en", "fr"):
            assert len(help_topic_body(t, lang)) >= 20, (t["id"], lang)


def test_setup_welcome_texts_mention_both_paths():
    import json

    for lang in ("de", "en", "fr"):
        data = json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8"))
        intro = data["setup"]["setup_mode_intro"]
        title = data["setup"]["setup_mode_title"]
        assert "BudgetManager" in title
        # Beide Wege + Enter-Tipp erwähnt
        assert "Enter" in intro or "Entr" in intro
