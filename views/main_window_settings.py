from __future__ import annotations

"""Einstellungs-Workflow des Hauptfensters.

Die Logik ist bewusst ausgelagert, damit ``MainWindow`` Navigation und
Fenster-Lebenszyklus koordiniert, ohne erneut zu einem GUI-Monolithen zu werden.
"""

import logging

from PySide6.QtWidgets import QDialog

from app_info import app_version_label
from model.shortcuts_config import save_shortcuts
from settings_dialog import SettingsDialog
from utils.i18n import tr, trf
from utils.notifications import show_info

logger = logging.getLogger(__name__)


def show_settings(self) -> None:
    """Zeigt Einstellungen-Dialog"""
    is_encrypted = (
        hasattr(self, "_encrypted_session") and self._encrypted_session is not None
    )
    dialog = SettingsDialog(
        self.settings,
        self,
        app_version=app_version_label(),
        encrypted_mode=is_encrypted,
        encrypted_session=getattr(self, "_encrypted_session", None),
    )

    if dialog.exec() == QDialog.Accepted:
        new_settings = dialog.get_settings()
        old_language = str(self.settings.get("language", "de") or "de")
        requested_language = str(
            new_settings.get("language", old_language) or old_language
        )
        language_changed = (
            requested_language.strip().lower() != old_language.strip().lower()
        )

        # Theme-Änderung?
        theme_changed = new_settings["theme"] != self.settings.theme

        # Einstellungen speichern
        self.settings.theme = new_settings["theme"]
        self.settings.auto_save = new_settings["auto_save"]
        self.settings.ask_due = new_settings["ask_due"]
        self.settings.refresh_on_start = new_settings["refresh_on_start"]
        # Tracking
        if "recent_days" in new_settings:
            self.settings.recent_days = int(new_settings["recent_days"] or 14)
        # Budgetübersicht: Monate für Vorschläge
        if "budget_suggestion_months" in new_settings:
            try:
                self.settings.set(
                    "budget_suggestion_months",
                    int(new_settings.get("budget_suggestion_months") or 3),
                )
            except Exception:
                self.settings.set("budget_suggestion_months", 3)

        # Separater Lernmodus: Budget aus reinem Tracking vorschlagen.
        # Diese Werte werden bewusst unabhängig vom normalen Budgettracker gespeichert.
        if "tracking_budget_learning_enabled" in new_settings:
            self.settings.set(
                "tracking_budget_learning_enabled",
                bool(new_settings.get("tracking_budget_learning_enabled", True)),
            )
        if "tracking_budget_learning_proposal_months" in new_settings:
            try:
                v = int(
                    new_settings.get("tracking_budget_learning_proposal_months") or 2
                )
            except Exception:
                v = 2
            self.settings.set(
                "tracking_budget_learning_proposal_months", max(1, min(12, v))
            )
        if "tracking_budget_learning_stable_months" in new_settings:
            try:
                v = int(new_settings.get("tracking_budget_learning_stable_months") or 3)
            except Exception:
                v = 3
            self.settings.set(
                "tracking_budget_learning_stable_months", max(1, min(12, v))
            )
        if "tracking_budget_learning_include_current_month_projection" in new_settings:
            self.settings.set(
                "tracking_budget_learning_include_current_month_projection",
                bool(
                    new_settings.get(
                        "tracking_budget_learning_include_current_month_projection",
                        True,
                    )
                ),
            )
        if "tracking_budget_learning_show_in_report" in new_settings:
            self.settings.set(
                "tracking_budget_learning_show_in_report",
                bool(new_settings.get("tracking_budget_learning_show_in_report", True)),
            )
        if "tracking_budget_learning_auto_end" in new_settings:
            self.settings.set(
                "tracking_budget_learning_auto_end",
                bool(new_settings.get("tracking_budget_learning_auto_end", False)),
            )

        if "budget_overview_drag_drop" in new_settings:
            enabled = bool(new_settings.get("budget_overview_drag_drop", True))
            self.settings.set("budget_overview_drag_drop", enabled)
            if hasattr(self, "budget_tab") and hasattr(
                self.budget_tab, "set_category_drag_enabled"
            ):
                self.budget_tab.set_category_drag_enabled(enabled)

        if "recurring_preferred_day" in new_settings:
            try:
                self.settings.set(
                    "recurring_preferred_day",
                    int(new_settings.get("recurring_preferred_day", 25)),
                )
            except Exception:
                self.settings.set("recurring_preferred_day", 25)

        if "budget_zero_balance_rule" in new_settings:
            self.settings.set(
                "budget_zero_balance_rule",
                bool(new_settings.get("budget_zero_balance_rule", False)),
            )
        if "budget_surplus_strategy" in new_settings:
            strategy = str(
                new_settings.get("budget_surplus_strategy", "savings") or "savings"
            )
            if strategy not in {"savings", "carryover"}:
                strategy = "savings"
            self.settings.set("budget_surplus_strategy", strategy)

        # Budgetübersicht: Übertrag-Kumulation Start (Monat/Jahr)
        # BUGFIX: Diese Werte kamen zwar aus dem SettingsDialog, wurden aber nie persistiert.
        if "carryover_start_month" in new_settings:
            try:
                m = int(new_settings.get("carryover_start_month") or 1)
            except Exception:
                m = 1
            if m < 1:
                m = 1
            if m > 12:
                m = 12
            self.settings.set("carryover_start_month", m)

        if "carryover_start_year" in new_settings:
            try:
                y = int(new_settings.get("carryover_start_year") or 0)
            except Exception:
                y = 0
            # 0 ist bewusst erlaubt (= aktuelles Jahr). Wenn gesetzt, nicht clampen.
            self.settings.set("carryover_start_year", y)
        # Zusätzliche (neue) Einstellungen speichern
        # (Diese Keys sind rückwärtskompatibel – Tabs können sie später nutzen.)
        self.settings.set("show_onboarding", new_settings.get("show_onboarding", True))
        self.settings.set(
            "remember_last_tab", new_settings.get("remember_last_tab", True)
        )
        self.settings.set(
            "remember_filters", new_settings.get("remember_filters", True)
        )
        self.settings.set("language", new_settings.get("language", "Deutsch"))
        self.settings.set("currency", new_settings.get("currency", "CHF"))
        self.settings.set("number_format", new_settings.get("number_format", "swiss"))

        # Währung/Zahlenformat sind sofort sicher aktualisierbar. Eine Sprache
        # wird dagegen erst beim nächsten Start vollständig angewendet: Die
        # komplexen Tabs besitzen keine vollständigen retranslateUi-Routinen.
        # Ein Teilwechsel würde eine gemischte de/en/fr-Oberfläche erzeugen.
        try:
            from utils.money import set_currency, set_number_format

            set_currency(new_settings.get("currency", "CHF"))
            set_number_format(new_settings.get("number_format", "swiss"))
            try:
                from utils.qt_translator import apply_number_locale

                apply_number_locale(new_settings.get("number_format", "swiss"))
            except Exception as _e:
                logger.debug("Qt-Zahlenformat (Wechsel) nicht installiert: %s", _e)
            if not language_changed:
                self._retranslate_ui()
        except ImportError as e:
            logger.debug("Einstellungs-Module konnten nicht aktualisiert werden: %s", e)

        self.settings.set("warn_delete", new_settings.get("warn_delete", True))
        self.settings.set(
            "warn_budget_overrun", new_settings.get("warn_budget_overrun", False)
        )
        self.settings.set("table_density", new_settings.get("table_density", "Normal"))
        self.settings.set(
            "highlight_fixcosts", new_settings.get("highlight_fixcosts", True)
        )
        self.settings.set("auto_backup", new_settings.get("auto_backup", False))
        self.settings.set("backup_days", int(new_settings.get("backup_days", 30) or 30))
        self.settings.set(
            "auto_backup_keep", int(new_settings.get("auto_backup_keep", 10) or 10)
        )
        self.settings.set(
            "backup_auto_delete",
            bool(new_settings.get("backup_auto_delete", False)),
        )

        # Tastenkürzel speichern und neu laden
        shortcut_map = new_settings.get("shortcuts")
        if shortcut_map and isinstance(shortcut_map, dict):
            save_shortcuts(self.settings, shortcut_map)
            self._setup_shortcuts()  # Shortcuts sofort neu binden
        # Datenbankpfad optional übernehmen
        if new_settings.get("database_path"):
            self.settings.database_path = new_settings["database_path"]

        # Kategorien-Tab Einstellung
        old_show_cat = self.settings.show_categories_tab
        new_show_cat = new_settings.get("show_categories_tab", False)
        self.settings.show_categories_tab = new_show_cat

        # Kategorien-Tab Toggle aktualisieren wenn geändert
        if old_show_cat != new_show_cat:
            if hasattr(self, "toggle_categories_action"):
                self.toggle_categories_action.setChecked(new_show_cat)
            # Tab direkt ein/ausblenden
            self._toggle_categories_tab(new_show_cat)

        # Auf Tabs anwenden
        if language_changed:
            show_info(
                self,
                tr("msg.restart_required_title"),
                tr("msg.language_restart_required"),
            )

        self._apply_settings_to_tabs()

        # Nach dem Speichern: Views neu laden, damit Änderungen (z.B.
        # Warnhinweise, Tab-Sichtbarkeit, Dichte, etc.) sofort wirken.
        self._schedule_refresh_all_tabs(reason="settings saved")

        # Theme anwenden (Profile werden automatisch geladen)
        self._apply_theme()

        if theme_changed:
            self.statusBar().showMessage(
                trf("msg.theme_changed_to", theme=new_settings["theme"]), 3000
            )
        else:
            self.statusBar().showMessage(tr("msg.settings_saved"), 2000)
