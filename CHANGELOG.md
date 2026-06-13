# Version 1.0.38 - i18n Hardcoding Fix + Kategorie Drag & Drop

Datum: 13. Juni 2026

## Fixes
- `tools/i18n_audit.py` repariert: Ignore-Filter prüft nun relative Pfade, damit `/mnt/data/...` nicht mehr das gesamte Projekt ausblendet.
- Verdächtige hardcodierte UI-Texte in den aktiven Python-Views/Dialogen auf i18n-Keys umgestellt.
- Fehlende i18n-Keys in `de.json`, `en.json` und `fr.json` ergänzt.
- Audit läuft wieder ohne fehlende Keys und ohne verdächtige hardcoded UI-Strings.

## Usability
- Kategorien-Manager unterstützt jetzt Drag & Drop für Ebenenwechsel:
  - Kategorie auf Kategorie ziehen → wird Child/Unterkategorie.
  - Kategorie auf Typ-Header ziehen → wird Parent/Hauptkategorie.
- Kontextmenü-Aktion ergänzt: „Zur Hauptkategorie machen“.
- Kategorien-Filter arbeitet nun mit internen Werten (`currentData`) statt mit übersetzten Texten.

---

# Changelog — BudgetManager

Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.
Format basiert auf [Keep a Changelog](https://keepachangelog.com/de/1.0.0/).

---

## [1.0.37] - 2026-06-13 — Setup-Assistent: Usability & i18n-Konsistenz

### Schritt-Übersicht, Sperr-Hinweise und vollständige Übersetzbarkeit

- **Neu: Schritt-Sidebar** links im Setup-Assistenten — zeigt alle Schritte mit Nummerierung, ✓ für abgeschlossene Schritte und Fettdruck für den aktuellen Schritt. Bereits besuchte Schritte sind **anklickbar** (direktes Zurückspringen), noch nicht erreichte sind ausgegraut. Der nicht gewählte Kategorien-Pfad (Manager vs. Excel-Import) wird in der Liste **ausgeblendet** und folgt live der Radio-Auswahl.
- **Neu: Sperr-Hinweis** — wenn „Weiter" bei blockierenden Schritten deaktiviert ist, erscheint jetzt ein 🔒-Hinweis, der erklärt, *was* zuerst zu tun ist (Kategorien anlegen, Excel importieren, Budget-Fenster öffnen), statt nur einen toten Button zu zeigen.
- **Fortschrittsanzeige** im Header zählt nur noch sichtbare Schritte („Schritt x von 10" statt x/11 inkl. verstecktem Branch).
- **Bugfix**: Das `_finishing`-Flag wurde im Hide/Show-Context-Manager abgefragt, aber nie gesetzt — nach Klick auf „Fertig" konnte der Assistent kurz wieder aufpoppen, falls ein Kinddialog beteiligt war. Jetzt wird das Flag in `_finish()` gesetzt.
- **i18n-Konsistenz**: Alle ~40 hardcodierten deutschen Strings im Setup-Assistenten (Buttons „Weiter →"/„Fertig", Seiten-Überschriften, Beschreibungstexte, Statusmeldungen, Fehlermeldungen, Dateifilter, MessageBox-Titel) laufen jetzt über `tr()`/`trf()`. Neue `setup.*`-Keys in **de/en/fr** ergänzt (je 40 Keys, alle drei Sprachen synchron bei 108 Setup-Keys). Schritt-Titel der Sidebar nutzen einheitliche `setup.nav_*`-Keys.

---

## [1.0.36] - 2026-06-12 — Setup-Assistent: Fenster-Layering-Fix

- Der Setup-Assistent erzwingt nicht mehr `WindowStaysOnTopHint` — daraus geöffnete Dialoge (Kategorien-Manager, Budget-Fenster, Tracking) werden nicht mehr verdeckt.
- Neuer Context-Manager `_setup_hidden_while_child_open()`: Der Assistent versteckt sich, solange ein Kinddialog offen ist, und kehrt danach automatisch in den Vordergrund zurück (an 5 Stellen eingesetzt).

---

## [1.0.35] - 2026-06-12 — CSV-Kategorien-Roundtrip mit Spaltenlösung

### Kategorien per CSV exportieren, manuell bearbeiten, wieder importieren

- **Neu**: Kategorien lassen sich als **CSV mit getrennten Spalten** exportieren und re-importieren — ohne die als unhandlich empfundene `›`-Pfadnotation in einer Spalte. Format:
  `Typ, Hauptkategorie, Unterkategorie, Fix (0/1), Wiederkehrend (0/1), Tag (1-31)`.
  Top-Level-Kategorie: Unterkategorie-Spalte leer. Unterkategorie: Hauptkategorie = Name der Elternkategorie.
- **Setup-Assistent (Starter)**: Neuer Button „Vorlage als CSV exportieren"; der Import akzeptiert jetzt `*.xlsx` **und** `*.csv` (Dispatch nach Dateiendung).
- **Robustheit**:
  - Trennzeichen (`,` `;` Tab) wird automatisch erkannt (deutsches Excel nutzt oft `;`).
  - UTF-8 mit BOM beim Schreiben → Umlaute öffnen in Excel korrekt.
  - Namen mit Schrägstrich (`Miete/Hypothek`, `ÖV (Abo/Billette)`, `Serafe (Radio/TV)`) bleiben **ein** Blatt — der CSV-Splitter trennt nur am expliziten `›`-Marker, nicht an `/`. (Der xlsx-„Pfad"-Splitter trennt weiterhin auch an `/`, wie dort dokumentiert.)
  - Tiefere Verschachtelung (>2 Ebenen) wird als Fallback `Kind › Enkel` in der Unterkategorie-Spalte ausgedrückt — kein Datenverlust.
- **Aufräumen**: xlsx- und CSV-Import teilen sich jetzt eine **gemeinsame Kern-Routine** (`_apply_path`/`_ensure_category`) — keine doppelte Upsert-Logik mehr (gleiche Lehre wie beim Default-Kategorien-Fix). Elternknoten überschreiben dabei ihre Flags nicht mehr, wenn sie über eine eigene Zeile gesetzt wurden.
- Der kombinierte CSV-Export (Export-Dialog, Tracking+Budget+Kategorien) nutzt im Kategorien-Block nun ebenfalls das Spaltenformat inkl. Tag.
- Verifiziert (In-Memory-DB): voller Export→Import-Roundtrip identisch (44 Kategorien), idempotent, Slash-Namen intakt, Semikolon-CSV erkannt, 3-Ebenen-Fallback korrekt; xlsx-Import nach Refactor unverändert funktionsfähig.

---

## [1.0.34] - 2026-06-12 — Standard-Kategorien mit Unterkategorien

### Vorab eingestellte Kategorien jetzt inkl. Unterkategorien

- **Vorher**: Schema und `data/default_categories.json` kannten zwar ein `children`-Feld, aber der Loader `load_default_categories()` ignorierte es und beide Seeding-Pfade (Erststart `ensure_defaults`, Reset) fügten nur **flach** ein. Unterkategorien wurden also nie vorab angelegt.
- **Jetzt**:
  - `DefaultCategory` trägt `children`; der Loader parst Unterkategorien **rekursiv** (Kinder erben den `typ` des Eltern-Eintrags).
  - Neue gemeinsame Routine `insert_default_categories(conn)` legt **Parent zuerst, dann Kinder mit `parent_id`** an. `INSERT OR IGNORE` macht sie idempotent; sie ist schema-tolerant (nutzt `parent_id`/`sort_order` nur, wenn vorhanden).
  - **Erststart und Reset** nutzen jetzt dieselbe Routine — beide Pfade können nicht mehr auseinanderlaufen (die alte Doppel-Logik in `database_management_model.py` entfällt).
  - `data/default_categories.json` ersetzt durch eine **saubere CH-Haushaltsvorlage** (ohne persönliche Namen): 17 Top-Level + 27 Unterkategorien (44 gesamt), gruppiert in Wohnen, Versicherungen, Kommunikation & Medien, Mobilität, Lebenshaltung, Freizeit, Sonstiges sowie Altersvorsorge/Rücklagen bei den Ersparnissen.
- Verifiziert (In-Memory-DB): 44 Kategorien korrekt mit `parent_id` verknüpft, Typ-Konsistenz Eltern/Kind OK, idempotent (zweiter Lauf 0 neu), `build_tree` rendert die Hierarchie wie erwartet (Ausgaben 8 Top-Level / 23 Unterkategorien).

---

## [1.0.33] - 2026-06-12 — Updater-Crash auf Windows-Konsole behoben

### UnicodeEncodeError bei `--check-update` / `--apply-update`

- **Vorher**: Der Updater gibt Statusmeldungen mit Emojis aus (`⬇️`, `❌`, `✓`). Die Windows-Konsole nutzt standardmäßig die Codepage cp1252, die diese Zeichen nicht kodieren kann — `print()` warf einen `UnicodeEncodeError: 'charmap' codec can't encode characters in position 0-1`. Das beendete den Updater-CLI-Modus mit einem „Unhandled exception in script"-Dialog (Traceback in `updater/check_update.py`, Zeile 42).
- **Jetzt**: Neue Hilfsfunktion `enable_utf8_console()` in `updater/common.py` stellt `stdout`/`stderr` auf UTF-8 um (`errors="replace"` als Sicherheitsnetz). Sie wird zu Beginn von `check_update.main()`, `apply_update.main()` und `generate_manifest.main()` aufgerufen. Robust gegen fehlende Streams (windowed PyInstaller-Build ohne Konsole: Streams sind dann `None` oder ohne `reconfigure` — wird sauber übersprungen).
- Verifiziert: cp1252-Stream reproduziert den exakten Fehler; nach `enable_utf8_console()` wird die Emoji-Zeile fehlerfrei als UTF-8 geschrieben.

---

## [1.0.32] - 2026-06-12 — Headless-Hänger im closeEvent behoben

### GUI-Smoke-Tests blockierten beim Schließen

- **Vorher**: Lief Auto-Save nicht, zeigte `MainWindow.closeEvent` eine modale `QMessageBox.question` (Speichern/Verwerfen/Abbrechen). Headless (`QT_QPA_PLATFORM=offscreen`) klickt niemand — der `exec()`-Aufruf blockierte für immer. Der Test-*Lauf* meldete zwar `PASSED`, der Prozess beendete sich aber nicht und musste per `timeout` abgebrochen werden. Ausgelöst wurde der Dialog auch durch das automatische Widget-Schließen beim Teardown.
- **Jetzt**: `closeEvent` prüft ein Flag `self._suppress_close_confirm`; ist es gesetzt, wird ohne Dialog akzeptiert. Der Auto-Save-Pfad und das normale Verhalten für Endnutzer bleiben unverändert (Guard greift erst *nach* dem Auto-Save-Early-Return und *vor* dem Dialog).
- Die Fixture in `tests/test_gui_smoke.py` setzt das Flag direkt nach der Erzeugung des Fensters, sodass die Tests von selbst durchlaufen — ohne `timeout`-Krücke.
- Gegencheck: Alle übrigen `.exec()`/`QMessageBox`-Aufrufe in `main_window.py` liegen in Menü-/Button-Handlern und feuern nur bei Nutzerinteraktion, nicht im Start- oder Schließpfad.

---

## [1.0.31] - 2026-06-11 — Qualitäts-Fixes (Punkte 2, 3, 4)

### GUI-Smoke-Tests in CI (Punkt 2)

- **Neue Tests `tests/test_gui_smoke.py`**: Starten die echte Qt-App headless (`QT_QPA_PLATFORM=offscreen`) und prüfen genau die Pfade, die in v1.0.29 still kaputt waren — MainWindow-Start (hätte den fehlenden `trf`-Import gefangen), Sprachwechsel mit Menü-Neuaufbau (hätte den `_setup_menus`-Bug gefangen), Tab-Durchschalten, Statusmeldungen mit `trf()`.
- Ohne installiertes PySide6 werden die Tests sauber übersprungen (verifiziert), in CI laufen sie vor jedem Build. Der Linux-Runner bekommt dafür die nötigen Qt-Systemlibs (libegl1 etc.).

### Undo/Redo-Gruppen transaktional (Punkt 3)

- **Vorher**: Jede Operation einer Undo-/Redo-Gruppe committete einzeln. Schlug eine Operation mitten in der Gruppe fehl, blieb ein halber Undo zurück — erste Operationen angewendet, Rest nicht, Stack-Eintrag teilweise verschoben.
- **Jetzt**: Die gesamte Gruppe (alle Operationen + Stack-Verschiebung + Löschung) läuft in einer Transaktion. Bei einem Fehler wird vollständig zurückgerollt, `undo()`/`redo()` liefern `False`, und eine Log-Warnung benennt die Gruppe und den Fehler. Die Einzel-Commits in `_delete_by_id`/`_insert_row`/`_update_by_id`/`_rename_cascade` wurden entfernt (nur intern verwendet, verifiziert).
- **Neuer Regressionstest** `test_undo_group_is_atomic`: provoziert einen Fehler mitten in einer Gruppe und prüft, dass die Datenzeile unangetastet bleibt, die Stack-Gruppe vollständig erhalten ist und der Redo-Stack keine Reste enthält.

### Stille except-Blöcke beseitigt (Punkt 4)

- **Alle 11 verbliebenen `except: pass`-Blöcke** loggen jetzt — dieselbe Fehlerklasse, die die „unerklärlichen Instabilitäten" von v1.0.29 verursachte. Zwei davon waren funktional relevant und loggen als WARNING:
  - `overview_budget_panel.py`: Fehlgeschlagene **Budget-Vorschläge** fehlten still in der Übersicht
  - `overview_budget_panel.py`: Fehlgeschlagene **Monatsüberträge** fehlten still in der Übersicht (inkl. Monat/Jahr/Typ im Log)
- Außerdem als WARNING: defekte Update-Settings (`update_manager.py`). Der Rest (Theme-Refresh, Icon-Cache, Excel-Zellen u.a.) loggt auf DEBUG. `tools/import_excel.py` und `tools/update_manager.py` haben jetzt einen Logger.

### Verifikation

- 13/13 Kern-Tests grün (inkl. neuem Atomicity-Test), 0 stille except-pass-Blöcke, 0 undefinierte Namen, 0 Import-Probleme, Versionen synchron auf 1.0.31

---

### Nachgereichte Fixes (zweite Tiefenanalyse)

- **Syntaxfehler in `tools/import_excel.py` und `tools/update_manager.py` behoben** (eigener Fehler aus dem except-Logging-Fix): `import logging` war vor `from __future__ import annotations` eingefügt worden — die beiden Werkzeuge kompilierten nicht. Neu in CI: `python -m compileall` prüft jetzt ALLE Dateien (auch tools/, die pytest nicht importiert), damit so etwas nie wieder durchrutscht.
- **Sparziel-Redo korrigiert (fachlich falsch)**: `_post_recalc()` wendete bei Redo dieselben Vorzeichen wie bei Undo an — nach Undo+Redo einer Sparbuchung wich das Sparziel um den doppelten Betrag ab statt zum Ausgangswert zurückzukehren. Jetzt richtungsabhängig (`redo=True` invertiert alle Deltas). Neuer Regressionstest `test_savings_goal_undo_redo_returns_to_start` (500 → Undo 400 → Redo 500, stabil über zwei Zyklen).
- **Reset-Dialog entschärft**: Die Löschung von `users.json` + Einstellungen ist nicht mehr automatischer Bestandteil des Full-Resets, sondern eine eigene Opt-in-Checkbox (Default AUS). Im verschlüsselten Modus zerstörte die automatische Löschung Salt/Schlüssel-Metadaten — die `.enc`-Datei war danach dauerhaft unlesbar. Vor dem Löschen werden `users.json`, Einstellungen und (im verschlüsselten Modus) die `.enc`-Datei ins Backup-Verzeichnis gesichert; die zweite Warnstufe benennt die Konsequenzen jetzt explizit (neue i18n-Keys DE/EN/FR). Dies revidiert die frühere Einstufung von Audit-Punkt P0.4 als „widerlegt": Das Model war unschuldig, der Dialog nicht.
- **Theme-Profile im Build**: `views/profiles/` (25 mitgelieferte Themes) fehlte in `BudgetManager.spec` — im Frozen-Build wären alle Themes verschwunden. Ergänzt.
- **Release-Stand geprüft**: Neuester öffentlicher GitHub-Release ist v1.0.28 (4. März) — v1.0.29–31 wurden noch nicht gepusht/getaggt. Kein Code-Problem; Release-Schritt steht aus.

---

### Update-Adresse final eingetragen

- **GitHub-Repo `sloogy/Budgetmanager`** überall hinterlegt: Installer-URL (Platzhalter `DEIN_GITHUB` ersetzt), Default in `tools/update_manager.py` (war `yourusername`; Modul ist als nicht-eingebundenes Standalone-Werkzeug markiert) und Doku-Beispiele in `updater/`. Der produktive Update-Pfad (`updater/common.py` → `releases/latest/download/latest.json`) zeigte bereits korrekt auf das Repo; der CI-Workflow generiert die Manifest-URLs ohnehin dynamisch aus `github.repository`.

---

## [1.0.30] - 2026-06-11 — Stabilitäts- und Release-Fix

Basierend auf der Tiefenanalyse von v1.0.29. Geprüfte, aber widerlegte Punkte
sind unten dokumentiert.

### Build & Release (P0.1, P1.1, P1.5)

- **`BudgetManager.spec` erstellt**: Der GitHub-Workflow rief `pyinstaller BudgetManager.spec` auf, die Datei existierte aber nicht im Repo — der CI-Build wäre abgebrochen. Die Spec bündelt explizit `locales/` und `data/default_categories.json` (Assets fehlen sonst im Frozen-Build).
- **Versionschaos behoben**: `app_info.py` ist jetzt die einzige Versionsquelle. Neues Skript `tools/sync_version.py` synchronisiert `version.json` (war 1.0.24), `VERSION_INFO.txt` (war 1.0.0) und den Inno-Setup-Installer (war 1.0.0). Der CI-Workflow prüft die Konsistenz vor jedem Build (`--check`).
- **Requirements aufgeteilt**: `requirements.txt` (Laufzeit), `requirements-dev.txt` (pytest/black/mypy), `requirements-build.txt` (PyInstaller). Vorher waren Dev-Tools aktiv in der Laufzeit-Liste. Workflow installiert jetzt aus `requirements-build.txt`. Altlast `requirements_updated.txt` entfernt.

### Datensicherheit (P0.2, P0.3)

- **Pre-Migration-Backup für verschlüsselte DBs**: Vor einer Schema-Migration im verschlüsselten Modus wird die originale `.enc`-Datei jetzt als `pre_migration_<Zeitstempel>.enc` ins Backup-Verzeichnis kopiert. Vorher gab es dort — anders als im unverschlüsselten Pfad — keinerlei Datei-Sicherung.
- **Gefährliche `restore_backup()`-Methode entfernt** (`DatabaseManagementModel`): Sie kopierte Backup-Dateien ohne Format-Prüfung per `shutil.copy2` über die aktive DB — ein `.bmr`-Bundle (ZIP) hätte die Datenbank zerstört. Die Methode wurde nirgends aufgerufen (toter Code), war aber eine Falle für künftige Verdrahtung.

### Default-Kategorien zentralisiert (P1.2)

- **Eine Quelle statt drei**: `data/default_categories.json` ist jetzt die einzige Quelle (neues Modul `model/default_categories.py` mit eingebautem Fallback). Vorher erzeugten Erststart (`ensure_defaults`, hardcodiert inkl. persönlicher Einträge wie „Tirza Jugendlohn." und Tippfehlern „Nebenerweb"/„Rechtschutzz") und Reset (`DEFAULT_CATEGORIES`, andere Liste) **unterschiedliche** Kategorien.
- **Bestands-DBs bleiben unangetastet** (defaults_loaded-Flag); die alten Namen bleiben in `utils/category_i18n.py` gemappt. Für die Namen der zentralen Quelle wurden 34 neue `cat.default.*`-Übersetzungen (DE/EN/FR) ergänzt.
- Reset setzt jetzt das `defaults_loaded`-Flag, damit Erststart-Logik nicht erneut einfügt.

### Tests & CI (P1.4)

- **Neue Testsuite `tests/test_core.py`** (12 Tests, ohne Qt lauffähig): Migration (frisch + idempotent), Reset (erzeugt identische Kategorien wie Erststart; `system_flags` überlebt), Undo/Redo-Roundtrip, Tabellen-Whitelist, Recurring-Datumslogik (Monatsende-Überlauf, Schaltjahr, start_date), `.bmr`-Bundle-Roundtrip, Restore via SQLite-Backup-API.
- Tests laufen im CI-Workflow vor jedem Build.

### Geprüfte, aber widerlegte Analysepunkte

- **P0.4 (Reset zerstört Login)**: Falsch — Reset löscht nur DB-Tabellen; `users.json`/`settings.json` liegen außerhalb der DB. Per Test abgesichert.
- **P0.5 (manuelle Tabellenlisten im Reset)**: Bereits erledigt — Reset liest dynamisch aus `sqlite_master` mit Preserve-Liste; `suggestion_accepted` wird miterfasst.
- **P0.6 (Backup sichert falsche Datei)**: Code-seitig behoben — vor dem Bundle wird `encrypted_session.save()` aufgerufen und die echte `.enc` gebündelt. Der manuelle Restore-Test mit verschlüsselter DB auf Windows bleibt als Release-Auflage offen.

### Bekannte offene Punkte (bewusst nicht in 1.0.30)

- Echte `accounts`-Tabelle / ID-basierte Verknüpfung statt Kategorie-Text (P1.6) — größerer Architektur-Umbau, eigenes Release
- Restliche hardcodierte deutsche UI-Texte (P2.1) — schrittweise, Datei für Datei
- Installer-Finalisierung: GitHub-URL-Platzhalter `DEIN_GITHUB` in `installer/budgetmanager_setup.iss` muss noch durch die echte URL ersetzt werden (P2.2)

---

## [1.0.29] - 2026-06-11

### Stabilitäts-Fixes (Ursachen der gemeldeten Instabilitäten)

- **Fehlender `trf`-Import in `main_window.py`**: An 7 Stellen wurde `trf()` verwendet, obwohl nur `tr` importiert war. Jede dieser Stellen (u. a. Statusmeldung nach Anzeigename-Änderung, Datenordner öffnen, Update-Dialog-Fehler, Setup-Assistent-Fehler) löste einen `NameError` aus, der vom globalen Excepthook als „Unerwarteter Fehler“-Dialog angezeigt wurde — die eigentliche Aktion war dabei meist erfolgreich, was die Fehler scheinbar zufällig und nicht nachvollziehbar machte.
- **Restore bei unverschlüsselter DB komplett überarbeitet**: Bisher wurde die Live-DB-Verbindung der App geschlossen und die Datei per `shutil.copy2` ersetzt. Folgen: (1) Bei „Nein“ auf den Neustart-Dialog lief die gesamte App auf einer toten Verbindung („Cannot operate on a closed database“ bei jedem Klick). (2) Zurückgebliebene `-wal`/`-shm`-Dateien konnten beim nächsten Start alte Daten über die wiederhergestellte DB spielen (Datenkorruption). Jetzt: Restore über die SQLite-Backup-API direkt in die lebende Verbindung — kein Neustart mehr nötig, Tabs werden automatisch aktualisiert, keine WAL-Risiken. Verschlüsselter Modus unverändert (Neustart weiterhin erforderlich).
- **Menüs wurden nach Sprachwechsel nie übersetzt**: `_retranslate_ui()` rief die nicht existierende Methode `_setup_menus()` auf; der Fehler wurde still verschluckt. Jetzt wird die Menüleiste geleert und vollständig neu aufgebaut (inkl. Bearbeiten-Menü-Status und Kategorien-Sichtbarkeit).
- **Setup-Assistent erschien beim unverschlüsselten Erststart nie**: `db_existed` wurde erst nach `open_db()` geprüft (die Datei existiert dann immer). Jetzt wird der vor dem Öffnen ermittelte Zustand (`db_existed_before`) verwendet.

### i18n-Fixes

- **39 `trf()`-Aufrufe ohne Format-Argumente korrigiert** (account_management, category_manager, categories_tab, login, backup_restore, settings, startup_wizard, setup_assistant, recurring_bookings, savings_goals, budget_entry, category_excel_io, category_properties, main_window): Nutzer sahen rohe Platzhalter wie `{e}`, `{mode_label}`, `{count}` statt der Werte.
- **Ungültige Platzhalter in Sprachdateien normalisiert**: `{self._active_user.security_label}` → `{label}`, `{len(selected) - 10}` → `{count}`, `{goal.name}`/`{user.display_name}` → `{name}`, `{len(self.categories)}`/`{len(editable)}` → `{count}` (alle drei Sprachen).
- **`tr("cancel")` → `tr("btn.cancel")`** im Backup-Bereinigungsdialog (Button zeigte wörtlich „cancel“).
- **16 fehlende französische Übersetzungen ergänzt** (`create_user.*` im Startup-Wizard/Login); `dlg.und_lenselected_10_weitere` für EN/FR übersetzt. Alle drei Locales jetzt identisch mit 1 172 Keys, 0 fehlende Keys, 0 ungültige Platzhalter (per AST-Audit verifiziert).
- **Logging-Fix**: `logger.warning(tr(...), e)` ohne `%s` im Format-String erzeugte interne Logging-Fehler; auf `logger.warning("%s: %s", …)` umgestellt. Zwei `print()`-Fehlerausgaben in `budget_entry_dialog.py` auf Logger umgestellt.

### Aufräumarbeiten (Dead Ends)

- **6 nie importierte Module nach `_attic/` verschoben** (per Import-Graph-Analyse verifiziert): `views/recurring_transactions_dialog_extended.py` (meldete „Buchung erfolgreich“, ohne tatsächlich zu buchen — der Insert war nur ein Kommentar!), `views/fixcost_check_dialog.py`, `model/fixcost_check_model.py` (öffnete eigene Datei-Verbindungen, die im verschlüsselten Modus ins Leere greifen), `model/budget_warnings_model.py` (ersetzt durch `_extended`), `views/appearance_profiles_dialog.py`, `views/theme_profiles_dialog.py`. Begründung je Datei in `_attic/README.md`. Die produktiven Pfade (tracking_tab → `RecurringBookingsDialog`/`MissingBookingsDialog`, `theme_editor_dialog`, `budget_warnings_model_extended`) sind nicht betroffen.

### Verifikation

- 0 Syntaxfehler, 0 undefinierte Namen, 0 unauflösbare projektinterne Importe (AST-Analyse über alle 86 aktiven Module)
- Funktionale Smoke-Tests: Undo/Redo-Roundtrip, Recurring-Datumslogik inkl. Monatsende-Überlauf (31. → 28./29. Feb., Schaltjahr), Restore via Backup-API mit weiterhin gültiger Live-Verbindung

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

## Merge-Fix nach 1.0.38
- Versionen verglichen: `category_drag_drop.zip` und `category_drag_drop claude.zip` sind inhaltlich identisch.
- `i18n_dragdrop_fixed` als Basis übernommen, weil dort die Hardcoding-/i18n-Fixes enthalten sind.
- Sinnvolle Drag-&-Drop-Ergänzungen aus der Kategorie-Version zurückgeführt: defensives `CategoryModel.can_reparent()`, Kontextmenü „Verschieben unter…“, Auswahl nach Verschieben.
- Einstellungen → Über: Version wird jetzt automatisch aus `app_info.app_version_label()` gesetzt und zusätzlich beim Öffnen der Einstellungen übergeben.
- Einstellungen → Verhalten: Formularlayout für HiDPI/lange deutsche Labels robuster gemacht und Seite scrollbar gemacht.
