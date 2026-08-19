"""v2.2.16 – Vereinheitlichung doppelter Werkzeuge (Bedienbarkeit).

Diese Tests sichern statisch, dass die konsolidierten Wege wirklich EINER sind
und die entfernten Dialoge nicht zurueckkehren. GUI-Verhalten wird auf dem
echten System geprueft; hier geht es um die strukturellen Zusicherungen.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── K1: Buchung – ein Dialog fuer Neu und Bearbeiten ───────────────────────
def test_tracker_dialog_is_gone():
    assert not (
        ROOT / "views" / "tracker_dialog.py"
    ).exists(), (
        "TrackerDialog muss entfallen – QuickAddDialog deckt Neu UND Bearbeiten ab"
    )


def test_quick_add_has_edit_mode():
    src = _src("views/quick_add_dialog.py")
    assert "edit_row_id" in src
    assert "_edit_row_id" in src
    # Update-Pfad im Speichern
    assert "self.tracking.update(" in src


def test_tracking_edit_uses_quick_add_dialog():
    src = _src("views/tabs/tracking_tab.py")
    assert "QuickAddDialog(" in src
    assert "edit_row_id=" in src
    assert "TrackerDialog" not in src.replace("# ", "")  # auch nicht im Kommentar-Code


def test_edit_keeps_unlisted_category_fallback():
    """v2.1.7-Blocker-Schutz muss im QuickAdd-Edit-Modus erhalten sein."""
    marker = (
        _src("views/quick_add_dialog.py")
        .split("def _apply_preset", 1)[1]
        .split("\n    def ", 1)[0]
    )
    assert "insertItem(0, wanted, wanted)" in marker
    assert "currentData() != wanted" in marker


# ── K2: Budget – nur der erweiterte Dialog ─────────────────────────────────
def test_slim_budget_entry_dialog_is_gone():
    assert not (ROOT / "views" / "budget_entry_dialog.py").exists()


def test_budget_tab_uses_only_extended():
    src = _src("views/tabs/budget_tab.py")
    assert "BudgetEntryDialogExtended(" in src
    assert "from views.budget_entry_dialog import" not in src


# ── K3: Fixkosten – ein Dialog ─────────────────────────────────────────────
def test_fixcost_and_missing_dialogs_are_gone():
    assert not (ROOT / "views" / "fixcost_dialog.py").exists()
    assert not (ROOT / "views" / "missing_bookings_dialog.py").exists()


def test_recurring_dialog_has_integrated_month_and_reload():
    src = _src("views/recurring_bookings_dialog.py")
    assert "initial_month" in src
    assert "reload_callback" in src
    assert "def set_items" in src
    # PendingBooking lebt jetzt hier
    assert "class PendingBooking" in src or "PendingBooking" in src


def test_tracking_tab_uses_single_fixcost_dialog():
    src = _src("views/tabs/tracking_tab.py")
    # Kein Import und kein Aufruf der entfernten Dialoge (Kommentare, die den
    # frueheren Zustand erklaeren, sind erlaubt).
    assert "import FixcostDialog" not in src
    assert "FixcostDialog(" not in src
    assert "MissingBookingsDialog(" not in src
    assert "import MissingBookingsDialog" not in src
    assert "reload_callback=" in src


# ── K4: Reset an einem Ort, hinter Re-Auth ─────────────────────────────────
def test_reset_removed_from_backup_dialog():
    src = _src("views/backup_restore_dialog.py")
    assert "btn_reset_db" not in src
    assert "def reset_database" not in src


def test_reset_requires_reauth_in_db_management():
    src = _src("views/database_management_dialog.py")
    assert "require_reauth" in src
    assert "active_user" in src


def test_shared_reauth_module_used_by_both_dialogs():
    assert (ROOT / "views" / "reauth.py").exists()
    reauth = _src("views/reauth.py")
    assert "def require_reauth" in reauth
    assert "QLineEdit.Password" in reauth
    for rel in (
        "views/backup_restore_dialog.py",
        "views/database_management_dialog.py",
    ):
        assert "require_reauth" in _src(
            rel
        ), f"{rel} nutzt die gemeinsame Abfrage nicht"


# ── K7: Menue entruempelt ──────────────────────────────────────────────────
def test_goto_menu_entries_removed_but_shortcuts_kept():
    src = _src("views/main_window.py")
    # Keine sichtbaren goto_*-Menueeintraege mehr …
    assert "view_menu.addAction(goto_cockpit)" not in src
    assert "view_menu.addAction(goto_tracking)" not in src
    # … aber die Actions bleiben fensterweit (Shortcut lebt weiter).
    assert "self.addAction(goto_cockpit)" in src


def test_tab_bar_controls_removed():
    src = _src("views/main_window.py")
    assert 'view_menu.addMenu(tr("menu.tab_bar"))' not in src
    assert 'QAction(tr("menu.reset_tab_order")' not in src


# ── K8 (B): ein Kategorie-Kern, zwei Rahmen ────────────────────────────────
def test_categories_share_one_widget_core():
    src = _src("views/category_manager_dialog.py")
    assert "class CategoryManagerWidget(QWidget)" in src
    assert "class CategoryManagerDialog(QDialog)" in src
    assert "class CategoriesTab(QWidget)" in src
    # Der Tab-Reexport zeigt auf den gemeinsamen Kern.
    tab = _src("views/tabs/categories_tab.py")
    assert "from views.category_manager_dialog import CategoriesTab" in tab


def test_categories_tab_exposes_expected_api():
    src = _src("views/category_manager_dialog.py")
    body = src.split("class CategoriesTab(QWidget)", 1)[1]
    for meth in (
        "refresh",
        "add_root_category",
        "add_subcategory",
        "delete_selected",
        "mass_edit",
    ):
        assert (
            f"def {meth}" in body
        ), f"CategoriesTab.{meth} fehlt (main_window nutzt es)"
