# Changelog — BudgetManager

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [1.0.25] - 2026-03-04

### Neue Features
- **Modernisierung der UI-Icons**: Alle Emoji-Text-Präfixe in Buttons, Menüs und Aktionen wurden durch native QIcons ersetzt (zentral gesteuert über `utils/icons.py`).
- **Lokalisierung bereinigt**: Emojis wurden aus den Sprachdateien (`de.json`, `en.json`, `fr.json`) entfernt und durch reine Text-Labels ersetzt. Die Icons werden nun programmatisch zugewiesen.
- **Backup-Verwaltung**: Neue Option "Ältestes Backup automatisch löschen" in den Einstellungen hinzugefügt.
- **Automatisierte Releases**: GitHub Actions Workflow für den automatischen Build von Windows EXE, Linux Binaries und Portable ZIP-Archiven implementiert.
- **Update-Sicherheit**: Das Update-Manifest (`latest.json`) inklusive SHA256-Prüfsummen wird nun automatisch bei jedem Release generiert.

### Bugfixes
- **CategoryManagerDialog**: Behebung eines `AttributeError` ('warning_bg'), bei dem eine Schleifenvariable das globale Farbobjekt überschrieb.
- **Einstellungen**: Fehler korrigiert, bei dem `backup_auto_delete` und `auto_backup_keep` beim Schließen des Dialogs nicht korrekt gespeichert wurden.
- **Backup-Limit**: Die maximale Anzahl an Backups wird nun auch bei manuell ausgelösten Sicherungen korrekt erzwungen.
- **Sicherheits-Backups**: Automatische Backups vor Wiederherstellungen (`before_restore`) oder Resets wachsen nicht mehr unbegrenzt (Limit auf 3 Dateien gesetzt).
- **Statistik-Fix**: Der Zähler für gespeicherte Backups ignoriert nun temporäre Sicherheits-Backups.

### Bereinigung (Cleanup)
- **Repo-Hygiene**: AI-Konfigurationsdateien und Metadaten (`.claude/`, `.gemini/`, `.codex/`, `AGENTS.md`, etc.) wurden aus der Versionsverwaltung entfernt.
- **Datenschutz & Sicherheit**: `.gitignore` erweitert, um benutzerspezifische Daten wie `c.enc`, `users.json` und lokale Einstellungen strikt auszuschließen.
- **Build-Optimierung**: Benutzerspezifische Dateien wurden aus dem `BudgetManager.spec` Bundle entfernt, um saubere Builds zu gewährleisten.

---

## [1.0.24] - 2026-03-03

### Behoben
- **`sqlite3.OperationalError: cannot start a transaction within a transaction`** in `add_fixcosts` — `db_transaction()` rief `conn.execute("BEGIN")` auf, obwohl Python 3.14's sqlite3 bereits implizit eine Transaktion gestartet hatte (z.B. durch ein vorheriges DML-Statement). Fix: `db_transaction` prüft jetzt `conn.in_transaction` vor dem `BEGIN`. Ist bereits eine Transaktion aktiv, wird die innere `db_transaction` transparent durchgereicht ohne eigenes BEGIN/COMMIT — die äußere Transaktion übernimmt Commit/Rollback. (`model/database.py`)

### Technisch
- `db_transaction`: 3 neue Zeilen am Anfang: `if conn.in_transaction: yield conn; return`
- Alle bestehenden Aufrufe bleiben unverändert — bei einfachen (nicht-verschachtelten) Aufrufen verhält sich alles identisch wie vorher.
- Version: app_info.py + version.json auf 1.0.24 aktualisiert.

---

## [1.0.23] - 2026-03-03

### Release-Readiness-Fixes (7 Blocker behoben)

#### Behoben — KRITISCH
- **B-03: `load()` _internal_change Guard reaktiviert** — `load()` setzte in seinem `finally`-Block `_internal_change = False` bedingungslos. Das war ein partieller Rückfall des v1.0.19-Bugs. Fix: Save/Restore-Pattern (`_prev_ic`) wie in allen anderen 9 Methoden. (`views/tabs/budget_tab.py:609+816`)
- **B-01: Typ Display-String statt DB-Key in Dialogen** — `views/budget_entry_dialog.py`, `views/budget_entry_dialog_extended.py`, `views/category_properties_dialog.py` verwendeten `currentText()` für den Typ. In EN/FR-UI wurden falsche Strings in die DB geschrieben. Fix: `addItem(display, userData=TYP_*)` + `currentData()` durchgehend. Imports auf Modul-Ebene ergänzt.
- **B-02: recurring_transactions_dialog — "Einnahmen" kein DB-Key** — `addItems(["Ausgaben", "Einnahmen"])` verwendete "Einnahmen" statt `TYP_INCOME` ("Einkommen"). `get_data()` las `currentText()`. Fix: `addItem(display_typ(TYP_*), TYP_*)` + `currentData()` + `findData()` bei Edit-Mode. (`views/recurring_transactions_dialog_extended.py`)

#### Behoben — HIGH
- **B-04: Undo-Stack unbegrenzt wachsend** — Kein `MAX_STACK_SIZE` vorhanden. Fix: `MAX_UNDO_ENTRIES = 100` als Klassenkonstante, Pruning-Block am Ende von `record_operation()` löscht älteste Gruppen über dem Limit. (`model/undo_redo_model.py`)
- **B-05: Global Search — Doppelklick-Navigation nicht implementiert** — `_on_double_click()` zeigte nur eine MessageBox. Fix: Setzt `self.selected_result` (dict mit tab/type/source/category) und ruft `self.accept()` auf. `main_window._show_global_search()` navigiert nach `dialog.exec()` via `_goto_tab()` zum passenden Tab. (`views/global_search_dialog.py`, `views/main_window.py`)
- **B-06: build_windows.py VERSION hartkodiert "1.0.0"** — Fix: `import app_info; VERSION = app_info.APP_VERSION`. Generierter Installer-Name zeigt jetzt korrekte Version. (`build_windows.py`)

#### Behoben — i18n
- **H-05: Monatsnamen hartkodiert Deutsch** — `quick_add_dialog.py` hatte 9 von 12 Monatsnamen hartkodiert. Fix: `[tr(f"month.{i}") for i in range(1, 13)]`. Keys `month.1`–`month.12` in `de.json`, `en.json`, `fr.json` ergänzt. (`views/quick_add_dialog.py`, alle 3 Locale-Dateien)
- **H-08: Export-Dialog "Alle Jahre" Textvergleich** — `currentText() != "Alle Jahre"` schlug in EN/FR mit `ValueError` fehl. Fix: `addItem(tr("lbl.all_years"), None)` + `currentData() is None` Check. Key `lbl.all_years` in allen 3 Locale-Dateien ergänzt. (`views/export_dialog.py`)

### Technisch
- QA-Pass: alle 11 geänderten Python-Dateien kompilieren fehlerfrei
- i18n: 13 neue Locale-Keys in de/en/fr (month.1–12, lbl.all_years) — alle validiert
- Version: app_info.py + version.json auf 1.0.23 aktualisiert

---

## [1.0.22] - 2026-03-03

### Behoben
- **Qt-Warning beim Start: "Cannot filter events for objects in a different thread"** — Der `installEventFilter`-Aufruf auf die Budget-Tabelle fand während der Widget-Initialisierung statt, bevor der Qt-Event-Loop (`app.exec()`) gestartet war. In PySide6 / Python 3.14 haben QObjects in dieser Phase noch keine stabile Thread-Affinität, was die Warnung auslöste. Fix: `installEventFilter` wird via `QTimer.singleShot(0, ...)` auf den ersten Event-Loop-Tick verschoben — zu diesem Zeitpunkt sind alle Objekte korrekt im Main-Thread registriert.

### Technisch
- `views/tabs/budget_tab.py`: `self.table.installEventFilter(self)` → `QTimer.singleShot(0, lambda: self.table.installEventFilter(self))`.
- Funktionalität unverändert: Enter-Navigation und alle anderen Keyboard-Events werden weiterhin korrekt gefiltert.
- Version: app_info.py + version.json auf 1.0.22 aktualisiert.

---

## [1.0.21] - 2026-03-03

### Behoben
- **Undo/Redo funktioniert nach Budget-Edits nicht mehr** — Der Undo- und Redo-Button/Shortcut (Ctrl+Z / Ctrl+Shift+Z) waren nach dem Bearbeiten von Zellen inaktiv (grayed out). Root Cause: `_update_undo_redo_actions()` wurde nur beim Tab-Wechsel aufgerufen, aber nie nachdem Daten tatsächlich gespeichert wurden. Vor dem v1.0.19-Fix hatte der Akkumulierungsbug bei jedem `load()` spurious `budget.set_amount`-Aufrufe erzeugt, die den Undo-Stack füllten und die Undo-Action enabled hielten — als versteckter Nebeneffekt des Bugs. Nach der Bugfix-Bereinigung blieb der Stack leer und die Action disabled.

### Technisch
- `views/tabs/budget_tab.py`: Neues Signal `budget_data_changed = Signal()` hinzugefügt.
- `_persist_single_cell()`: Emittiert `budget_data_changed` nach `budget.set_amount()` (autosave).
- `_handle_parent_month_edit()`: Emittiert `budget_data_changed` nach direktem `budget.set_amount()`.
- `save()`: Emittiert `budget_data_changed` am Ende.
- `views/main_window.py`: `budget_data_changed`-Signal mit `_update_undo_redo_actions` verbunden.
- `_save_budget()`: Ruft `_update_undo_redo_actions()` explizit nach dem Speichern auf.
- Version: app_info.py + version.json auf 1.0.21 aktualisiert.

---

## [1.0.20] - 2026-03-03

### Behoben
- **Segmentation Fault bei Enter-Taste in Budget-Tabelle** — Fataler Absturz (SIGSEGV) in `eventFilter` beim Drücken von Enter/Return in einer Tabellenzelle. Root Cause: `setCurrentCell()` wurde synchron innerhalb von `eventFilter` aufgerufen, was Qt-intern `currentChanged → commitData → installEventFilter` triggerte und dadurch `eventFilter` rekursiv (reentrant) aufrief, während Qt's interner Zustand noch instabil war. Fix: `setCurrentCell`-Aufrufe mittels `QTimer.singleShot(0, ...)` auf nach dem aktuellen Event-Zyklus verschoben.

### Technisch
- `views/tabs/budget_tab.py`: Import von `QTimer` aus `PySide6.QtCore` hinzugefügt.
- `eventFilter()`: Beide `self.table.setCurrentCell(...)` Aufrufe in `QTimer.singleShot(0, lambda: ...)` gekapselt.
- Version: app_info.py + version.json auf 1.0.20 aktualisiert.

---

## [1.0.19] - 2026-03-03

### Behoben
- **Budget-Tab: Kumulierung bei Tab-Wechsel/Reload** — Parent-Werte (z.B. Versicherung 1650.00) wuchsen bei jedem Öffnen um den Kinder-Betrag (1600). Root Cause: `_update_total_row()` und `_recalc_footer()` setzten `_internal_change = False` in ihrem `finally`-Block, obwohl der übergeordnete `load()` dieses Flag auf `True` gesetzt hatte. Dadurch feuerten `setBackground()`/`setFont()` in `_apply_table_styles()` ungeschützte `itemChanged`-Signale, die den angezeigten Gesamtwert (1650) als Puffer in die DB zurückschrieben. Beim nächsten Load: Puffer=1650 + Kinder=1600 = 3250, usw.

### Technisch
- **Save/Restore Pattern für `_internal_change`**: Alle 9 Stellen in `budget_tab.py`, die `_internal_change` in `try/finally` setzen, speichern jetzt den vorherigen Zustand (`_prev = self._internal_change`) und stellen ihn im `finally` wieder her (`self._internal_change = _prev`). Dies verhindert, dass verschachtelte Aufrufe den Guard des äußeren Kontexts vorzeitig aufheben.
- Betroffene Methoden: `_update_total_row()`, `_recalc_footer()`, `_update_parent_chain()`, `_handle_parent_month_edit()`, `_handle_leaf_ask_due()`, `_handle_normal_edit()`, `_handle_total_column_edit()`, `_recalc_row_total()`, `_handle_tag_edit()`.
- Version: app_info.py + version.json auf 1.0.19 aktualisiert.

---

## [1.0.18] - 2026-03-03

### Behoben
- **Budget-Tab: Parent-Zellen zeigen korrekte Gesamtsumme (kein "+" Suffix)** — Rollback auf v1.0.9-Logik. Parent-Monatszellen zeigen wieder `puffer + kinder_summe` als schlichte Zahl (z.B. "1650.00"). Der Nutzer gibt den Puffer (50) ein; die Anzeige zeigt automatisch `50 + 1600 = 1650.00`. Kein Akkumulationsproblem, weil beim Reload `_build_tree_flat` den Puffer (50) frisch aus der DB liest und die Anzeige stabil bei 1650.00 bleibt.
- **Budget-Tab: Jahresspalte Parent-Zellen** — Zeigt ebenfalls die Gesamtsumme ohne "+" Suffix.
- **Budget-Tab: `_update_parent_chain`** — Berechnet `new_total = buf + children_sum` und setzt den Anzeigewert korrekt.
- **Budget-Tab: `_recalc_row_total`** — Jahresspalte für Parent-Zeilen zeigt jetzt Gesamtsumme ohne "+" Suffix.

### Technisch
- `load()`: `_cell_text = fmt_amount(total_val)` für alle Zeilen (kein `has_children`-Branch mehr).
- `_handle_parent_month_edit()`: `parse_amount(item.text())` (kein `_parse_cell_amount`), `display = typed_puffer + children_sum`, `item.setText(fmt_amount(display))`.
- `_update_parent_chain()`: `new_total = buf + children_sum`, `it.setText(fmt_amount(new_total))`.
- `_recalc_row_total()`: `tot.setText(fmt_amount(row_total))` ohne "+" Suffix.
- Version: app_info.py + version.json auf 1.0.18 aktualisiert.

---

## [1.0.17] - 2026-03-03

### Behoben
- **Budget-Tab: Akkumulation bei Budget-Reload** — Parent-Monatszellen zeigten bisher `puffer + kinder_summe` als Anzeigewert (z.B. "1650.00+"). Bei erneutem Laden wurde dieser Anzeigewert fälschlicherweise als neuer Puffer gespeichert, was zu exponentiellem Wachstum führte (`1650 + 1600 = 3250` usw.). Fix: Parent-Zellen zeigen jetzt nur den blanken Pufferwert (z.B. "50+"). Die Gesamtsumme (Puffer + Kinder) ist ausschließlich im Tooltip sichtbar.

### Technisch
- `load()` in budget_tab.py: `_cell_text = fmt_amount(max(0, own_val)) + "+"` statt `(max(0, own) + children):.2f + "+"`.
- `_update_parent_chain()`: zeigt jetzt nur den Puffer, nicht Puffer + Kinder.
- `_handle_parent_month_edit()`: speichert `typed_puffer`, zeigt nur Puffer im Cell-Text.
- `_build_parent_tooltip()`: liest Puffer aus `_buffer_cache` statt aus dem Zellentext.
- Version: app_info.py + version.json auf 1.0.17 aktualisiert.

---

## [1.0.16] - 2026-03-03

### Geändert
- **Budget-Tab: Parent-Monatszellen zeigen korrekte Gesamtsumme** — Oberkategorie-Zellen zeigen jetzt immer eine sichtbare Zahl mit "+" Suffix (z.B. "1600.00+"). Root-Cause: negativer Puffer-Wert (`own_val < 0`) wurde bei der Anzeige ignoriert. Neue Formel: `display_total = max(0.0, own_val) + children_sum`. Vorher zeigte `fmt_amount(0.0)` einen Leerstring → Zelle zeigte nur "+" ohne Betrag.
- **Budget-Tab: Jahresspalte Parent-Zellen** — `row_display_total` für die Jahresspalte wird jetzt nach derselben Logik berechnet; Oberkategorien zeigen auch dort den korrekten Gesamtwert mit "+" Suffix.
- **Budget-Tab: Tooltips für Parent-Zellen** — Tooltips (Monat und Jahr) zeigen jetzt `Puffer = max(0, own_val)`; negative Puffer-Werte sind nicht mehr sichtbar.
- **Budget-Tab: `_update_parent_chain`** — Setzt jetzt ebenfalls das read-only Flag und den korrekten Anzeigewert für Oberkategorie-Zellen.

### Technisch
- Formel-Änderung in budget_tab.py: `display_total = max(0.0, own_val) + children_sum` ersetzt die alte Logik die `own_val < 0` ignorierte.
- Version: app_info.py + version.json auf 1.0.16 aktualisiert.

---

## [1.0.15] - 2026-03-03

### Geändert
- **Budget-Tab: Parent-Kategorie Tooltip** — Beim Hovern über eine Oberkategorie (z.B. "Versicherung") wird jetzt angezeigt: Puffer-Wert oben, dann alle Unterkategorien mit Beträgen, dann Summe der Kinder. Kein hardcodierter Text, alles via i18n-Sprachfiles.
- **Budget-Tab: "+" Marker** — In der Jahresspalte (Total) wird für Oberkategorien ein "+" Zeichen angehängt (z.B. "1'600.00+"), um anzuzeigen dass der Wert eine Summe aus Unterkategorien ist.
- **Tab-Leiste: Position wählbar** — Im Menü "Ansicht → Tab-Leiste" kann die Position (Links/Rechts/Oben/Unten) gewählt und die Tab-Leiste ein-/ausgeblendet werden. Standard: Links. Einstellung wird persistent gespeichert.
- **Windows Installer Fix** — Zeile 33 in `installer/budgetmanager_setup.iss`: `SetupIconFile=icon.ico` auskommentiert (Datei fehlte → Inno Setup-Fehler). Dokumentation und Generator-Script `tools/create_icon.py` erstellt.
- **build_windows.py Fixes** — Doppelter hiddenimport entfernt, fehlendes `import os` im Spec-Template ergänzt.
- **i18n: Neue Schlüssel** — `budget.tooltip.puffer`, `budget.tooltip.children_sum`, `budget.parent.marker`, `menu.tab_bar*` in de/en/fr Sprachfiles.

### Technisch
- Neue Hilfsfunktion `_parse_cell_amount()` in budget_tab.py (parst auch "X + Y" Format).
- `_build_parent_tooltip()` komplett neu (liest live aus Tabellenzellen, vollständig i18n).
- `_build_tree_flat()` gibt jetzt zusätzlich `direct_children_by_name` zurück.
- Version: app_info.py + version.json auf 1.0.15 aktualisiert.

---

## [1.0.10] - 2026-03-02
_Siehe separate Release Notes für diese Version._

## [1.0.0] - 2026-02-20
### Added
- Erstes stabiles Release mit vollständiger Feature-Suite (Budget, Tracking, wiederkehrende Buchungen, Fixkosten-Check, Warnungen, Tags, Favoriten, Sparziele, Backup/Restore, DB-Management, i18n, Updater).
- Breites Logging-Rollout in Models und Views zur Verbesserung der Wartbarkeit.

### Changed
- Stumme try-except Blöcke durch geloggte Fehlerbehandlungen ersetzt.

### Security
- SQL-Injection-Härtung durch Whitelisting von Tabellennamen in kritischen Datenbankoperationen.

## [0.4.8.0] - 2026-02-20
### Added
- JSON-basiertes i18n-System für Übersetzungen (locales/de.json, locales/en.json mit je 337 Strings).
- Neues Modul utils/i18n.py mit tr(), trf(), display_typ(), db_typ_from_display(), available_languages(), set_language() und Auto-Init.
- Robuster Fallback-Mechanismus für fehlende Übersetzungen (de -> key).

### Changed
- Das Menüsystem (53 Aufrufe, alle 6 Menü-Methoden) vollständig auf das i18n-System umgestellt.
- Alle hartcodierten deutschen Menü-Strings aus main_window.py entfernt.

## [0.4.7.0] - 2026-02-20
### Changed
- Systematisches Refactoring aller Methoden mit mehr als 200 Zeilen Code in kleinere Submethoden (5 Methoden aufgeteilt, Methoden >200 Zeilen: 5 -> 0).
- Unerreichbarer Code nach return-Anweisungen in budget_tab.py entfernt.
- TODO-Navigation in global_search_dialog.py implementiert.

### Fixed
- Fehlender Import für QMessageBox in global_search_dialog.py ergänzt.

## [0.4.6.0] - 2026-02-19
### Added
- Logging in neun weiteren View-Dateien implementiert.
- Neue Model-Methoden: TagsModel.usage_count(), TagsModel.name_exists(), CategoryModel.count(), CategoryModel.delete_all(), BudgetModel.count(), TrackingModel.count(), BudgetModel.get_amount(), TrackingModel.get_month_total().

### Changed
- SQL-Queries aus Views in entsprechende Models verschoben (19 -> 10 Queries in Views; MVC-Trennung gestärkt).
- Import-Reihenfolge in main_window.py und backup_restore_dialog.py gemäß PEP 8 korrigiert.
- from __future__ import annotations in allen 72 Python-Dateien vereinheitlicht (7 nachgerüstet).

### Fixed
- Stumme except: pass Blöcke durch logger.debug() ersetzt.

## [0.4.5.0] - 2026-02-17
### Added
- Neues Modul views/ui_colors.py zur zentralen Verwaltung von UI-Farben (UIColors-Dataclass, automatischer Fallback, Dark-Mode-Support, Cache mit Invalidierung).
- Theme-Integration in über 20 Dialogen und Ansichten; rund 160 hartcodierte Farbwerte ersetzt.

### Fixed
- Shortcut-Kollision Ctrl+E behoben (Bearbeiten -> F2).
- Shortcut-Kollision Ctrl+N behoben (Budget-Neu -> Insert).
- Kritischer Variable-Shadowing-Bug in overview_tab._load_main_categories() behoben.
- 14 Enum-Stile auf moderne Qt6-Syntax modernisiert.
- 14 stumme Exception-Handler durch logger.debug() ersetzt.

### Changed
- Manuelle Währungsformatierungen durch zentrale format_money()-Funktion ersetzt.
- 33 MessageBox-Titel korrigiert; 19 Dialogtitel vereinheitlicht.

## [0.4.4.0] - 2026-02-16
### Fixed
- Kritischer Bug: Keine Vorschläge von Januar bis Mai durch vorzeitigen Abbruch behoben; jahresübergreifende Analyse implementiert.
- Inkompletter aktueller Monat verfälschte Analyse; Analyse startet nun beim abgeschlossenen Vormonat (use_current_month=False).
- Vorzeichen-Ratio-Threshold von 1.0 auf 0.7 gesenkt, um mehr valide Trends zu erkennen.
- Lückenmonat blockierte alle Vorschläge; Fenster erweitert sich nun über Lücken (bis 3x months_back).
- Default-Inkonsistenz budget_suggestion_months (settings.py=6 vs. Dialog=3) auf einheitlich 3 korrigiert.
- Fehlende abs()-Behandlung in BudgetWarningsModel für Ausgaben und Ersparnisse.
- get_type_suggestions scheiterte am Jahresanfang; jahresübergreifende Analyse implementiert.
- Stumme Fehlerbehandlung im Vorschläge-Banner durch logger.warning() ersetzt.

## [0.3.9.0] - 2026-02-14
### Added
- Neue Kontoverwaltung (Menü Konto) mit drei Tabs: Profil, Passwort/PIN und Sicherheitsstufe (Quick/PIN/Passwort).
- Neue Methode UserModel.change_display_name().

### Fixed
- Einstellungsdialog zeigt bei verschlüsselten Konten eine Informationsbox statt des Datenbankpfads.
- Dialoge verwenden setMinimumSize() statt setFixedSize() und sind nun skalierbar.
- Budget-Vorschläge nutzen dynamische effective_min = min(min_consecutive_months, len(check_months)).

## [0.3.8.0] - 2026-02-14
### Added
- Optionale Benutzerverwaltung mit AES-256/Fernet-verschlüsselten Datenbanken pro Benutzer.
- Login-Dialog beim Anwendungsstart; Multi-User-Unterstützung mit separaten verschlüsselten DBs.
- Neue Module: model/crypto.py, model/user_model.py, views/login_dialog.py.

### Removed
- Erscheinungsmanager entfernt (Duplikat zum ThemeManager).
- Nicht genutzten Menüpunkt Wiederkehrende verwalten entfernt.
- 8 tote Dateien bereinigt.

### Security
- Verschlüsselte DB läuft vollständig im RAM; Klartext wird nie auf die Festplatte geschrieben.
- Auto-Save alle 5 Minuten und per atexit-Hook.
- PBKDF2-HMAC-SHA256 mit 200.000 Iterationen für die Schlüsselableitung.

## [0.3.7.1] - 2026-02-13
### Fixed
- Kritischer Bug NameError: name Qt is not defined in settings_dialog.py durch Hinzufügen des fehlenden PySide6.QtCore-Imports behoben.

## [0.3.7.0] - 2026-02-13
### Added
- Konfigurierbare Tastenkürzel für häufig genutzte Aktionen.
- Funktionale Auto-Backup-Logik mit konfigurierbarem Intervall.

### Changed
- Konsistenz der Kontextmenüs und Interaktionsmuster verbessert.

## [0.18.3] - 2025-07-12
### Added
- Smart Search mit kategorisierten Treffern.
- Quick Actions für häufige Folgeschritte.
- Auto-Refresh relevanter Listen nach Änderungen.
- Verbesserte Tastaturbedienung in Suchdialogen.

### Fixed
- Fokusprobleme nach Suchaktionen behoben.
- Einzelne Darstellungsfehler in Ergebnislisten korrigiert.
- Stabilitätsprobleme in seltenen Such-/Update-Sequenzen reduziert.

## [0.18.2] - 2025-07-05
### Added
- Suchfilter erweitert.

## [0.18.1] - 2025-07-01
### Added
- Suchgrundlagen.

## [0.18.0] - 2024-12-24
### Added
- Sieben vordefinierte Themes: Standard Hell, Standard Dunkel, Hell-Grün, Dunkel-Blau, Dunkel-Grün, Kontrast-Schwarz/Weiß, Pastell-Sanft.
- Neue Theme-Profil-Keys für Dropdown-Farben: dropdown_bg, dropdown_text, dropdown_selection, dropdown_selection_text, dropdown_border.
- Neue ThemeManager-API-Methoden: get_all_profiles(), get_profile(), get_current_profile(), apply_theme(), create_profile(), update_profile(), delete_profile(), export_profile(), import_profile(), get_type_colors().

---

## Versionshistorie (Kompakt)

### Aktuelle Linie
- `v0.2.2.5` (2025-09-26): Aufgabenmanagement und UI-/Stabilitätsverbesserungen
- `v0.2.2.4` (2025-09-15): Verbesserte Aufgabeninteraktionen
- `v0.2.2.3` (2025-09-14): Reports und Performance-Optimierungen
- `v0.2.2.2` (2025-09-08): Wiederkehrende Buchungen erweitert
- `v0.2.2.1` (2025-08-31): Organisatorische Basisfunktionen
- `v0.2.0` (2025-08-20): Dashboard- und Reporting-Basis

### Search-/UX-Linie
- `v0.18.3` (2025-07-12): Smart Search, Auto-Refresh, Quick Actions
- `v0.18.2` (2025-07-05): Suchfilter erweitert
- `v0.18.1` (2025-07-01): Suchgrundlagen
- `v0.18.0` (2025-06-28): Refactoring-Vorbereitung

### Frühe stabile Linie
- `v0.17.x` (2025-06): Konten- und Transaktionsverbesserungen
- `v0.16.x` (2025-05): stabile SQLite-Kernfunktionen

### Changed
- Theme Manager auf JSON-basierte Profile umgestellt (Speicherort: ~/.budgetmanager/themes/).
- Automatische Migration: bestehendes appearance_profile bleibt erhalten; neue Standardprofile beim ersten Start erstellt.

### Fixed
- Anzeigefehler mit schwarzer Schrift auf schwarzem Hintergrund in Dropdowns behoben.
- Typ-spezifische Farbgebung bleibt in allen Themes korrekt erhalten.
- Theme-Einstellungen gehen nach Neustart nicht mehr verloren.

## [0.17.0] - 2024-12-23
### Added
- Wiederkehrende Transaktionen: Tabelle recurring_transactions mit Soll-Buchungsdatum (1-31), Start/Enddatum, Aktivierungsstatus und Tracking des letzten Buchungsdatums.
- Model RecurringTransactionsModel mit CRUD; Dialog RecurringTransactionsDialogExtended.
- Intelligente Budget-Warnungen: gewichteter Durchschnitt letzter 6 Monate, 10% Sicherheitspuffer, automatischer Dialog ab 3 Monaten Überschreitung.
- BudgetWarningsModelExtended mit Häufigkeitszähler und Überschreitungsstatistiken; Dialog BudgetAdjustmentDialog.
- Datenbank-Management-Dialog: Reset, Backup-Liste mit Metadaten, VACUUM-Optimierung, JSON-Export; Model DatabaseManagementModel.
- Windows-Installer (Inno Setup, mehrsprachig) und Build-Skript build_windows.py.
- Auto-Updater gegen GitHub Releases mit SHA256-Verifikation, Fortschrittsanzeige, Stable/Beta-Channel.

### Changed
- Datenbankschema auf Version 5 aktualisiert; Performance-Indizes hinzugefügt.

### Fixed
- Edge-Cases bei Datumsberechnung (z.B. 31. im Feb wird auf den letzten Monatstag gesetzt).
- Zeitzone-Probleme und Memory-Leaks in langen Sessions behoben.

## [0.16.0] - 2024-11-XX
### Added
- Tags/Labels zur zusätzlichen Kategorisierung von Transaktionen.
- Undo/Redo-Funktion für alle Änderungen.
- Favoriten für häufig verwendete Kategorien.
- Sparziele setzen und verfolgen.
- Budget-Warnungen mit konfigurierbaren Schwellenwerten.
- Theme Profiles: Speichern und Laden von Farbschemata.
- Backup und Restore-Funktionalität.
- Globale Suche über alle Transaktionen.

### Changed
- Datenbankschema auf Version 4 aktualisiert.
- UI-Verbesserungen in allen Dialogen; Performance-Optimierungen bei großen Datenmengen.

### Fixed
- Absturz bei leerem Budget behoben.
- Sortierung in der Kategorie-Tabelle korrigiert.
- Excel-Export mit Sonderzeichen korrigiert.

## [0.15.0] - 2024-10-XX
### Added
- Fixkosten-Verwaltung.
- Monatliche Übersicht mit Visualisierungen.
- Quick-Add-Dialog für schnelle Buchungen.
- Tastaturkürzel für häufige Aktionen.

### Changed
- UI-Design modernisiert; Navigation verbessert; Ladezeiten optimiert.

## [0.14.0] - 2024-09-XX
### Added
- Export nach Excel (.xlsx).

### Changed
- Kategorien-Verwaltung und Budget-Tracking mit monatlicher Ansicht verbessert.

### Fixed
- Datum-Sortierung in der Tracking-Tabelle korrigiert.
- Rundungsfehler bei Währungen behoben.

## [0.13.0] - 2024-08-XX
### Added
- Diagramme zur Visualisierung von Ausgaben.
- PDF-Export von Reports.
- Filtern nach Kategorien und Zeitraum.

## [0.12.0] - 2024-07-XX
### Added
- Fixkosten-Funktionalität.
- Wiederkehrende Buchungen (Basis-Version).
- Notizen zu Transaktionen.

### Changed
- Datenbank-Schema optimiert; UI für bessere Übersichtlichkeit angepasst.

## [0.10.0] - 2024-05-XX
### Added
- Jahresübersicht und Budget-Ist-Vergleich.
- Kategorien-Analyse.

## [0.8.0] - 2024-03-XX
### Added
- Export-Funktionen (CSV, Excel).
- Suchfunktion für Transaktionen.
- Mehrjahres-Support.

## [0.5.0] - 2024-01-XX
### Added
- Basis-Tracking von Einnahmen und Ausgaben.
- Budget-Planung nach Kategorien.
- SQLite als Datenbank-Backend.
- Kategorien-Verwaltung.
