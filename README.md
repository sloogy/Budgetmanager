# 💰 BudgetManager v2.1.0

BudgetManager ist eine lokale Desktop-Anwendung für Jahresbudget, Buchungen, Kategorien, Fixkosten, wiederkehrende Zahlungen, Sparziele und Auswertungen.

![Version](https://img.shields.io/badge/version-2.1.0-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![GUI](https://img.shields.io/badge/gui-PySide6%20%2F%20Qt6-purple)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

---

## Schnellstart

### Windows — empfohlen für normale Nutzer

1. Aktuelles Release herunterladen.
2. Portable-ZIP entpacken oder Installer starten.
3. `BudgetManager.exe` starten.

Portable Daten liegen im Ordner `data/` neben dem Programm. Dadurch kann der komplette Ordner auch auf einem USB-Stick genutzt werden.

### Linux / Entwicklung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Alternativ:

```bash
./run.sh
```

---

## Neu in v2.1.0

- Zentrale Datumsbereich-Helfer für Monats-/Jahresabfragen; doppelte `_month_bounds()`-Logik entfernt.
- Tracking, Cockpit, Budgetübersicht, Budgetwarnungen, Vorschlagsengine und KPI-Monatswerte verwenden indexfreundliche halb-offene Datumsbereiche.
- SQLite-Lock-Timeout konsistent auf 10 Sekunden ausgerichtet.
- Release-Nachweise aus Fix- und Performance-Runde in `RELEASE_REPORT_v2_1_0.md` konsolidiert.
- Neue Regressionstests sichern Datumsgrenzen, Timeout-Konfiguration und entfernte Logik-Dubletten ab.

- 13. Monatslohn im Budget-Reiter als eigene Einmaleinkommens-Kategorie erfassbar.
- Jahreskopie zeigt Fixkosten, wiederkehrende, Pot- und inkrementelle Kategorien zur Prüfung und kann nach Vorjahresmuster verteilen.
- Null-Bilanz-Regel verhindert widersprüchliche Ersparnis-Senkungsvorschläge.

- Final-Release-Härtung für den In-App-Updater: Frozen-Builds starten jetzt die echten `--check-update`/`--apply-update`-Pfade.
- Portable-ZIP nutzt stabile Startdateien (`BudgetManager.exe` / `BudgetManager`), während GitHub-Assets weiterhin versioniert bleiben.
- Windows-Update migriert alte versionierte Portable-Binaries auf den stabilen Startpunkt und startet danach die neue App.
- Release-Dokumentation, Help-Dateien, Manifest-Vorlagen und Versionshinweise sind auf v2.1.0 synchronisiert.
- i18n-Härtung für mehrere dynamische Dialogtexte in Budget, Tracking, Backup, Konto, Tags, Themes und Sparzielen.
- Konto & Daten sind in einem eigenen Hub gebündelt: Konto verwalten, Speicherort, Backup/Wiederherstellung und Datenbank-Wartung.
- Der Datenordner ist frei wählbar; beim Wechsel kann die App bestehende Nutzerdaten sicher kopieren, inklusive Sicherheits-ZIP.
- Default-Datenbank und Default-Backups folgen dem aktiven Datenordner; explizite Sonderpfade bleiben möglich.
- PBKDF2-Härtung mit 600 000 Iterationen; ältere Vorab-Konten werden nach erfolgreichem Login automatisch migriert.
- Autobuchungen, Budget-Deckungswarnungen, Schnelleingabe-Suche und Budget-Mehrfachauswahl sind enthalten.


Diese Version ist als Release-Ready-Source-Candidate gedacht. Vor Veröffentlichung sollten zusätzlich der echte Windows-/Linux-Build und `python tools/verify_qt_translations.py <Build-Ordner>` ausgeführt werden, damit die Qt-eigenen Kontextmenüs ebenfalls DE/FR lokalisiert sind.

## Wichtige Grundfunktionen

### Fixkosten / Wiederkehrend sauber getrennt

- **Fix + Wiederkehrend** = echte monatliche Fixkosten, Betrag aus Budget, gesperrt.
- **Fix ohne Wiederholung** = geschützte variable Kosten/Rückstellungen, z. B. Franchise oder Selbstbehalt; Betrag ist beim Buchen editierbar.
- **Wiederkehrend ohne Fix** = regelmäßige, variable Buchung; Betrag ist editierbar.
- Fix-only und recurring-only gelten im Monat erst als abgeschlossen, wenn der Budgetbetrag erreicht wurde.

### Tracker-Kategorieauswahl

- Favoriten stehen oben.
- Normale manuelle Kategorien werden nach manueller Buchungshäufigkeit sortiert.
- Fix-/Wiederkehrend-Kategorien sind eigene Gruppen und werden nicht durch automatische Buchungen hochsortiert.

### Kategorie-Logik finalisiert

- Kategorie-Rename läuft zentral über `CategoryModel.rename_and_cascade()`.
- Rename aktualisiert alle bekannten Text-Referenzen:
  - Budget
  - Tracking/Buchungen
  - Favoriten
  - Budget-Warnungen
  - wiederkehrende Buchungen
  - angenommene Budgetvorschläge
  - Sparziele
- Kategorie-Löschung läuft zentral über `delete_category_safely()` / `delete_categories_safely()`.
- Beim Löschen fragt die App, was mit abhängigen Daten passieren soll:
  - Buchungen/Budget bis zur Kategorie-Löschung entfernen und Sparziele entkoppeln,
  - alle zugehörigen Daten löschen,
  - abhängige Daten einer anderen Kategorie desselben Typs zuordnen.
- Beim Löschen einer Parent-Kategorie werden direkte Children eine Ebene hochgezogen, nicht verwaist und nicht automatisch mitgelöscht.


### Budgetvorschläge / Forecast korrigiert

- Fixkosten und wiederkehrende Kategorien werden vor falschen 0-Monats-Senkungen geschützt.
- 0-Monate werden bei Fixkosten nicht als Beweis für „Budget zu hoch“ gewertet.
- Wiederholte echte Buchungen dürfen trotzdem Budgeterhöhungen oder -senkungen auslösen.
- Flexible Kategorien bleiben flexibel: wiederholte Muster wie `20 / 30 / 0` bei Hobby können weiterhin Vorschläge erzeugen.

### Update-Ablauf verbessert

- Menü `Extras → Updates...` öffnet ein eigenes Update-Fenster.
- Klick auf `Update jetzt ausführen` prüft, lädt und startet die Installation automatisch.
- Das Update-Fenster zeigt die einzelnen Schritte im Log.
- Unter Windows wird ein eigenes Update-Helferfenster geöffnet, weil die laufende EXE nicht selbst überschrieben werden kann.
- Installer-Versionen laden das Setup-Asset und aktualisieren über den Installer, damit Uninstaller, Startmenü und Installationspfad sauber bleiben.
- Datenordner, Backups, Exporte, Einstellungen und Update-Cache bleiben im gewählten Datenordner erhalten.
- Der alte irreführende Text `python -m updater.apply_update` nach der Prüfung wurde ersetzt.
- Bereits vorbereitete, aber veraltete Staging-Updates aktivieren den Installieren-Button nicht mehr.

### Währung, Zahlenformat und i18n

- Zahlenformat ist formatbewusst: Schweiz, Europa und US/UK werden korrekt geparst und formatiert.
- Alte Zahlenformat-Codes werden migriert.
- App-eigene Kontextmenüs sind über i18n-Keys übersetzt.
- Qt-Systemübersetzungen werden beim Start geladen, sofern die `.qm`-Dateien im Build vorhanden sind.

Details stehen im [CHANGELOG.md](CHANGELOG.md).

### Hilfe / Wissensdatenbank / Mindmap

- `F1` öffnet das durchsuchbare In-App-Handbuch.
- `Ctrl+F1` öffnet die Tastenkürzel.
- `Hilfe → HTML-Wissensdatenbank öffnen…` öffnet die vollständige lokale HTML-Hilfe unter `docs/help/index.html`.
- `Hilfe → Informations-Laufplan / Mindmap anzeigen…` öffnet `docs/help/mindmap.html` direkt im Browser. Diese Mindmap ist ohne Mermaid-Plugin sichtbar und kann gedruckt oder als PDF gespeichert werden.
- `Hilfe → Restore-Key anzeigen…` zeigt den Datenbank-/Restore-Key der aktuell geöffneten Datenbank.

Die Wissensdatenbank erklärt alle Kernfunktionen: Erststart, Restore-Key, Datenbank, Backup, Kategorien, Drag & Drop, Budget, Buchungen/Tracking, Fixkosten, Wiederkehrend, Übersicht, Sparziele, Favoriten, Tags, Export, Updates und typische Stolperfallen.

Wichtig bei Fixkosten: Das Häkchen bucht nichts automatisch im Hintergrund. Es nimmt die Kategorie in **Tracking → Fix/Wiederkehrend buchen…** auf, nutzt den Budgetbetrag des Monats, überspringt vorhandene Buchungen und schützt Fixkosten vor falschen 0-Monats-Budgetvorschlägen.

---

## Funktionsumfang

### Budget

- Jahresbudget mit Monatswerten und Totalen.
- Kategorien mit Haupt-/Unterkategorien.
- Typen: Einkommen, Ausgaben, Ersparnisse.
- Fixkosten- und Wiederkehrend-Markierung.
- Fälligkeitstag pro Kategorie.
- Budgetwerte direkt in der Tabelle bearbeiten.
- Budgetvorschläge basierend auf historischen Buchungen.

### Buchungen / Tracking

- Einnahmen, Ausgaben und Ersparnisse erfassen.
- Filter nach Zeitraum, Kategorie und Typ.
- Schnellfilter für die letzten 14 oder 30 Tage.
- Wiederkehrende Buchungen und Fixkostenprüfung.
- Import-/Export-Funktionen für Excel/CSV.

### Kategorien

- Kategorien-Manager mit Baumansicht.
- Drag & Drop für Parent/Child-Ebenen.
- Kontextmenü: verschieben, zur Hauptkategorie machen, umbenennen, sicher löschen.
- Schutz gegen Self-Parenting, Typ-Mischung und Zyklen.
- Sicherer Löschdialog mit Daten löschen / komplett löschen / anderer Kategorie zuordnen.

### Übersicht

- Budget-Ist-Vergleich.
- KPIs für Einnahmen, Ausgaben, Sparen und Saldo.
- Diagramme und Auswertungen.
- Filter nach Jahr, Monat und Zeitraum.

### App & Komfort

- Mehrsprachig: Deutsch, Englisch, Französisch.
- Währungssymbol und Zahlenformat konfigurierbar.
- Themes und Designprofile.
- Lokale SQLite-Datenbank.
- Backup/Restore.
- Persistentes Undo/Redo.
- Multi-Account-System mit Quick/PIN/Passwort-Modus.
- Portable Update-Mechanik für Windows und Linux.

---

## Projektstruktur

```text
BudgetManager/
├── main.py                         # App-Start
├── app_info.py                     # zentrale Versionsquelle
├── settings.py                     # robuste App-Einstellungen
├── model/                          # Datenbank, Migrationen, Geschäftslogik
├── views/                          # PySide6-Dialoge und Tabs
├── utils/                          # i18n, Geldformatierung, Hilfsfunktionen
├── locales/                        # de/en/fr JSON-Übersetzungen
├── data/default_categories.json    # Standard-Kategorien
├── installer/                      # Inno-Setup-Skript
├── updater/                        # Update-Manifest/Updater
├── tools/                          # Audit-/Release-Hilfen
└── tests/                          # Core- und GUI-Smoke-Tests
```

---

## Versionierung

`app_info.py` ist die einzige manuelle Versionsquelle:

```python
APP_VERSION = "2.1.0"
APP_RELEASE_DATE = "19. Juni 2026"
```

Vor einem Release prüfen:

```bash
python tools/sync_version.py --check
```

Synchronisieren:

```bash
python tools/sync_version.py
```

---

## Tests und Checks

```bash
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/sync_version.py --check
python tools/i18n_audit.py
black --check model/
mypy model/
pytest tests/ -v
```

GUI-Tests werden ohne PySide6 automatisch übersprungen.

---

## Release-Update-Manifest

Für GitHub-Releases wird `latest.json` aus dem Template generiert:

```bash
python -m updater.generate_manifest \
  --version 2.1.0 \
  --release-tag v2.1.0 \
  --channel stable \
  --windows-zip dist/BudgetManager-v2.1.0-portable.zip \
  --linux-zip dist/BudgetManager-v2.1.0-portable.zip \
  --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.1.0 \
  --out latest.json
```

Die Datei `latest.json` muss zusammen mit dem Portable-ZIP / der Windows-EXE in das GitHub-Release hochgeladen werden.

---

## Datenschutz

Alle Daten bleiben lokal. Standardmäßig nutzt BudgetManager den portablen Datenordner `data/` neben der Anwendung. Über den Konto-Hub kann ein anderer Datenordner gewählt werden; DB, verschlüsselte Konto-Dateien und Standard-Backups folgen dann diesem Ordner.

---

## Weitere Dokumentation

- [README_INSTALLATION.md](README_INSTALLATION.md) — Installation, Start und Update.
- [docs/help/index.html](docs/help/index.html) — vollständige lokale HTML-Wissensdatenbank.
- [docs/help/README.md](docs/help/README.md) — Markdown-Version der Wissensdatenbank.
- [docs/help/mindmap.html](docs/help/mindmap.html) — direkt anzeigbare Mindmap / Informations-Laufplan.
- [FEATURES.md](FEATURES.md) — Funktionsübersicht.
- [CHANGELOG.md](CHANGELOG.md) — Änderungen nach Version.
- [docs/OFFENE_PUNKTE_FINAL_RELEASE.md](docs/OFFENE_PUNKTE_FINAL_RELEASE.md) — Release-Befund und Abnahmehinweise.

### Sparziele im Workflow

Sparziele sind jetzt klarer eingebettet: im Budget gibt es einen kleinen 🎯-Einstieg, im Tracking erscheint bei aktiven Zielen ein ausblendbares Panel mit Fortschrittsbalken und Doppelklick zum Ziel, und die Übersicht bleibt die Kontrollstelle.

### Sparziel-Entnahme / Geld herausbuchen

Geld aus einem Sparziel wird als **negative Ersparnisse-Buchung** auf die mit dem Sparziel verknüpfte Kategorie gebucht, z. B. `-500 CHF` auf `Ersparnisse → Hochzeit`. Negative Beträge sind dafür bei `Ersparnisse` erlaubt; bei `Ausgaben` bleiben negative Beträge bewusst gesperrt.

Sparziele haben jetzt echte Grenzen: Eine Entnahme darf den Stand nicht unter `0 CHF` ziehen, und eine Einzahlung darf das Ziel nicht über `100 %` füllen. Bei beiden Fällen wird die Buchung blockiert und eine Meldung angezeigt.

Best Practice: Sparziel zuerst **freigeben**, dann die Entnahme buchen und das Ziel abschließen, wenn es erledigt ist.

### Sicherer Start

Auto-Speichern und Auto-Backup sind beim ersten Start aktiv.

## Mehrfachstart-Schutz

BudgetManager verhindert parallele Programmstarts, damit Datenbank, Auto-Save und Auto-Backups nicht gleichzeitig von mehreren Instanzen beschrieben werden.

## Erststart-Import

Beim Import einer `.bmr`/`.enc`-Datei im Erststart zuerst Backup wählen, danach Sicherheitsstufe wählen. `.bmr`-Backups von Quick-Benutzern können über die enthaltene `users.json` automatisch übernommen und in den neuen Benutzer re-verschlüsselt werden. Falls das Backup von einem PIN-/Passwort-Benutzer oder einer anderen Installation stammt, wird der Restore-Key des alten Backups abgefragt. Bei falschem Key wird kein leerer Benutzer zurückgelassen.

## Parallelbetrieb mit anderen Programmen

BudgetManager schützt nur seinen eigenen Datenordner vor Mehrfachzugriff. Das verhindert, dass zwei BudgetManager-Fenster gleichzeitig dieselbe verschlüsselte Datenbank speichern. Der Schutz ist **nicht** global auf `python main.py` gelegt. Andere Programme mit eigenem Ordner, z. B. ein Füller-Sammelprogramm, können parallel laufen.

Zum Beenden alter BudgetManager-Testinstanzen bitte nicht pauschal `pkill -f "python main.py"` verwenden, wenn andere Python-Apps offen sind. Besser: BudgetManager-Fenster schließen oder gezielt die PID aus `data/budgetmanager.instance.lock/pid` prüfen.

### Cockpit und Instanzen

Das Cockpit startet keine eigene BudgetManager-Instanz. Es ist ein normaler Reiter innerhalb des Hauptfensters. Der Startablauf wurde so angepasst, dass das Hauptfenster genau einmal sichtbar gemacht wird. Update-Prüfungen im Source-Modus laufen über `python -m updater.check_update` statt über ein zweites `python main.py`.
