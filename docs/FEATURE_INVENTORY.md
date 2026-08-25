# Funktionsinventar – Abgleich der eingereichten Wunschliste

Stand: **v3.0.6**, 25. August 2026
Prüfmethode: Abgleich jeder Zeile der eingereichten Liste gegen Modul, Bedienweg
(UI-Einstieg) und vorhandene Regressionstests. Jede Zeile wurde für v3.0.6 am
Quellbaum nachgeprüft — Modul, Dialog und Test existieren.

Diese Datei löst `FEATURE_INVENTORY_v2.2.37.md` ab. Der Versionsstempel im
Dateinamen entfiel, weil das Inventar bei jedem Release fortgeschrieben wird
statt als Einmalbericht zu entstehen.

**Ergebnis: 13 von 13 Punkten sind ausgeliefert.**

| # | Wunsch | Status | Modul | Bedienweg | Test |
|---|--------|--------|-------|-----------|------|
| 1 | Wiederkehrende Transaktionen (automatische Buchungen) mit Soll-Buchungsdatum je Eintrag | ausgeliefert, siehe Hinweis unten | `model/recurring_transactions_model.py` (`_calculate_booking_date`, `_is_valid_booking_date`); aktiver Pfad über `categories.is_recurring` / `recurring_day` | Extras → Wiederkehrende Buchungen | `test_recurring_day_booking_date.py`, `test_recurring_preferred_day_defaults.py` |
| 2 | Fixkosten: Prüfung, ob im Monat schon gebucht | ausgeliefert | `model/fixed_cost_due.py` (`is_open_this_month`, Qt-frei) | Cockpit-Kachel „Fixkosten" | `test_fixed_cost_suggestion.py` |
| 3 | Falls nicht gebucht: optionale Liste zum Anzeigen und Auswählen | ausgeliefert | `views/recurring_bookings_dialog.py` (Typ- und Art-Filter, `optional_items`, Zeilenauswahl) | Cockpit → Fixkosten buchen | `test_autobook_optional_and_budget_multiselect.py` |
| 4 | Budgetwarnungen bei Überschreitung | ausgeliefert | `model/budget_warnings_model_extended.py` (`BudgetWarning`, `BudgetExceedance`) | Extras → Budgetwarnungen; automatisch beim Buchen | `test_picker_and_budget_reached.py` |
| 5 | Tags/Labels als zusätzliche Kategorisierung | ausgeliefert | `model/tags_model.py`, `views/tags_manager_dialog.py` | Extras → Tags verwalten; Filter im Tracking | `test_pot_reserve_and_tags_filters_v225.py`, `test_release_2225_tracking_tag_integrity.py` |
| 6 | Undo/Redo | ausgeliefert | `model/undo_redo_model.py` (`UndoRow`, `UndoRedoModel`) | Bearbeiten-Menü; Tastenkürzel konfigurierbar | `test_core.py`, `test_logic_deep_release_regressions.py`, `test_release_306_fixes.py` |
| 7 | Favoriten (häufige Kategorien pinnen) | ausgeliefert | `model/favorites_model.py`, `views/favorites_dashboard_dialog.py` | Kategorien-Kontextmenü; Schnellerfassung | `test_release_2216_unify_tools.py` |
| 8 | Sparziele setzen und tracken | ausgeliefert | `model/savings_goals_model.py` (inkl. `validate_savings_goal_bounds`), `views/savings_goals_dialog.py` | Reiter „Sparziele" | `test_release_221_reset_and_ux.py` |
| 9 | Backup / Wiederherstellung | ausgeliefert | `model/restore_bundle.py` (signiertes Bundle, SHA-256), `model/backup_auth.py`, `views/backup_restore_dialog.py` | Konto & Daten → Backup | `test_release_2210_backup_auth.py`, `test_startup_restore_regression.py` |
| 10 | Datenbank-Reset auf Standard | ausgeliefert | `model/database_management_model.py`, `views/database_management_dialog.py` | Konto & Daten → Datenverwaltung | `test_release_221_reset_and_ux.py` |
| 11 | Erscheinungsmanager: Farbprofile erzeugen und speichern | ausgeliefert | `theme_manager.py`, `views/theme_editor_dialog.py` | Einstellungen → Erscheinungsbild | `test_release_2233_sidebar_theming.py` |
| 12 | Windows-Installer packen | ausgeliefert | `installer/budgetmanager_setup.iss`, `tools/build_windows_installer.ps1`, `BudgetManager.spec` | Buildskript | `test_installer_icon_workflow.py` |
| 13 | Update-Tool (optional) | ausgeliefert | Paket `updater/` (Ed25519-signiertes Manifest, `startup_check.py`), `views/update_dialog.py`, `tools/verify_release_manifest.py` | Hilfe → Nach Updates suchen | `test_release_2229_manifest_verify_gate.py`, `test_release_2212_update_restore_hardening.py` |

## Hinweis zu Punkt 1

`model/recurring_transactions_model.py` ist ausdrücklich eine
Kompatibilitätsschicht. Der produktive Workflow für monatliche Fix- und
Wiederholungsbuchungen läuft über die Kategorien (`categories.is_fix`,
`categories.is_recurring`, `categories.recurring_day`) und markiert
Auto-Buchungen sprachunabhängig über die Spalte `tracking.source`.

Die frühere Per-Eintrag-Terminvorschau (`get_pending_bookings`,
`_is_already_booked`, `update_last_booking_date`) wurde in v2.1.0 entfernt: Sie
war produktiv nicht angebunden, und ihre Dublettenerkennung hing am
deutschsprachigen Marker `"Wiederkehrend (ID: …)"` — genau das nutzt der
Live-Pfad bewusst nicht mehr, weil es in englischer und französischer Oberfläche
gebrochen wäre.

Erhalten geblieben sind die Tabellen-CRUD für `recurring_transactions` und die
reinen Datumshelfer. Ein Soll-Buchungsdatum **je Eintrag** existiert damit im
Datenmodell, wird in der Oberfläche aber **je Kategorie** gepflegt. Wer echte
Pro-Eintrag-Termine mit unterschiedlichen Tagen innerhalb derselben Kategorie
braucht, benötigt eine Reaktivierung des Modells samt sprachunabhängiger
Dublettenerkennung. Das ist eine offene Produktentscheidung, kein Fehler.

## Weiterhin offen

Diese Punkte stehen unverändert in `docs/open-tasks.md`:

- Direkter PDF-Druck und Druckvorschau (aktuell CSV/TXT-Export).
- XLSX-Berichte als Ausgabeformat.
- `views/tabs/budget_tab.py:_apply_table_styles()` leitet Farben weiterhin aus
  `QPalette` statt aus dem App-Theme ab (gleicher Fehlertyp wie v2.2.33).
