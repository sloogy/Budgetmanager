"""Regressionstests v2.2.35 – Handbuch deckt den realen Funktionsumfang ab."""

from __future__ import annotations

from tools.handbook_completeness_audit import run_audit
from views.help_content import HELP_TOPICS, help_topic_body


def test_handbook_completeness_audit_passes():
    failed = [check for check in run_audit() if not check.passed]
    assert not failed, [(c.name, c.details) for c in failed]


def test_new_handbook_topics_are_trilingual_and_searchable():
    required = {
        "lernmodus",
        "pot-rueckstellung",
        "jahreswechsel",
        "suche-filter",
        "export-druck",
        "einstellungen-design",
        "tastenkurzel",
        "datenverwaltung",
        "diagnose",
    }
    by_id = {t["id"]: t for t in HELP_TOPICS}
    assert required <= set(by_id)
    for topic_id in required:
        for lang in ("de", "en", "fr"):
            assert len(help_topic_body(by_id[topic_id], lang)) >= 180


def test_month_close_help_does_not_claim_a_lock():
    topic = next(t for t in HELP_TOPICS if t["id"] == "monatsabschluss")
    de = help_topic_body(topic, "de")
    assert "friert den Monat nicht ein" in de
    assert "Vermerk" in de


def test_export_help_states_actual_limits():
    topic = next(t for t in HELP_TOPICS if t["id"] == "export-druck")
    de = help_topic_body(topic, "de")
    assert "CSV" in de and "TXT" in de
    assert "PDF" in de and "XLSX" in de
    assert "Druckvorschau" in de
    assert ".bmr" in de and "Druck" in de
