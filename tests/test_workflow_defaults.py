from pathlib import Path

from settings import Settings


def test_safe_defaults_enabled_from_first_start(tmp_path):
    settings = Settings(settings_file=str(tmp_path / "settings.json"))
    assert settings.auto_save is True
    assert settings.get("auto_backup", False) is True
    assert int(settings.get("backup_days", 0)) == 7


def test_help_mindmap_is_packaged_and_directly_readable():
    root = Path(__file__).resolve().parents[1]
    help_dir = root / "docs" / "help"
    assert (help_dir / "README.md").exists()
    mindmap_html = help_dir / "mindmap.html"
    assert mindmap_html.exists()
    html = mindmap_html.read_text(encoding="utf-8")
    assert "BudgetManager Informations-Laufplan" in html
    assert "lokale HTML-Mindmap ohne externe Abhängigkeiten" in html
    assert "Aktive Sparziele" in html


def test_help_mindmap_is_available_in_de_en_fr():
    root = Path(__file__).resolve().parents[1]
    help_dir = root / "docs" / "help"
    expected_html = {
        "de": ["BudgetManager Informations-Laufplan", "Aktive Sparziele", "Wissensdatenbank"],
        "en": ["BudgetManager information flow", "active savings goals", "knowledge base"],
        "fr": ["Parcours d’information BudgetManager", "objectifs d’épargne actifs", "base de connaissances"],
    }
    expected_mmd = {
        "de": ["Cockpit / Startseite", "Aktive Sparziele", "Wissensdatenbank"],
        "en": ["Cockpit / home", "active savings goals", "knowledge base"],
        "fr": ["Cockpit / accueil", "objectifs d’épargne actifs", "base de connaissances"],
    }
    forbidden = {
        "en": ["Informations-Laufplan", "Aktive Sparziele", "Wissensdatenbank", "Monatsstatus"],
        "fr": ["Informations-Laufplan", "Aktive Sparziele", "Wissensdatenbank", "Monatsstatus"],
    }

    for lang, needles in expected_html.items():
        html_path = help_dir / f"mindmap.{lang}.html"
        mmd_path = help_dir / f"mindmap.{lang}.mmd"
        assert html_path.exists()
        assert mmd_path.exists()
        html = html_path.read_text(encoding="utf-8")
        mmd = mmd_path.read_text(encoding="utf-8")
        for needle in needles:
            assert needle in html
        for needle in expected_mmd[lang]:
            assert needle in mmd
        for needle in forbidden.get(lang, []):
            assert needle not in html
            assert needle not in mmd
