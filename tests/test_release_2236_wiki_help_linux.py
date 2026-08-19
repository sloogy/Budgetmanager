"""Regressionstests v2.2.36 – Wiki-Grafiken und Linux-sicherer Hilfe-Einstieg."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_linux_sidebar_has_plain_question_mark_help_button():
    src = (ROOT / "views/main_window.py").read_text(encoding="utf-8")
    assert "f\"?  {tr('menu.help')}\"" in src
    assert "self.sidebar_help_button = add_utility" in src
    assert "self._show_handbook" in src


def test_wiki_graphics_are_bundled_and_linked():
    paths = [
        ROOT / "docs/help/wiki-audit.html",
        ROOT / "docs/help/assets/wiki_audit_overview.png",
        ROOT / "docs/help/assets/dataflow_decision_logic.png",
        ROOT / "docs/help/assets/wiki_audit_dashboard.png",
    ]
    for path in paths:
        assert path.is_file(), path
        assert path.stat().st_size > 1000, path
    spec = (ROOT / "BudgetManager.spec").read_text(encoding="utf-8")
    assert '("docs/help", "docs/help")' in spec


def test_help_menu_and_handbook_link_to_wiki_audit():
    main = (ROOT / "views/main_window.py").read_text(encoding="utf-8")
    main += (ROOT / "views/help_menu.py").read_text(encoding="utf-8")
    dialog = (ROOT / "views/help_dialog.py").read_text(encoding="utf-8")
    additions = (ROOT / "views/help_content_additions.py").read_text(encoding="utf-8")
    assert '"menu.wiki_audit"' in main
    assert "docs/help/wiki-audit.html" in main
    assert "help.btn_open_wiki_audit" in dialog
    assert '"wiki-zusammenhaenge"' in additions
