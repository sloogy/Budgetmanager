# Changelog — BudgetManager

### v2.0.12 – Übersicht-Charts: 90-Tage-Budget & Top-Buchungen

**Donut/Ring-Chart bei rollierenden Zeiträumen (7/30/90 Tage) korrigiert**
- Das Budget im Ring-Chart wurde bisher über das **deaktivierte Monats-Combo** berechnet (Default: aktueller Monat) und mit dem Ist des gesamten Zeitraums verglichen. Bei 90 Tagen wurde so ~3 Monate Ist gegen **1 Monat Budget** gestellt → „offen"-Ring fälschlich 0 bzw. ~300 % Auslastung.
- Jetzt nutzt der Donut das **bereichsbezogene Budget** (über die Monate des gewählten Zeitraums summiert) — identisch zur KPI-Leiste darüber. Damit verschwindet der Widerspruch zwischen KPI-Leiste und Ring.
- Im Jahr-/Monats-Modus bleibt das Ergebnis unverändert (das Bereichsbudget entspricht dort Jahr bzw. Einzelmonat).

**Top-Buchungen pro Kategorie aggregiert**
- Bisher wurden **einzelne Buchungszeilen** nach Betrag sortiert; wiederkehrende Posten wie **Lohn** erschienen dadurch mehrfach (z.B. 3× im 90-Tage-Fenster).
- Jetzt werden Buchungen **pro Kategorie summiert** und die größten 5 Kategorien gezeigt (Lohn = eine Summe). Aggregationslogik in `model/overview_aggregation.py` (Qt-frei, testbar).

**Tests**
- `tests/test_overview_charts.py`: bereichsbezogenes Budget (90-Tage-Fenster) und Top-Buchungen-Aggregation.

### v2.0.11 – Aufräumen: Experten-Tab entfernt, Erststart-Name, Version

- **Separater Kategorien-Tab (Experten-Modus) entfernt.** Er war redundant: Kategorienverwaltung läuft weiterhin über den **Kategorie-Manager** (`Strg+K`, Menü Extras → Kategorien verwalten) und direkt im **Budget**-Tab (inkl. Drag & Drop). Der Schnellzugriff `Strg+2` öffnet jetzt den Kategorie-Manager-Dialog.
- Zugehörige **Settings-Option „separaten Kategorien-Tab anzeigen"** und der Menü-Umschalter entfernt.
- **Erststart-Platzhalter** des Anzeigenamens von „Christian Krämer" auf **„Max Mustermann"** geändert (de/en/fr).
- Hilfe/Wissensdatenbank: Verweise auf den entfernten Tab auf Kategorie-Manager/Budget-Tab umgestellt (de/en/fr, HTML + Markdown).
- Doppelten Platzhalter in `data/` aufgeräumt (`.keep` entfernt, `.gitkeep` bleibt).
- Version zentral auf **2.0.11** gezogen (app_info, version.json, Installer-`.iss`, `latest.json`-Templates, README/FEATURES/Updater-Doku).

### v2.0.10 – Fixkosten ohne Wiederholung, Budget-erreicht-Logik & Tracker-Picker

**Fixe Beträge ohne Wiederholung (Franchise, Selbstbehalt etc.)**
- Kategorien mit **fix XOR wiederkehrend** (genau ein Flag) gelten im Monat erst dann als abgeschlossen, wenn der **Budgetbetrag erreicht** ist — nicht mehr schon bei der ersten Buchung.
- Der **buchbare Betrag ist editierbar** und mit dem noch offenen **Restbetrag** vorbelegt. Damit lassen sich z.B. Krankenkassen-Franchise oder Selbstbehalt in mehreren Teilbeträgen über den Monat verbuchen.
- Kategorien mit **beiden** Flags (fix + wiederkehrend) bleiben wie bisher: fixer Monatsbetrag, gesperrt, einmal pro Monat.
- Budget-Voraussage unverändert: fix- oder wiederkehrend-markierte Kategorien sind weiter vor 0-Monats-Senkungen geschützt (≥3 echte Buchungsmonate >0 nötig).

**Cockpit „Offene Monatsbuchungen"**
- Nutzt dieselbe Budget-erreicht-Logik und zeigt eine neue **Restbetrag-Spalte** (was im Monat noch offen ist).

**Übersichtlichere Kategorieauswahl im Tracker**
- Neuer gruppierter Picker in Schnelleingabe und Buchungsdialog.
- Reihenfolge: **Favoriten ★**, dann **häufig manuell gebucht**, dann **normale Buchungen**, danach **Fix / variabel**, **Wiederkehrend / variabel** und **echte Fixkosten**.
- Automatische Fix-/Wiederkehrend-Buchungen zählen nicht fürs Ranking, damit Alltagskategorien nicht verdrängt werden.
- Unterkategorien bleiben durch **Baum-Pfade** sichtbar; das Suchfeld filtert per Texteingabe.
- Der Schnellbutton **Nur echte Fixkosten** bucht nur Kategorien mit beiden Flags. Fix-only Kategorien wie Franchise/Selbstbehalt bleiben im editierbaren Dialog.

**Tests**
- Neue Datenschicht-Tests: gruppierter Picker, Franchise-/Wiederkehrend-/Both-Flags-Abschlusslogik (`tests/test_picker_and_budget_reached.py`).

### v2.0.9 – Release-Konsolidierung

- Versionsnummer auf **2.0.9** angehoben, weil nach dem 2.0.8-Tag mehrere funktionale Fixes hinzugekommen sind (Backup-Import, Kategorie-Dropdown-Ranking, Tracking-Quelle, Theme-Hauptbalken, Cockpit-/Startablauf, Single-Instance, Updater).
- Veröffentlichungsstand ist der frühere „SETUP BACKUP IMPORT FIXED"-Arbeitsstand, **nicht** der ältere 2.0.8-RELEASE-Schnitt (dem das Cockpit und 86 i18n-Keys fehlten).
- Zurückgemergt, da im FIXED-Stand verloren: `.github/workflows/build.yml` (CI-Build), `.gitignore`, `data/.gitkeep`.
- Versionssync zentral auf 2.0.9 gezogen (version.json, Installer-`.iss`, `latest.json.template`, `docs/latest.json.template`, README/FEATURES/Installations- und Updater-Doku).
- Headless-Stabilitätstest der gesamten Datenschicht durchgeführt (siehe `STABILITAETSTEST_v2_0_9.md`).

### Fix: Backup-Import im geführten Starter

- Setup-Assistent: „Backup wiederherstellen“ nutzt jetzt den BackupRestoreDialog mit korrektem DB-/User-/Session-Kontext.
- Direkter Restore eines ausgewählten Backup-Pfads ist über `restore_external_path()` sauber unterstützt.
- Restore-Optionen für Settings und Benutzerdatei werden auch beim direkten Restore abgefragt.
- Erststart-Import von `.bmr`-Quick-Backups kann den im Bundle enthaltenen Quick-DB-Key aus `users.json` nutzen und fragt nicht unnötig nach dem Restore-Key.
- Neue `.bmr`-Manifeste enthalten `source_db_name` zur besseren Zuordnung.


### v2.0.8 – Single-Instance Release-Blocker-Fix

- Mehrfachstart robust und **datenordnerspezifisch** blockiert: mehrere BudgetManager-Instanzen können nicht mehr parallel dieselbe verschlüsselte Datenbank öffnen.
- Wichtig: Der Schutz blockiert nicht global `python main.py`. Andere Programme mit eigenem App-/Datenordner, z. B. ein Füller-Sammelprogramm, dürfen parallel laufen.
- Der alte `QLockFile`-Schutz mit 30-Sekunden-Stale-Timeout wurde ersetzt, weil lange laufende Apps dadurch fälschlich wieder freigegeben werden konnten.
- Neuer atomarer Lock-Ordner `data/budgetmanager.instance.lock` mit gespeicherter PID.
- Bei normalem Beenden wird das Lock entfernt; nach Crash wird ein veraltetes Lock beim nächsten Start automatisch erkannt und bereinigt.
- Regressionstests für aktive und stale Locks ergänzt.


### v2.0.8 – Übersicht Graphen-Erweiterung

- Übersicht erweitert um **Monatsverlauf**: Ausgaben Budget vs. Gebucht pro Monat.
- Übersicht erweitert um **Monatsbilanz**: echte Bilanz vs. geplante Bilanz.
- Übersicht erweitert um **Top-Buchungen**: größte Buchungen im gewählten Zeitraum.
- Chart-Widget bereinigt Achsen beim Wechsel zwischen Pie/Donut/Line/Bar, damit keine alten Achsen hängen bleiben.
- Wissensdatenbank, HTML-Hilfe und Mindmap um die neuen Diagramme ergänzt.


Alle wichtigen Änderungen an diesem Projekt werden in dieser Datei dokumentiert.

---

## [2.0.8] - 2026-06-13 — Merge (release_ready-Basis) + Fixkosten-Vorschlagsregel

Zusammenführung der beiden 2.0.7-Linien zu einem releasefähigen Stand. Basis ist
das `release_ready`-Paket (4 distinkte Zahlenformate swiss/german/french/anglo,
`set_money_locale`/`preferred_number_format_for_currency`, geführter Update-Dialog
mit GUI-Modus, `BUDGETMANAGER_APP_DIR`-Override, Release-Integritätstest). Aus dem
Schwesterpaket übernommen: `docs/DAU_TEST_ERSTSTART.md`. Das dortige
`dau_first_run_check.py` rief die nicht existierende API
`delete_category(strategy=…)` auf und war defekt — die korrekte
`delete_category_safely(...)`-Variante aus `release_ready` bleibt.

### Hilfe & Mindmap-Merge

- Beste Lösung aus `RELEASE 2` und `RELEASE KB COMPLETE` zusammengeführt:
  - durchsuchbares In-App-Handbuch behalten,
  - vollständige lokale HTML-/Markdown-Wissensdatenbank wieder eingebunden,
  - `docs/help` wieder in PyInstaller `datas` aufgenommen,
  - direkt anzeigbare `docs/help/mindmap.html` ergänzt,
  - Help-Menü vereinheitlicht: F1 = Handbuch, Ctrl+F1 = Tastenkürzel, direkter Restore-Key und direkter Mindmap-Aufruf.
- Kategorie-Filterwerte wieder sprachunabhängig gemacht (`all`, `fix`, `recurring`), damit Filter nicht durch Übersetzungen brechen.

### Neu / Korrektheit

- **Fixkosten-Regel in der Budget-Vorschlagslogik** (`budget_suggestion_engine.py`):
  0-Monate dürfen bei Fixkosten/wiederkehrenden Kategorien (`is_fix=1` oder
  `is_recurring=1`) keinen senkenden Budgetvorschlag beweisen. Für diese
  fixed-like Kategorien werden 0-Monate aus der Änderungsanalyse entfernt;
  es braucht mindestens 3 echte Buchungsmonate (> 0), bevor ein Vorschlag
  entsteht. Damit sind inkrementelle/lumpy Fixkosten (quartalsweise, jährlich
  oder in Raten) geschützt, während wiederholte echte Überschreitungen weiterhin
  eine Erhöhung auslösen können. Steuerbar über `respect_fixed_costs`
  (Standard `True`). Nach der Rundung werden Mindeständerungen nochmals geprüft.
- **Erweiterter Regressionstest** `tests/test_fixed_cost_suggestion.py` (8 Fälle):
  Fixkosten+0 → kein Vorschlag; Nicht-Fixkosten+0 → Vorschlag; wiederholte echte
  Fixkostenbuchungen → Erhöhung; Schutz abschaltbar; Versicherung 250/0/0 → kein
  Senken; `is_recurring` geschützt; Hobby 20/30/0 bleibt flexibel;
  Nahrungsmittel 450/350 bleibt stabil.
- **Update-Dialog-Freischaltung repariert** (`updater/check_update.py`):
  Nach erfolgreichem Download/Staging wird wieder ein strukturiertes Ergebnis
  (`available=true`, `staged=true`) geschrieben. Ohne diesen Fix hätte der
  GUI-Dialog den Installationsbutton nach erfolgreichem Check nicht zuverlässig
  freigeschaltet. Ein Release-Integritätstest schützt diese Stelle.
- **Updater wendet die geprüfte Version an** (`updater/apply_update.py`):
  Bisher nahm `apply_update` blind die höchste vorhandene Staging-Version.
  Lag ein alter, höher nummerierter Staging-Ordner herum (z. B. ein Beta-Rest
  `2.1.0`), während Stable gerade `2.0.9` vorbereitet hatte, wurde das falsche,
  ältere Update angewendet (Staging-Ordner werden nie aufgeräumt, der Fall ist
  also erreichbar). `check_update` schreibt nun `staged_version`, und
  `apply_update` bevorzugt genau diese Version (neue Funktion
  `target_staged_version()`), mit sicherem Fallback auf die höchste vorhandene
  Version, falls kein/kein gültiges Prüfergebnis vorliegt. Regressionstest
  `test_apply_uses_checked_version_not_highest_stale_staging`.

### Hilfe & Usability

- **In-App-Wissensdatenbank (Handbuch)** über *Hilfe → Handbuch* (Shift+F1):
  durchsuchbarer Themenbrowser (`views/help_dialog.py`, Inhalte in
  `views/help_content.py`), dreisprachig (de/en/fr), **17 Themen** über den
  gesamten Funktionsumfang: Einstieg, Kategorien, **Drag & Drop** (wo/wie/was),
  Budget & Vorschläge, **Buchungen/Tracking**, **Fixkosten** (ausführlich),
  Wiederkehrende, **Übersicht**, **Sparziele** (wann/wie/wo), **Favoriten**
  (wofür), **Tags**, **Rückgängig/Wiederholen**, Backup, **Datenbank & Schlüssel**,
  **Konten & Sicherheit**, Updates, Währung/Zahlenformat.
- **Datenbank-/Restore-Key zugänglich gemacht:**
  - Der Restore-Key wird jetzt **beim Erststart für ALLE Konten** angezeigt – auch
    für Quick-Konten (ohne Passwort), mit passendem Hinweis, dass er zum
    Wiederherstellen nötig ist (`views/startup_wizard.py`).
  - **Direkter Zugang aus der Hilfe**: Knopf *„DB-Schlüssel / Restore-Key
    anzeigen“* im Handbuch öffnet den Schlüssel der aktuell geöffneten Datenbank
    (neuer, jederzeit aufrufbarer `views/restore_key_dialog.py` mit Kopieren).
    Das schließt auch die Lücke, dass PIN-/Passwort-Konten den Key bisher nach dem
    Erststart nicht erneut einsehen konnten.
  - Das Handbuch-Thema *Datenbank & Schlüssel* erklärt Zweck, Fundorte und
    Sicherheit des Schlüssels.
- **Fixkosten-/Wiederkehrend-Tooltips vereinheitlicht und vervollständigt** (alle
  acht Checkboxen) inkl. Budget-Vorschlags-Wirkung; Verweis aufs Handbuch.
- **Dead-End-Feinschliff**: Tooltip am deaktivierten *Zuweisen*-Feld erklärt, warum
  es ausgegraut ist (keine Zielkategorie vorhanden).

### i18n

- 2 in `release_ready` fehlende Schlüssel ergänzt (`catdel.opt_cascade_all`,
  `dlg.create_account`) in de/en/fr → wieder **1735 identische Schlüssel** je Sprache.

### Verifiziert (Container)

- `compileall`: 0 Syntaxfehler · alle JSON gültig · i18n-Parität 3×1735
- `tools/i18n_audit.py`: keine hardcoded UI-Strings
- `tools/dau_first_run_check.py`: ALLE CHECKS BESTANDEN
- `tools/sync_version.py --check`: alle Versionsdateien synchron auf **2.0.8**
- Tests: **34 passed, 1 skipped**
  (22 core + 4 release-integrity + 8 fixcost; GUI-Tests ohne PySide6 übersprungen)
- Paket-Hygiene: kein `users.json`, keine `*.enc`, kein `__pycache__`/`.pyc`/`.pytest_cache`

> Offen (nur außerhalb des Containers möglich): realer Windows-/Linux-Smoke-Test,
> Qt-Übersetzungskataloge im Build (`verify_qt_translations.py`), Installer-Bau,
> Git-Tag `v2.0.8` + echte SHA256 in `latest.json`.

---

## [2.0.7] - 2026-06-13 — Release-Fixloop nach v2.0.2/v2.0.6 Vergleich

### Fixed
- v2.0.2 als stabile Basis behalten und v2.0.6-Regressionen bei Kategorie-Reassign, Mehrfachlöschung und Undo/Redo nicht übernommen.
- Update-Dialog auf geführten Ablauf umgestellt: automatische Prüfung, strukturiertes `updates/last_check.json`, ein Installationsknopf, sichtbarer Windows-Update-Helfer.
- Erststart verbessert: Zahlenformat bereits bei Sprache/Region wählbar, QLocale an BudgetManager-Zahlenformat gekoppelt.
- Setup-Assistent blockiert Budget-/Tracking-Schritte erst dann frei, wenn wirklich ein Budgetwert > 0 bzw. eine Buchung vorhanden ist.
- Release-Paket bereinigt: keine Testuser, keine `.enc`-Userdaten, keine `.pytest_cache`.

### Tests
- `python -m compileall -q .` erfolgreich.
- `pytest -q`: 26 passed, 1 skipped.
- `tools/dau_first_run_check.py`: alle Headless-Erststartchecks bestanden.

## [2.0.2] - 2026-06-13 — Kategorie-Integrität (Rename/Delete/Parenting)

### Behoben (kritisch)

- **Rename zentralisiert**: `rename_and_cascade` aktualisiert jetzt ALLE
  namensbasierten Tabellen (budget, tracking, budget_warnings, favorites,
  recurring_transactions, savings_goals) atomar. Vorher blieben Warnungen,
  Favoriten, wiederkehrende Buchungen und Sparziele auf dem alten Namen hängen.
- **Löschen integritätssicher** (`delete_category`): keine verwaisten Daten mehr.
  Drei Wege, vom Nutzer wählbar (neuer `CategoryDeleteDialog`):
  1. *Mit allen abhängigen Daten löschen* (Buchungen/Budget/Favoriten/…),
  2. *Daten einer anderen Kategorie zuordnen* (Reassign),
  zusätzlich werden `category_tags` und `funded_by_category_id` sauber behandelt.
- **Parent-Löschung stuft Kinder hoch**: direkte Unterkategorien werden nicht
  mehr verwaist, sondern auf die Ebene der gelöschten Kategorie gezogen
  (Hauptkategorie gelöscht → Kinder werden selbst Hauptkategorien).
- **Zahlenformat-Migration**: alte/abweichende Codes (`ch/eu/us`, `de/fr`, …)
  werden über `normalize_number_format` auf die kanonischen Keys gemappt –
  bestehende Einstellungen fallen nicht mehr still auf `swiss` zurück.

### Hinweise

- Alle bestehenden Löschpfade (`delete`, `delete_by_ids`) laufen jetzt über die
  zentrale, integritätssichere Logik (Default-Strategie `cascade`).
- Reparenting-Validierung (Zyklen/Typ-Mix) war bereits in `update_parent`
  vorhanden und bleibt erhalten.



### Neu

- **Konfigurierbares Zahlenformat** (Dezimal-/Tausendertrennzeichen) unabhängig
  von der Währung: `swiss` (1'234.56), `german` (1.234,56), `french` (1 234,56),
  `anglo` (1,234.56). Umgesetzt in `utils/money.py` (`set_number_format` /
  `get_number_format`), persistiert als Setting `number_format`.
- **Neuer Schritt „Zahlenformat" im Setup-Assistenten** direkt nach der
  DB-Erstellung – mit Live-Vorschau. Auch nachträglich in den Einstellungen
  (Region) änderbar.

### Behoben

- **Native Kontextmenüs konstant englisch** (Rückgängig/Ausschneiden/Kopieren/
  Einfügen/Löschen/Alles auswählen): Es wurde nie ein `QTranslator` installiert.
  Neu: `utils/qt_translator.py` lädt `qtbase_<lang>.qm` beim Start und bei jedem
  Sprachwechsel. `.spec` bündelt die nötigen `.qm`-Dateien für Frozen-Builds.
- **i18n-Inkonsistenz**: 151 in EN bzw. 151 in FR unübersetzte (deutsche) Strings
  übersetzt – inkl. der `auto.*`-Schlüssel. Platzhalter (`{value_0}`, `{e}` …)
  bleiben konsistent; Locale-Parität de/en/fr = 1648 Keys.
- **`parse_money` formatbewusst**: `"1.234"` wird je nach aktivem Format korrekt
  als 1.234 (swiss/anglo) bzw. 1234 (german/french) interpretiert.

### Intern

- Setup-Assistent: fragile, hartcodierte Schritt-Indizes der Branch-Navigation
  durch symbolische Konstanten ersetzt (robust gegen Reihenfolge-Änderungen).



### Zusammengeführt

- Stabile Codebasis aus `1.0.42_clean_merged` beibehalten.
- Versionsziel aus `BudgetManager_Source_2_0_0` übernommen.
- Dokumentation bereinigt und auf `v2.0.2` aktualisiert.

### Behoben / erhalten

- Installer schreibt Erststart-Einstellungen nach `data/budgetmanager_settings.json`.
- Windows-Pfade in Installer-Settings bleiben gültiges JSON.
- `Settings._load()` merged Teil-JSONs über vollständige Defaults.
- Budget-Drag&Drop, Kategorien-Drag&Drop und Dropdown-Settings bleiben enthalten.
- Updater-/Installer-Manifestdateien sind auf `v2.0.2` synchronisiert.

### Bereinigt

- `CLAUDE.md`, `_attic`, lokale Settings, i18n-Audit-Ausgaben und alte Merge-/Analyse-/Bugfix-Berichte nicht übernommen.
- Stale Markdown-Dateien mit 0.x-, 1.0.35- oder internen Analysebezügen nicht übernommen.
- Aktive Markdown-Dokumente neu geschrieben oder auf den aktuellen Release reduziert.

---

## [1.0.42] - 2026-06-13 — Install-Manager, Dropdowns und Budget-Drag&Drop

- Install-/Erststartdialog fragt zusätzlich Währung und bevorzugten Monatstag ab.
- Bei Sprachauswahl werden Währung und bevorzugter Tag sinnvoll vorbefüllt.
- Option „Kein bevorzugter Tag“ ergänzt.
- Einstellungen → Verhalten: Überschuss-/Defizit-Vorschlag als Dropdown.
- Einstellungen → Verhalten: Drag & Drop in der Budgetübersicht ein-/ausschaltbar.
- Kategorien-Manager: Fälligkeitstag als Dropdown.
- Budgetübersicht: Kategorien können per Drag & Drop umgehängt werden.
- Installer-Regression korrigiert: Settings werden in `data/budgetmanager_settings.json` geschrieben.
- Settings-Defaults-Merge korrigiert.

---

## [1.0.41] - 2026-06-13 — Kategorien-Manager: Fenster & Spaltenlayout

- Kategorien-Manager unter Windows mit Minimieren/Maximieren ergänzt.
- Abgeschnittene Kategorie-Spalte behoben.
- Splitter-Verhalten verbessert: Kategorie-Baum bekommt beim Vergrößern den zusätzlichen Platz.

---

## [1.0.38] - 2026-06-13 — i18n Hardcoding Fix + Kategorie Drag & Drop

- i18n-Audit repariert.
- Verdächtige hardcodierte UI-Texte in aktiven Views/Dialogen auf i18n-Keys umgestellt.
- Fehlende i18n-Keys in `de.json`, `en.json` und `fr.json` ergänzt.
- Kategorien-Manager unterstützt Drag & Drop für Ebenenwechsel.
- Kontextmenü-Aktion „Zur Hauptkategorie machen“ ergänzt.
- Kategorien-Filter arbeitet mit internen Werten statt übersetzten Texten.

---

## Ältere Historie

Ältere Zwischenstände wurden aus dem Release-Paket entfernt, weil sie teilweise veraltete Versionsnummern, alte Architekturstände oder Analyseberichte enthielten. Für Git-Historie und alte Release-Artefakte bleibt die vollständige Historie im Repository/Tag erhalten.

## v2.0.8 Workflow-Finalisierung

- Sparziele besser in Budget und Tracking eingebettet.
- Aktive Sparziele werden im Tracking nur bei Bedarf mit Fortschrittsbalken angezeigt.
- Budget-Tab erhält einen kleinen 🎯 Sparziele-Einstieg.
- Sparziel-Dialog erklärt den roten Faden von Plan → Buchung → Fortschritt → Freigabe → Verbrauch.
- Auto-Speichern und Auto-Backup sind beim ersten Start aktiv.
- Wissensdatenbank und Mindmap um den Sparziel-Workflow erweitert.
