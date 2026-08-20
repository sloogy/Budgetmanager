# 💰 BudgetManager v2.2.62

BudgetManager ist eine lokale Desktop-Anwendung für Jahresbudget, Buchungen, Kategorien, Fixkosten, wiederkehrende Zahlungen, Sparziele und Auswertungen.

![Version](https://img.shields.io/badge/version-2.2.62-blue)
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

## Neu in v2.2.62

- **LifePlanner-/LiveManager-Installation:** Der GitHub-Release enthält bewusst unsigned `.lpmodule`-Pakete für Windows x86_64 und Linux x86_64; lokal ist eine manuelle Vertrauensbestätigung erforderlich.
- **Integritätsnachweis:** Jedes Modulpaket erhält eine eigene SHA-256-Datei und wird vor dem Upload strukturell geprüft.
- **Ein Releaseweg:** Portable Pakete, Windows-Setup, Updater-Dateien, SBOM und LifePlanner-Module entstehen aus demselben Tag-Workflow.

## Neu in v2.2.61

- **QtCharts-Lebensdauer:** Ersetzte Übersichtsdiagramme bleiben bis zum nativen Qt-`destroyed`-Signal referenziert und werden erst im Event-Loop sicher freigegeben.
- **Installer-E2E:** Der Windows-Releasejob prüft Silent-Install, Start der installierten App, Release-Selbsttest und Silent-Uninstall.
- **Reproduzierbare CI:** Build und Tests installieren die gehashten Linux-/Windows-Lockfiles; virtuelle Umgebungen werden von statischen Quellcode-Audits ausgeschlossen.

## Neu in v2.2.60

- **Verbindliche Basis:** v2.2.56 LIFEPLANNER_FIXED bleibt führend; Verbesserungen aus v2.2.58 wurden selektiv übernommen.
- **LifePlanner-Profile:** BudgetManager nutzt die vom Host vorgegebenen, getrennten Daten- und Bridge-Ordner und bleibt gleichzeitig standalone startbar.
- **Review-Inbox:** Neue, geänderte, abgelehnte und verwaiste FPM-/LifePlanner-Vorschläge werden nachvollziehbar verwaltet. Vor der Übernahme können Datum, Typ, Kategorie, Betrag und Beschreibung bearbeitet werden.
- **Kein Auto-Buchen:** Externe Finanzdaten werden niemals ungeprüft als Buchung gespeichert. Fremdwährungen benötigen eine ausdrückliche Bestätigung.
- **Bidirektionale Bridge:** FPM-Ausgaben und Sparziele können weiterhin getrennt in die Outbox geschrieben werden.
- **Monatsstatus nach Lohn:** Der Cockpit-Zeitraum beginnt beim tatsächlichen beziehungsweise hinterlegten Lohneingang und endet am Tag vor dem nächsten Lohntag.
- **Klare Release-Grenze:** Der BudgetManager-Tag veröffentlicht nur BudgetManager-Artefakte. LifePlanner prüft seinen Online-Stand über den eigenen Veröffentlichungsweg; `.lpmodule`-Dateien werden hier nicht hochgeladen.
- **Cockpit und Sparziele:** Freie Kachelspalten, Drop-Platzhalter, QtCharts-Härtung sowie Sparziel-Flussbestand mit Bezug, Korrektur und Teilfreigabe bleiben erhalten.

## Neu in v2.2.55

- Die gesamte Kopfzeile einer Cockpit-Kachel dient im manuellen Modus als Drag-Zone.
- Bereits ab 720 px stehen zwei gleich breite Zielspalten zur Verfügung.
- Reihenfolge und Spaltenzuordnung werden nach jedem Drop gespeichert.
- Tabellen, Buttons und Diagramme innerhalb der Kacheln bleiben normal bedienbar.

## Neu in v2.2.54

- Kritischen nativen QtCharts-Absturz im Cockpit nach dem Hinzufügen von Buchungen behoben.
- Die obere Linie des Flächendiagramms wird dauerhaft gehalten, weil `QAreaSeries` sie nicht besitzt.
- Verlauf, Serien und Achsen werden nicht mehr bei jedem Refresh zerstört, sondern sicher in-place aktualisiert.
- Notstart ohne Cockpit-Diagramme: `BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh`.
- Neue Regressionstests sichern Objektlebensdauer, atomare Punktaktualisierung und den Notstartschalter.

## Neu in v2.2.53

- Kritischen nativen Qt-/PySide6-Segfault nach Abschluss des Setup-Assistenten behoben.
- Das verschobene Auto-Backup läuft erst nach vollständig abgeschlossenem Dialogabbau und in einem separaten Event-Loop-Schritt.
- Parent-gebundene Timer, Referenzschutz und Abschluss-Guard verhindern Callbacks auf zerstörte Qt-Objekte und Doppelabschlüsse.

## Neu in v2.2.52

- Kritischen Cockpit-Startabbruch durch Python-Klassen-Comprehension behoben.
- Dashboard-Spaltenvorgaben werden nun importstabil aus Modulkonstanten aufgebaut.
- Neuer Regressionstest verhindert erneute `NameError`-Abbrüche beim Laden des Cockpits.

## Neu in v2.2.51

- Kritischen Erststart-Abbruch im Sprachwahldialog behoben (`FrozenInstanceError` in `UIColors`).
- Berechnete Hover-Farben werden bei der unveränderlichen Farb-Dataclass jetzt korrekt und typisiert initialisiert.
- Ein neuer Runtime-Regressionstest startet die Farbkonfiguration wirklich und schützt vor derselben Fehlerklasse.

## Neu in v2.2.50

- Neuer **Einfach-/Erweitert-Modus**: Der einfache Modus reduziert die Oberfläche auf Cockpit, Budget, Tracking und Übersicht; alle Funktionen bleiben im erweiterten Modus erreichbar.
- Export erweitert um **XLSX-Arbeitsmappen** mit getrennten Tabellenblättern sowie schwarzweiss-taugliche **A4-PDF-Berichte**.
- Diagnose-ZIPs enthalten jetzt anonymisierte Qt-/Skalierungsdaten und eine technische Datenbank-Gesundheitsprüfung, aber keine Buchungen, Namen oder Beträge.
- Restore-Kopien bleiben auch bei vollem Datenträger, fehlenden Rechten oder Austauschfehlern atomar; der bisherige Datenbestand bleibt bis zum letzten geprüften Dateitausch erhalten.
- CI erzeugt eindeutige Voll-Coverage-Artefakte, prüft kritische Sicherheitsmodule separat und führt einen 50’000-Buchungen-Performance-Benchmark aus.
- Fedora-/Windows-Gates erzeugen visuelle Screenshots und weisen einfarbige, leere oder fehlerhaft skalierte Hauptansichten zurück.
- Strengere Typprüfung für Backup, Diagnose, Update-Signatur, sicheren Excel-Import und Berichtsexport.

## Neu in v2.2.49

- Die Sicherheitsverbesserungen aus KILLCRITIC GREEN und ENTERPRISE RELEASE AUDITED wurden ohne Rückschritte bei lokalen Coverage-, Qt- und Bandit-Prüfungen zusammengeführt.
- Der Erststart-Import prüft `.bmr`-Backups jetzt genauso strikt wie der normale Restore und streamt Datenbanken mit Größenlimit statt sie vollständig in den Arbeitsspeicher zu lesen.
- Vollständige Konto-Wiederherstellungen erhalten andere lokale Konten. Nur ein exakt identisches Konto wird ersetzt; Namens- oder Datenbankkollisionen brechen sicher ab.
- Manifest und Nutzdaten werden aus demselben geöffneten Archiv geprüft, um Austauschrennen zwischen Prüfung und Restore zu verhindern.
- Leere optionale Dateien erhalten gültige Prüfsummen; fehlerhafte SHA-256-Felder und unvollständige Konto-Metadaten werden abgewiesen.
- Backup-Dialoge melden jetzt den tatsächlichen Bundle-Inhalt statt lediglich vorhandene Quelldateien.
- Neue v2.2.49-Regressionen sichern beide Restore-Wege, Mehrbenutzer-Erhalt, atomare Kopien und Kompressions-Grenzfälle ab.

## Neu in v2.2.48

- Backup-Integrität umfasst jetzt Datenbank, Einstellungen und das zugehörige Benutzerkonto; manipulierte oder beschädigte Zusatzdaten werden abgewiesen.
- Konto-Backups enthalten bei mehreren lokalen Benutzern nur noch den zur gesicherten Datenbank passenden Kontoeintrag und bleiben dadurch selbstkonsistent.
- Vollständige Konto-Wiederherstellungen streamen große Datenbanken mit harter Größenbegrenzung statt die gesamte Datei in den Arbeitsspeicher zu laden.
- Legacy-Backups können nach ausdrücklicher Bestätigung in eine vollständig gehashte Kopie migriert werden.
- Manipulierte ZIP-Kompressionsmethoden werden kontrolliert abgewiesen; Update-Archive dürfen keine doppelten oder plattformabhängig kollidierenden Pfade enthalten.
- Aktive lokale Dokumentationslinks werden durch einen Regressionstest abgesichert.

## Neu in v2.2.47

- Die ausführlichere Cockpit-Anleitung aus der Guide-Variante wurde mit der technisch robusteren Enterprise-Version verbunden.
- Ein eigenes In-App-Hilfethema erklärt Kennzahlen und Trendfarben, Ring- und Flächendiagramm, Automatikmodus, fixiertes Drag-and-drop, Spaltenwechsel und Designprofile.
- Layoutmodus, Reihenfolge und Spalten bleiben atomar gespeichert; DesignManager und Theme-Wechsel werden nicht umgangen.
- Das Enterprise-DAU-Audit erkennt jetzt auch dreistellige fest codierte Farben wie `#666`.

## Neu in v2.2.43

- Dashboard-Optik aus v2.2.42 und das automatische/fixierte Kachellayout aus v2.2.41 sind in einer gemeinsamen Implementierung zusammengeführt.
- Leere Bereiche schrumpfen und wandern im Automatikmodus stabil nach unten; im fixierten Modus lassen sich Kacheln über den Griff `≡` zwischen beiden Spalten verschieben.
- Reihenfolge, Spalten, Sichtbarkeit und Auf-/Zuklappzustand werden gespeichert; Einstellungen aus beiden Zwischenversionen werden migriert.
- KPI-Karten, Ringdiagramm und Flächenverlauf bleiben vollständig vom aktiven DesignManager-Profil gesteuert.
- Fehler der Dashboard-Variante behoben: fehlender KPI-Icon-Parameter, herausgefilterte Diagramm-Kachel, instabile Einspalten-Ablage und undefinierte Theme-Randfarbe.
- Theme-Wechsel aktualisieren Cockpit-Diagramme und KPI-Trends sofort.

Vollständige Anleitung: [`docs/USER_GUIDE.de.md`](docs/USER_GUIDE.de.md). In der App: **F1**.

## Wichtige Grundfunktionen

### Fixkosten / Wiederkehrend sauber getrennt

- **Fix + Wiederkehrend** = echte monatliche Fixkosten, Betrag aus Budget, gesperrt.
- **Fix ohne Wiederholung** = geschützte variable Kosten/Rückstellungen, z. B. Franchise oder Selbstbehalt; Betrag ist beim Buchen editierbar.
- **Wiederkehrend ohne Fix** = regelmäßige, variable Buchung; Betrag ist editierbar.
- Fix-only und recurring-only gelten im Monat erst als abgeschlossen, wenn der Budgetbetrag erreicht wurde.

### Tracker-Kategorieauswahl

- Favoriten stehen oben.
- Normale manuelle Kategorien werden nach manueller Buchungshäufigkeit sortiert.
- Parent-Kategorien mit Unterkategorien werden im Tracking nicht als eigene Buchungszeile angezeigt.
- Unterkategorien werden kurz angezeigt: **Miete** statt **Wohnen › Miete** oder **Wohnen - Miete**.
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

Die Wissensdatenbank erklärt alle Kernfunktionen einschließlich **Soft-0-Budget / sanfter Null-Bilanz**: Erststart, Restore-Key, Datenbank, Backup, Kategorien, Drag & Drop, Budget, Buchungen/Tracking, Fixkosten, Wiederkehrend, Übersicht, Sparziele, Favoriten, Tags, Export, Updates und typische Stolperfallen.

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
- Verständlichere Diagramme: bewährter Plan/Ist-Donut, Kategorien-Ranking, Konto-Vergleich als Balken, Monatsverlauf, Monatsbilanz und Top-Buchungen.
- Der gute Plan/Ist-Donut bleibt. Der verwirrende Kreis daneben wird nicht mehr für Einnahmen/Ausgaben/Ersparnisse genutzt, weil diese Werte keine Anteile desselben Topfs sind.
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
APP_VERSION = "2.2.62"
APP_RELEASE_DATE = "20. August 2026"
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
  --version 2.2.62 \
  --release-tag v2.2.62 \
  --channel stable \
  --windows-zip dist/BudgetManager-v2.2.62-portable-windows.zip \
  --linux-zip dist/BudgetManager-v2.2.62-portable-linux.zip \
  --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.2.62 \
  --out latest.json
```

Die Datei `latest.json` wird zusammen mit den Plattform-ZIPs, Installer-Artefakten, unsigned `.lpmodule`-Paketen und Prüfsummen in das GitHub-Release hochgeladen.

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
- [docs/open-tasks.md](docs/open-tasks.md) — verbleibende externe Release-Schritte und Abnahmehinweise.

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

## Lernmodus v2.2.22 – Entscheidungspfad

Der Lernmodus ist für den Einstieg gedacht, wenn noch kein Budget gesetzt wurde und zuerst echte Buchungen gesammelt werden sollen. Im Erststart bedeutet das: Ist der Lernmodus aktiv, darf der Budget-Schritt ohne Budgetwert abgeschlossen werden. Ist der Lernmodus deaktiviert, bleibt die Mindestprüfung hart und es muss mindestens ein Budgetwert vorhanden sein.

1. **Kein Budget im Jahr vorhanden** → die Kategorie darf aus manuellem Tracking ein Startbudget vorschlagen.
2. **Budget im Jahr vorhanden** → Lernmodus ist für diese Kategorie beendet; danach gilt nur noch die normale Budget-Vorschlagslogik.
3. **Vorschlag im Budgetwarner** → Betrag prüfen, Budgetart bestätigen und erst dann übernehmen.
4. **Unsicher** → Rechtsklick auf den Lernvorschlag und „Weiter beobachten“ wählen.
5. **Kategorie passt nicht monatlich** → „Als unregelmäßig / Rückstellung markieren“ wählen.
6. **Nicht verwenden** → „Ignorieren“ blendet die Lernphase dauerhaft aus, bis der Status zurückgesetzt wird.

Budgetarten im Lernmodus:

- **Fix + wiederkehrend**: Miete, Abo, gleichbleibender Lohn.
- **Fix + inkrementell**: Jahres- oder Quartalskosten, die als Monatsreserve geplant werden.
- **Nur wiederkehrend**: regelmäßig, aber nicht exakt gleich.
- **Variabler Topf**: Lebensmittel, Hobby, Haushalt.
- **Ersparnis-Topf**: Sparen als planbarer Topf.
- **Schwankendes Einkommen**: Stundenlohn oder variable Einnahmen; vorsichtig abgerundet.
- **Unregelmäßig / Rückstellung**: Franchise, Selbstbehalt, Reparaturen, seltene Kosten.

Best Practice: Erst tracken, dann Vorschläge prüfen, niemals blind alle Vorschläge übernehmen. Gerade bei Gesundheit, Franchise und Jahresrechnungen ist ein Rückstellungsbudget meist besser als ein starrer Monatsfixbetrag.

Hinweis zur Übersicht: Neue Startbudget-Vorschläge aus dem Lernmodus werden im Banner mit **🆕** angezeigt. **📉** bleibt echten Defizit-/Erhöhungswarnungen vorbehalten, **📈** steht für Überschuss-/Senkungsvorschläge.

### Neu in v2.2.36

- Wiki-Audit und drei grafische Offline-Erklärungen der Prozess- und Datenzusammenhänge.
- Sichtbarer **? Hilfe**-Knopf in der Seitenleiste, Linux-/GNOME-sicher ohne Emoji-Abhängigkeit.
- Direkter Aufruf der Wiki-Grafiken aus Hilfe-Menü und In-App-Handbuch.
