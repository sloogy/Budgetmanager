"""Menü und Laufzeitumschaltung für Einfach-/Erweitert-Modus."""

from __future__ import annotations

import logging

from PySide6.QtGui import QAction, QActionGroup

from utils.icons import get_icon
from utils.i18n import tr
from utils.ui_experience_mode import detect_mode, mode_payload

logger = logging.getLogger(__name__)


def build_ui_experience_menu(window, view_menu) -> None:
    """Baut das kompakte Bedienmodus-Menü in die Hauptansicht ein."""
    mode_menu = view_menu.addMenu(tr("ui_mode.menu"))
    mode_menu.setIcon(get_icon("🧭"))
    window._ui_mode_group = QActionGroup(window)
    window._ui_mode_group.setExclusive(True)
    window._ui_mode_actions = {}
    for mode, label_key, tip_key in (
        ("simple", "ui_mode.simple", "ui_mode.simple_tip"),
        ("advanced", "ui_mode.advanced", "ui_mode.advanced_tip"),
    ):
        action = QAction(tr(label_key), window)
        action.setCheckable(True)
        action.setToolTip(tr(tip_key))
        action.triggered.connect(
            lambda checked=False, selected=mode: (
                apply_ui_experience_mode(window, selected) if checked else None
            )
        )
        window._ui_mode_group.addAction(action)
        mode_menu.addAction(action)
        window._ui_mode_actions[mode] = action
    custom_action = QAction(tr("ui_mode.custom"), window)
    custom_action.setEnabled(False)
    mode_menu.addAction(custom_action)
    window._ui_mode_custom_action = custom_action
    sync_ui_experience_mode_actions(window)
    view_menu.addSeparator()


def apply_ui_experience_mode(window, mode: str) -> None:
    """Wendet einen vollständigen Einfach-/Erweitert-Modus atomar an."""
    payload = mode_payload(mode)
    window.settings.set_many(payload)
    window._rebuild_tabs_keep_current(window.cockpit_tab)
    window._apply_tab_icons()
    try:
        preset = str(payload.get("cockpit_preset", "focus"))
        index = window.cockpit_tab.preset_combo.findData(preset)
        if index >= 0:
            blocked = window.cockpit_tab.preset_combo.blockSignals(True)
            window.cockpit_tab.preset_combo.setCurrentIndex(index)
            window.cockpit_tab.preset_combo.blockSignals(blocked)
        window.cockpit_tab._apply_panel_visibility()
        window.cockpit_tab.refresh()
    except Exception:
        logger.exception(
            "Bedienmodus konnte im Cockpit nicht vollständig aktualisiert werden"
        )
    window._sync_tab_visibility_actions()
    sync_ui_experience_mode_actions(window)
    window.statusBar().showMessage(
        (
            tr("ui_mode.simple_applied")
            if mode == "simple"
            else tr("ui_mode.advanced_applied")
        ),
        3500,
    )


def sync_ui_experience_mode_actions(window) -> None:
    """Synchronisiert die Modusanzeige mit der tatsächlich sichtbaren UI."""
    actions = getattr(window, "_ui_mode_actions", {})
    if not actions:
        return
    mode = detect_mode(window.settings)
    for key, action in actions.items():
        blocked = action.blockSignals(True)
        action.setChecked(key == mode)
        action.blockSignals(blocked)
    custom = getattr(window, "_ui_mode_custom_action", None)
    if custom is not None:
        custom.setVisible(mode == "custom")
