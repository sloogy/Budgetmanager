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
