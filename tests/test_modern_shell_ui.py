from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN_WINDOW = ROOT / "views" / "main_window.py"


def source() -> str:
    return MAIN_WINDOW.read_text(encoding="utf-8")


def test_modern_shell_wraps_existing_tabs_in_sidebar_navigation():
    text = source()
    assert "def _build_modern_shell" in text
    assert "self.tabs.tabBar().hide()" in text
    assert "self.setCentralWidget(shell)" in text
    assert "self._sidebar_buttons" in text


def test_sidebar_uses_existing_domain_tabs_without_duplicate_views():
    text = source()
    for name in (
        "self.cockpit_tab",
        "self.tracking_tab",
        "self.budget_tab",
        "self.savings_tab",
        "self.overview_tab",
        "self.categories_tab",
        "self.account_tab",
    ):
        assert name in text
    assert "QStackedWidget" not in text


def test_sidebar_and_tabs_stay_synchronized():
    text = source()
    assert "def _sync_sidebar_selection" in text
    assert "self.tabs.currentChanged.connect(self._sync_sidebar_selection)" in text
    assert "button.setChecked(widget is current)" in text


def test_unified_actions_still_call_shared_handlers():
    text = source()
    assert "self._show_quick_add" in text
    assert "self._tracking_add_fixcosts" in text
    assert "self._show_category_manager" in text
    assert "self._show_savings_goals" in text
    assert "self._show_global_search" in text


def test_savings_and_pot_are_not_merged_by_ui_rework():
    text = source()
    assert "self.savings_tab" in text
    assert "self.account_tab" in text
    assert "Sparziele und POT" not in text  # no accidental combined navigation label
