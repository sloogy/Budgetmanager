"""v2.2.23 – Enterprise-UI-/Usability-/ADHS-Nachaudit.

Sichert die im unabhängigen Audit gefundenen Regressionen ab:
- Release-Cleaner entfernt durch Tests erzeugte Nutzerdaten.
- Vorbefüllte Felder werden beim globalen Erstfokus nicht überschreibungsbereit markiert.
- Formularfelder erhalten verständliche Accessibility-Namen.
- Icon-only-Löschaktionen bleiben Enter-sicher.
- Sprache wird nicht unvollständig live umgeschaltet.
- Mitgelieferte Themes erfüllen WCAG-AA-Kontrast für UI-Text.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _qt_widgets():
    """Qt nur für die drei echten GUI-Tests anfordern.

    Dadurch bleiben die fünf Qt-unabhängigen Release-/Quelltests auch in
    schlanken Headless-Umgebungen aktiv.
    """
    return pytest.importorskip("PySide6.QtWidgets")


def _app():
    qt = _qt_widgets()
    return qt.QApplication.instance() or qt.QApplication([])


def _luminance(hex_color: str) -> float:
    raw = hex_color.lstrip("#")
    rgb = [int(raw[i : i + 2], 16) / 255.0 for i in (0, 2, 4)]
    linear = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(a: str, b: str) -> float:
    l1, l2 = _luminance(a), _luminance(b)
    bright, dark = max(l1, l2), min(l1, l2)
    return (bright + 0.05) / (dark + 0.05)


def test_release_cleaner_removes_runtime_user_data(tmp_path):
    from tools.clean_release_tree import clean

    data = tmp_path / "data"
    (data / "backups").mkdir(parents=True)
    (data / "theme_profiles").mkdir()
    for rel in (
        "budgetmanager_settings.json",
        "budgetmanager_settings.tmp",
        "users.json",
        "budgetmanager.db",
        "cache.sqlite",
        "vault.enc",
    ):
        (data / rel).write_text("test", encoding="utf-8")
    (data / "theme_profiles" / "private.json").write_text("{}", encoding="utf-8")

    clean(tmp_path)

    for rel in (
        "budgetmanager_settings.json",
        "budgetmanager_settings.tmp",
        "users.json",
        "budgetmanager.db",
        "cache.sqlite",
        "vault.enc",
        "theme_profiles",
    ):
        assert not (data / rel).exists(), rel
    assert (data / "backups" / ".gitkeep").exists()


def test_global_focus_does_not_select_prefilled_text():
    qt = _qt_widgets()
    from utils.ui_usability import focus_first_input

    _app()
    dialog = qt.QDialog()
    layout = qt.QVBoxLayout(dialog)
    field = qt.QLineEdit("123.45")
    layout.addWidget(field)
    dialog.show()
    qt.QApplication.processEvents()
    dialog.setFocus()

    focus_first_input(dialog)

    assert field.hasFocus()
    assert field.selectedText() == ""
    assert field.cursorPosition() == len(field.text())
    dialog.close()


def test_form_label_becomes_accessible_name():
    qt = _qt_widgets()
    from utils.ui_usability import enhance_widget_tree

    _app()
    dialog = qt.QDialog()
    form = qt.QFormLayout(dialog)
    field = qt.QLineEdit()
    form.addRow("Betrag", field)

    enhance_widget_tree(dialog)

    assert field.accessibleName() == "Betrag"


def test_icon_only_destructive_button_is_never_default():
    qt = _qt_widgets()
    from utils.ui_usability import enhance_widget_tree

    _app()
    dialog = qt.QDialog()
    layout = qt.QVBoxLayout(dialog)
    button = qt.QPushButton("")
    button.setToolTip("Eintrag löschen")
    button.setAutoDefault(True)
    button.setDefault(True)
    layout.addWidget(button)

    enhance_widget_tree(dialog)

    assert not button.autoDefault()
    assert not button.isDefault()


def test_language_change_is_deferred_to_restart_to_avoid_mixed_ui():
    src = (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")
    start = src.index("    def _show_settings(self):")
    end = src.index("\n    def ", start + 10)
    method = src[start:end]
    assert "language_changed" in method
    assert "msg.language_restart_required" in method
    assert "set_language(" not in method


def test_tag_color_action_has_usable_click_target():
    src = (ROOT / "views" / "tags_manager_dialog.py").read_text(encoding="utf-8")
    assert "btn_color.setFixedSize(36, 32)" in src
    assert "btn_color.setFixedSize(30, 24)" not in src


def test_builtin_theme_text_contrast_is_wcag_aa():
    pairs = {
        "text": (
            "hintergrund_app",
            "hintergrund_panel",
            "hintergrund_seitenleiste",
            "tabelle_hintergrund",
            "tabelle_alt",
        ),
        "text_gedimmt": (
            "hintergrund_app",
            "hintergrund_panel",
            "hintergrund_seitenleiste",
        ),
        "akzent_text": ("akzent",),
        "akzent_panel_text": ("hintergrund_panel",),
        "tabelle_header_text": ("tabelle_header",),
        "auswahl_text": ("auswahl_hintergrund",),
        "dropdown_text": ("dropdown_bg",),
        "dropdown_selection_text": ("dropdown_selection",),
        "hover_text": ("hover_hintergrund",),
        "negativ_text": (
            "hintergrund_app",
            "hintergrund_panel",
            "tabelle_hintergrund",
            "tabelle_alt",
        ),
    }
    failures: list[str] = []
    for path in sorted((ROOT / "views" / "profiles").glob("*.json")):
        profile = json.loads(path.read_text(encoding="utf-8"))
        for foreground, backgrounds in pairs.items():
            if foreground not in profile:
                continue
            for background in backgrounds:
                if background not in profile:
                    continue
                ratio = _contrast(profile[foreground], profile[background])
                if ratio < 4.5:
                    failures.append(
                        f"{path.name}: {foreground}/{background}={ratio:.2f}:1"
                    )
    assert not failures, "\n".join(failures)


def test_release_tree_has_no_runtime_settings():
    assert not (ROOT / "data" / "budgetmanager_settings.json").exists()
