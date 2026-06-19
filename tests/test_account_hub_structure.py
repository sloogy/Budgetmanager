"""Struktur-/Marker-Tests für den Konto-Hub (Item B, V2). Qt-frei.

Sichert per Quelltext-Marker ab, dass der zentrale Hub existiert, an die
bestehenden Dialoge delegiert und sowohl im Reiter „Konto" als auch in der
Einstellungen-Seite eingebettet ist – und dass die verstreuten Einstiege
entfernt wurden.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def test_hub_component_exists_and_delegates():
    src = _read("views/account_data_hub.py")
    assert "class AccountDataHub(QWidget)" in src
    # Delegiert an die bestehenden, getesteten Methoden des Hauptfensters
    assert '"_show_account_management"' in src
    assert '"_show_backup_restore"' in src
    assert '"_show_database_management"' in src
    # Speicherort inkl. Datenübernahme über den zentralen Handler
    assert "_handle_data_directory_change" in src
    # Inline-Speicherort-Steuerung
    assert "_choose_data_dir" in src and "_apply_data_dir" in src


def test_mainwindow_registers_account_tab():
    src = _read("views/main_window.py")
    assert "from views.account_data_hub import AccountDataHub" in src
    assert "self.account_tab = AccountDataHub(" in src
    # In Tab-Definition, Sichtbarkeit und Default-Reihenfolge eingehängt
    assert "6: (self.account_tab, tr(\"tab.account\"))" in src
    assert "6: \"account\"" in src
    assert "default_order = [5, 0, 2, 3, 4, 6]" in src


def test_settings_embeds_same_hub():
    src = _read("settings_dialog.py")
    assert "from views.account_data_hub import AccountDataHub" in src
    assert "self.account_hub = AccountDataHub(" in src
    assert 'tr("settings.account_data")' in src
    # Alte, jetzt im Hub lebende Datenordner-Methoden sind entfernt
    assert "def _choose_data_dir" not in src
    assert "def _refresh_data_dir_effective" not in src


def test_scattered_entrypoints_removed():
    src = _read("views/main_window.py")
    # Backup/DB-Verwaltung nicht mehr als verstreute Extras-Aktionen
    assert "extras_menu.addAction(backup_action)" not in src
    assert "extras_menu.addAction(db_manage_action)" not in src
    # data_directory wird nicht mehr über den Settings-OK-Pfad verarbeitet
    assert 'if "data_directory" in new_settings:' not in src


def test_account_menu_links_to_tab():
    src = _read("views/main_window.py")
    assert 'tr("menu.account_data")' in src
    assert "self._goto_tab(self.account_tab)" in src
