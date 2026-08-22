import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app_info import APP_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_guides_exist_and_are_current():
    for lang in ("de", "en", "fr"):
        text = (ROOT / "docs" / f"USER_GUIDE.{lang}.md").read_text(encoding="utf-8")
        assert APP_VERSION in text
        assert len(text) > 1500


def test_german_help_no_longer_teaches_removed_tab_workflow():
    text = (ROOT / "docs" / "help" / "README.md").read_text(encoding="utf-8")
    forbidden = (
        "Haupt-Reiter selbst sind verschiebbar",
        "Extras → Tab-Reihenfolge zurücksetzen",
        "Reiter ein-/ausblenden",
    )
    for phrase in forbidden:
        assert phrase not in text
    assert "linke Seitenleiste" in text
    assert "denselben vollständigen Buchungsdialog" in text


def test_pot_and_savings_goal_are_documented_as_separate_concepts():
    for name in ("USER_GUIDE.de.md",):
        text = (ROOT / "docs" / name).read_text(encoding="utf-8")
        assert "POT/Rückstellung" in text
        assert "Sparziel" in text
        assert "getrennt" in text


def test_reset_documentation_points_to_database_management_only():
    text = (ROOT / "docs" / "USER_GUIDE.de.md").read_text(encoding="utf-8")
    assert "Reset existiert nur noch in der Datenbankverwaltung" in text
    assert "erneut den Benutzercode" in text


def test_html_help_was_regenerated():
    html = (ROOT / "docs" / "help" / "index.html").read_text(encoding="utf-8")
    assert f"BudgetManager Hilfe {APP_VERSION}" in html
    assert "Vereinheitlichte Bedienung" in html
    assert "<table>" in html
