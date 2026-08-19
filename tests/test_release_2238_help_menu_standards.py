"""Regressionstests v2.2.38 – Hilfe-Menü nach Desktop-Richtlinien.

Geprüft werden die Punkte, die beim alten flachen Zwölf-Punkte-Menü verletzt
waren: Länge, Gruppierung, Auslassungszeichen, Zugriffstasten, Reihenfolge und
Anwendersprache.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELP_MENU = ROOT / "views/help_menu.py"
MAIN_WINDOW = ROOT / "views/main_window.py"
LANGS = ("de", "en", "fr")


def _menu_source() -> str:
    return HELP_MENU.read_text(encoding="utf-8")


def _label(lang: str, key: str) -> str:
    data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
    flat = f"menu.{key}"
    if flat in data:
        return data[flat]
    return data["menu"][key]


# ── Struktur ────────────────────────────────────────────────────


def test_main_window_delegates_help_menu():
    src = MAIN_WINDOW.read_text(encoding="utf-8")
    assert "self.help_menu = build_help_menu(self, menubar)" in src
    assert "from views.help_menu import build_help_menu" in src


def test_top_level_stays_short():
    """Oberste Ebene bleibt überschaubar; Seltenes gehört in Untermenüs."""
    src = _menu_source()
    body = src.split("def build_help_menu", 1)[1].split("def current_release_notes", 1)[
        0
    ]
    # Nur Aufrufe zaehlen, deren Ziel das Hauptmenue ist (nicht visuals/trouble).
    calls = re.findall(r"_add\(\s*\n?\s*(\w+), window", body)
    top_level = calls.count("menu")
    submenus = body.count("menu.addMenu(")
    assert submenus == 2, "Visuelle Übersichten und Problembehandlung erwartet"
    assert top_level + submenus <= 10, f"{top_level + submenus} Einträge sind zu viele"


def test_menu_is_grouped_by_separators():
    body = _menu_source().split("def build_help_menu", 1)[1]
    assert body.count("menu.addSeparator()") >= 4, "zu wenige Sinnabschnitte"


def test_diagnostics_moved_into_submenu():
    """Protokolle und Diagnosepaket dürfen nicht mehr auf oberster Ebene stehen."""
    body = _menu_source()
    for key in (
        "menu.show_log",
        "menu.show_crash_log",
        "menu.open_diagnostics_folder",
        "menu.create_diagnostic_report",
        "menu.show_restore_key",
    ):
        assert f'"{key}"' in body
        line = [ln for ln in body.splitlines() if f'"{key}"' in ln][0]
        context = body[: body.index(line)]
        assert context.rindex("trouble") > context.rindex("menu.addSeparator()"), key


def test_about_is_last_entry():
    body = _menu_source().split("def build_help_menu", 1)[1]
    assert body.rindex('"menu.about"') > body.rindex('"menu.release_notes"')
    assert body.rindex('"menu.about"') > body.rindex('"menu.updates"')


def test_update_check_moved_from_extras_to_help():
    """Nach Updates suchen gehört ins Hilfe-Menü, nicht in die Extras-Sammlung."""
    main = MAIN_WINDOW.read_text(encoding="utf-8")
    extras = main.split("def _create_extras_menu", 1)[1].split(
        "def _create_account_menu", 1
    )[0]
    assert 'tr("menu.updates")' not in extras
    assert '"menu.updates"' in _menu_source()


# ── Beschriftungen ──────────────────────────────────────────────

DIALOG_ITEMS = (
    "handbook",
    "shortcuts",
    "setup_assistant",
    "show_log",
    "show_crash_log",
    "create_diagnostic_report",
    "show_restore_key",
    "updates",
    "release_notes",
    "about",
)
IMMEDIATE_ITEMS = (
    "knowledge_base",
    "help_mindmap",
    "wiki_audit",
    "open_diagnostics_folder",
    "help_visuals",
    "troubleshooting",
)


def test_dialog_items_end_with_single_ellipsis_character():
    for lang in LANGS:
        for key in DIALOG_ITEMS:
            label = _label(lang, key)
            assert label.endswith("…"), f"{lang}/{key}: {label!r}"
            assert "..." not in label, f"{lang}/{key}: drei Punkte statt …"


def test_immediate_items_have_no_ellipsis():
    for lang in LANGS:
        for key in IMMEDIATE_ITEMS:
            label = _label(lang, key)
            assert not label.endswith("…"), f"{lang}/{key}: {label!r}"
            assert "..." not in label, f"{lang}/{key}"


def test_access_keys_are_unique_per_menu_level():
    top = (
        "handbook",
        "knowledge_base",
        "help_visuals",
        "shortcuts",
        "setup_assistant",
        "troubleshooting",
        "updates",
        "release_notes",
        "about",
    )
    sub = (
        "show_log",
        "show_crash_log",
        "open_diagnostics_folder",
        "create_diagnostic_report",
        "show_restore_key",
    )
    for lang in LANGS:
        for group in (top, sub):
            used = []
            for key in group:
                label = _label(lang, key)
                assert "&" in label, f"{lang}/{key}: keine Zugriffstaste"
                used.append(label[label.index("&") + 1].lower())
            assert len(used) == len(set(used)), f"{lang}: doppelte Zugriffstaste {used}"


def test_developer_jargon_removed_from_user_labels():
    for lang in LANGS:
        assert "Restore-Key" not in _label(lang, "show_restore_key")
        assert "Crash-Log" not in _label(lang, "show_crash_log")


def test_all_languages_translate_the_update_entry():
    """Vorher stand in allen drei Sprachen unübersetzt '&Updates...'."""
    labels = {lang: _label(lang, "updates") for lang in LANGS}
    assert len(set(labels.values())) == 3, labels


# ── Neuerungen-Dialog ───────────────────────────────────────────


def test_release_notes_reads_only_the_top_section():
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    sections = re.split(r"^## ", text, flags=re.MULTILINE)
    assert len(sections) > 2, "Changelog braucht mehrere Versionsabschnitte"
    src = _menu_source()
    assert "sections[1]" in src
    assert "CHANGELOG.md" in src


def test_release_notes_strings_exist_in_all_languages():
    for lang in LANGS:
        data = json.loads((ROOT / f"locales/{lang}.json").read_text(encoding="utf-8"))
        for key in (
            "release_notes_title",
            "release_notes_heading",
            "release_notes_missing",
        ):
            flat = f"help.{key}"
            value = data.get(flat) or data.get("help", {}).get(key)
            assert value, f"{lang}/{key} fehlt"
        assert "{version}" in (
            data.get("help.release_notes_title") or data["help"]["release_notes_title"]
        )


def test_changelog_is_shipped_for_release_notes():
    spec = (ROOT / "BudgetManager.spec").read_text(encoding="utf-8")
    assert "CHANGELOG.md" in spec, "Changelog muss im Build mitgeliefert werden"
