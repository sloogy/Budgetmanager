# 💰 BudgetManager v2.2.70

BudgetManager ist eine lokale Desktop-Anwendung für Jahresbudget, Buchungen, Kategorien, Fixkosten, wiederkehrende Zahlungen, Sparziele und Auswertungen.

![Version](https://img.shields.io/badge/version-2.2.70-blue)
![Python](https://img.shields.io/badge/python-3.11+-green)
![GUI](https://img.shields.io/badge/gui-PySide6%20%2F%20Qt6-purple)
![Platform](https://img.shields.io/badge/platform-Windows%20%7C%20Linux-lightgrey)

Alle Daten bleiben auf dem eigenen Rechner. Es gibt kein Konto in der Cloud, keine Telemetrie und keinen Serverzwang; die einzige optionale Netzwerkverbindung ist die Update-Prüfung gegen GitHub.

---

## Inhalt

- [Schnellstart](#schnellstart)
- [Erste Schritte in der App](#erste-schritte-in-der-app)
- [Anleitung: die wichtigsten Abläufe](#anleitung-die-wichtigsten-abläufe)
- [Hilfe in der App](#hilfe-in-der-app)
- [Notstart- und Diagnoseschalter](#notstart--und-diagnoseschalter)
- [Funktionsumfang](#funktionsumfang)
- [Neu in v2.2.70](#neu-in-v2270)
- [Für Entwickler](#für-entwickler)
- [Weitere Dokumentation](#weitere-dokumentation)

---

## Schnellstart

### Windows — empfohlen für normale Nutzer

1. Aktuelles [Release](https://github.com/sloogy/Budgetmanager/releases) herunterladen.
2. Entweder `BudgetManager_Setup_2.2.70.exe` (Installer) starten **oder** `BudgetManager-v2.2.70-portable-windows.zip` entpacken.
3. Portable Version: `start-windows.cmd` beziehungsweise `BudgetManager.exe` starten.

Portable Daten liegen im Ordner `data/` neben dem Programm. Dadurch kann der komplette Ordner auch auf einem USB-Stick genutzt werden. Der Installer fragt beim ersten Start nach einem Datenordner.

Die Pakete sind bewusst nicht Authenticode-signiert. Windows SmartScreen warnt deshalb; die Prüfsummen aus `SHA256SUMS.txt` sollten vor dem Start kontrolliert werden. Details dazu in [README_INSTALLATION.md](README_INSTALLATION.md).

### Linux

Fertiges Paket `BudgetManager-v2.2.70-portable-linux.zip` entpacken und starten:

```bash
./start-linux.sh
```

Aus dem Quellcode:

```bash
git clone https://github.com/sloogy/Budgetmanager.git
cd Budgetmanager
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 main.py
```

Alternativ erledigt `./run.sh` beides: Es startet eine vorhandene Binary, sonst legt es `.venv` an, installiert die Abhängigkeiten und startet den Quellcode.

Unter Wayland schaltet BudgetManager automatisch auf das XCB-/XWayland-Backend, weil Qt beim Schliessen kleiner Dialoge sonst nativ abstürzen kann. Wer natives Wayland will, setzt `BM_ALLOW_WAYLAND=1`.

### macOS

Für macOS gibt es kein fertiges Release-Paket. Der Start aus dem Quellcode funktioniert:

```bash
./start-macos.sh
```

Voraussetzung ist Python 3.12 oder neuer; das Skript legt `.venv` an und installiert die Abhängigkeiten selbst.

### Voraussetzungen

- Python 3.11 oder neuer (CI und Releases bauen mit 3.12) — nur für den Start aus dem Quellcode.
- PySide6/Qt 6 (kommt über `requirements.txt`).
- Unter Linux die Qt-Systembibliotheken: `libegl1`, `libgl1`, `libxkbcommon-x11-0`, `libxcb-cursor0`, `libdbus-1-3`, `libfontconfig1`.

---

## Erste Schritte in der App

1. **Sprache und Region wählen.** Der Erststart-Assistent fragt Sprache, Währung, Zahlenformat und den bevorzugten Buchungstag ab.
2. **Restore-Key sichern.** Er wird einmalig angezeigt und gehört an einen Ort ausserhalb des Programmordners. Ohne ihn lässt sich ein verschlüsseltes Backup auf einer anderen Installation nicht öffnen. Später erneut abrufbar über `Hilfe → Restore-Key anzeigen…`.
3. **Kategorien anlegen** oder die mitgelieferten Standardkategorien übernehmen.
4. **Budget setzen** — oder den **Lernmodus** aktiv lassen und zuerst nur buchen. Im Lernmodus darf der Budget-Schritt ohne Betrag abgeschlossen werden.
5. **Buchen** unter *Tracking*. Fixkosten und wiederkehrende Zahlungen laufen über `Tracking → Fix/Wiederkehrend buchen…`.
6. **Auswerten** im Cockpit und in der Übersicht.

Auto-Speichern und Auto-Backup sind ab dem ersten Start aktiv.

### Einfach- oder Erweitert-Modus

Der einfache Modus reduziert die Oberfläche auf Cockpit, Budget, Tracking und Übersicht. Es geht dabei nichts verloren: Alle übrigen Funktionen sind im erweiterten Modus erreichbar, umschaltbar in den Einstellungen.

---

## Anleitung: die wichtigsten Abläufe

### Fixkosten und Wiederkehrend sauber getrennt

- **Fix + Wiederkehrend** = echte monatliche Fixkosten, Betrag aus dem Budget, gesperrt.
- **Fix ohne Wiederholung** = geschützte variable Kosten oder Rückstellungen, zum Beispiel Franchise oder Selbstbehalt; der Betrag ist beim Buchen editierbar.
- **Wiederkehrend ohne Fix** = regelmässige, aber variable Buchung; der Betrag ist editierbar.
- Fix-only und Recurring-only gelten im Monat erst als abgeschlossen, wenn der Budgetbetrag erreicht ist.

Wichtig: Das Häkchen bucht nichts automatisch im Hintergrund. Es nimmt die Kategorie in `Tracking → Fix/Wiederkehrend buchen…` auf, nutzt den Budgetbetrag des Monats, überspringt bereits vorhandene Buchungen und schützt die Kategorie vor falschen 0-Monats-Budgetvorschlägen.

### Kategorien umbenennen und löschen

- Umbenennen läuft zentral über `CategoryModel.rename_and_cascade()` und zieht alle Textreferenzen nach: Budget, Tracking/Buchungen, Favoriten, Budget-Warnungen, wiederkehrende Buchungen, angenommene Budgetvorschläge und Sparziele.
- Löschen läuft über `delete_category_safely()` / `delete_categories_safely()`. Die App fragt vorher, was mit abhängigen Daten passieren soll:
  - Buchungen und Budget bis zur Löschung entfernen und Sparziele entkoppeln,
  - alle zugehörigen Daten löschen,
  - abhängige Daten einer anderen Kategorie desselben Typs zuordnen.
- Beim Löschen einer Parent-Kategorie werden direkte Children eine Ebene hochgezogen — sie werden nicht verwaist und nicht stillschweigend mitgelöscht.
- Der Kategorienbaum schützt gegen Self-Parenting, Typ-Mischung und Zyklen.

### Kategorieauswahl im Tracking

- Favoriten stehen oben.
- Normale manuelle Kategorien werden nach manueller Buchungshäufigkeit sortiert.
- Parent-Kategorien mit Unterkategorien erscheinen nicht als eigene Buchungszeile.
- Unterkategorien werden kurz angezeigt: **Miete** statt **Wohnen › Miete**.
- Fix- und Wiederkehrend-Kategorien bilden eigene Gruppen und werden nicht durch automatische Buchungen hochsortiert.

### Sparziele

Sparziele sind an mehreren Stellen eingebettet: im Budget über den 🎯-Einstieg, im Tracking über ein ausblendbares Panel mit Fortschrittsbalken und Doppelklick zum Ziel, in der Übersicht als Kontrollstelle.

Geld aus einem Sparziel wird als **negative Ersparnisse-Buchung** auf die verknüpfte Kategorie gebucht, zum Beispiel `-500 CHF` auf `Ersparnisse → Hochzeit`. Negative Beträge sind deshalb bei `Ersparnisse` erlaubt; bei `Ausgaben` bleiben sie bewusst gesperrt.

Die Grenzen sind hart: Eine Entnahme darf den Stand nicht unter `0` ziehen, eine Einzahlung das Ziel nicht über `100 %` füllen. Beides wird blockiert und gemeldet.

Best Practice: Sparziel zuerst **freigeben**, dann die Entnahme buchen und das Ziel abschliessen, wenn es erledigt ist.

### Lernmodus — Entscheidungspfad

Der Lernmodus ist für den Einstieg gedacht, wenn noch kein Budget steht und zuerst echte Buchungen gesammelt werden sollen. Ist er deaktiviert, bleibt die Mindestprüfung im Erststart hart: mindestens ein Budgetwert muss vorhanden sein.

1. **Kein Budget im Jahr vorhanden** → die Kategorie darf aus manuellem Tracking ein Startbudget vorschlagen.
2. **Budget im Jahr vorhanden** → der Lernmodus ist für diese Kategorie beendet; danach gilt nur noch die normale Vorschlagslogik.
3. **Vorschlag im Budgetwarner** → Betrag prüfen, Budgetart bestätigen und erst dann übernehmen.
4. **Unsicher** → Rechtsklick auf den Lernvorschlag und „Weiter beobachten“ wählen.
5. **Kategorie passt nicht monatlich** → „Als unregelmäßig / Rückstellung markieren“ wählen.
6. **Nicht verwenden** → „Ignorieren“ blendet die Lernphase dauerhaft aus, bis der Status zurückgesetzt wird.

Budgetarten im Lernmodus:

| Budgetart | Typische Beispiele |
| --- | --- |
| Fix + wiederkehrend | Miete, Abo, gleichbleibender Lohn |
| Fix + inkrementell | Jahres- oder Quartalskosten als Monatsreserve |
| Nur wiederkehrend | regelmässig, aber nicht exakt gleich |
| Variabler Topf | Lebensmittel, Hobby, Haushalt |
| Ersparnis-Topf | Sparen als planbarer Topf |
| Schwankendes Einkommen | Stundenlohn, variable Einnahmen; vorsichtig abgerundet |
| Unregelmässig / Rückstellung | Franchise, Selbstbehalt, Reparaturen, seltene Kosten |

Best Practice: erst tracken, dann Vorschläge prüfen, niemals blind alles übernehmen. Gerade bei Gesundheit, Franchise und Jahresrechnungen ist ein Rückstellungsbudget meist besser als ein starrer Monatsfixbetrag.

In der Übersicht sind die Banner-Symbole eindeutig: **🆕** neuer Startbudget-Vorschlag aus dem Lernmodus, **📉** echte Defizit-/Erhöhungswarnung, **📈** Überschuss-/Senkungsvorschlag.

### Budgetvorschläge und Forecast

- Fixkosten und wiederkehrende Kategorien sind vor falschen 0-Monats-Senkungen geschützt; ein 0-Monat gilt dort nicht als Beweis für „Budget zu hoch“.
- Wiederholte echte Buchungen dürfen trotzdem Erhöhungen oder Senkungen auslösen.
- Flexible Kategorien bleiben flexibel: Muster wie `20 / 30 / 0` bei Hobby erzeugen weiterhin Vorschläge.

### Backup, Restore und Erststart-Import

- Auto-Backup läuft beim Start; manuelle Backups jederzeit über den Konto-Hub.
- Ein Backup (`.bmr`) enthält Datenbank, Einstellungen und den passenden Kontoeintrag; Integrität und Prüfsummen werden vor jedem Restore geprüft.
- Beim Erststart-Import zuerst das Backup wählen, danach die Sicherheitsstufe. `.bmr`-Backups von Quick-Benutzern werden über die enthaltene `users.json` übernommen und in den neuen Benutzer re-verschlüsselt.
- Stammt das Backup von einem PIN-/Passwort-Benutzer oder einer anderen Installation, wird der Restore-Key abgefragt. Bei falschem Key bleibt kein leerer Benutzer zurück.
- Eine vollständige Konto-Wiederherstellung erhält andere lokale Konten; ersetzt wird nur ein exakt identisches Konto.

### Update aus der App

1. Menü `Extras → Updates…` öffnen (oder im Über-Dialog auf `Updates…` klicken).
2. `Update jetzt ausführen` klicken. Die App prüft, lädt, verifiziert Signatur und Prüfsumme und startet die Installation.
3. Unter Windows schliesst sich BudgetManager und ein Update-Helferfenster übernimmt, weil die laufende EXE sich nicht selbst überschreiben kann.
4. Installer-Versionen laden das Setup-Asset und aktualisieren über den Installer, damit Uninstaller, Startmenü und Installationspfad sauber bleiben.

Datenordner, Backups, Exporte, Einstellungen und Update-Cache bleiben dabei erhalten. Das Update-Fenster protokolliert jeden Schritt.

> **Einmalig nötig für alte Installationen:** Den eingebauten Vertrauensanker für Update-Signaturen gibt es erst ab v2.2.65. Eine ältere Installation muss einmal von Hand aktualisiert werden; danach funktioniert das In-App-Update wieder von selbst. Für v2.2.61 liegt dem Release zusätzlich `BudgetManager-v2.2.61-Trust-Bridge.ps1` bei, das nur den öffentlichen Schlüssel nachträgt.

### Währung, Zahlenformat und Sprachen

- Deutsch, Englisch und Französisch; Qt-Systemübersetzungen werden beim Start geladen, sofern die `.qm`-Dateien im Build vorhanden sind.
- Das Zahlenformat ist formatbewusst: Schweiz, Europa und US/UK werden korrekt geparst und formatiert; alte Formatcodes werden migriert.
- App-eigene Kontextmenüs sind über i18n-Keys übersetzt.

### Mehrfachstart und Parallelbetrieb

BudgetManager verhindert, dass zwei Instanzen denselben Datenordner beschreiben — sonst kämen sich Datenbank, Auto-Save und Auto-Backup in die Quere. Der Schutz gilt **pro Datenordner**, nicht global für `python main.py`: Andere Python-Programme mit eigenem Ordner laufen ungestört parallel.

Zum Beenden alter Testinstanzen deshalb bitte kein pauschales `pkill -f "python main.py"`, sondern das Fenster schliessen oder gezielt die PID aus `data/budgetmanager.instance.lock/pid` prüfen.

Das Cockpit startet keine eigene Instanz — es ist ein normaler Reiter im Hauptfenster. Update-Prüfungen im Source-Modus laufen über `python -m updater.check_update` statt über ein zweites `python main.py`.

---

## Hilfe in der App

- `F1` öffnet das durchsuchbare In-App-Handbuch.
- `Ctrl+F1` öffnet die Tastenkürzel.
- `Hilfe → HTML-Wissensdatenbank öffnen…` öffnet die vollständige lokale Hilfe unter [`docs/help/index.html`](docs/help/index.html).
- `Hilfe → Informations-Laufplan / Mindmap anzeigen…` öffnet [`docs/help/mindmap.html`](docs/help/mindmap.html) im Browser. Die Mindmap ist ohne Mermaid-Plugin sichtbar und lässt sich drucken oder als PDF speichern.
- `Hilfe → Restore-Key anzeigen…` zeigt den Datenbank-/Restore-Key der aktuell geöffneten Datenbank.
- `? Hilfe` in der Seitenleiste führt zum selben Angebot, ohne Emoji-Abhängigkeit unter Linux/GNOME.

Die Wissensdatenbank erklärt alle Kernfunktionen einschliesslich **Soft-0-Budget / sanfter Null-Bilanz**: Erststart, Restore-Key, Datenbank, Backup, Kategorien, Drag & Drop, Budget, Buchungen, Fixkosten, Wiederkehrend, Übersicht, Sparziele, Favoriten, Tags, Export, Updates und typische Stolperfallen.

Ausführliche Anleitung: [`docs/USER_GUIDE.de.md`](docs/USER_GUIDE.de.md) ([EN](docs/USER_GUIDE.en.md), [FR](docs/USER_GUIDE.fr.md)).

---

## Notstart- und Diagnoseschalter

Alle Schalter sind Umgebungsvariablen, verändern keine Daten und gelten nur für den jeweiligen Start.

| Variable | Wirkung |
| --- | --- |
| `BM_DISABLE_COCKPIT_CHARTS=1` | Startet ohne die beiden Cockpit-Diagramme; hilft bei Grafiktreiberproblemen mit QtCharts. |
| `BM_SKIP_STARTUP_AUTO_BACKUP=1` | Überspringt nur die automatische Backup-Prüfung beim Start. Manuelle Backups bleiben aktiv. |
| `BM_ALLOW_WAYLAND=1` | Erzwingt natives Wayland statt des stabileren XCB-/XWayland-Fallbacks. |
| `BM_FORCE_XCB=1` | Erzwingt das XCB-Backend, auch ausserhalb einer Wayland-Sitzung. |
| `BUDGETMANAGER_DATA_DIR=…` | Setzt den Datenordner explizit, zum Beispiel für Launcher oder Tests. |

Beispiel:

```bash
BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh
```

---

## Funktionsumfang

### Budget

- Jahresbudget mit Monatswerten und Totalen.
- Kategorien mit Haupt- und Unterkategorien.
- Typen: Einkommen, Ausgaben, Ersparnisse.
- Fixkosten- und Wiederkehrend-Markierung, Fälligkeitstag pro Kategorie.
- Budgetwerte direkt in der Tabelle bearbeiten.
- Budgetvorschläge auf Basis historischer Buchungen.

### Buchungen / Tracking

- Einnahmen, Ausgaben und Ersparnisse erfassen.
- Filter nach Zeitraum, Kategorie und Typ, Schnellfilter für 14 oder 30 Tage.
- Wiederkehrende Buchungen und Fixkostenprüfung.
- Import und Export für Excel/CSV.

### Kategorien

- Kategorien-Manager mit Baumansicht.
- Drag & Drop für Parent-/Child-Ebenen.
- Kontextmenü: verschieben, zur Hauptkategorie machen, umbenennen, sicher löschen.
- Schutz gegen Self-Parenting, Typ-Mischung und Zyklen.

### Cockpit und Übersicht

- Cockpit mit KPI-Kacheln, Ringdiagramm und Flächenverlauf; Kacheln automatisch oder frei anordenbar.
- Monatsstatus nach Lohn: Der Cockpit-Zeitraum beginnt beim tatsächlichen beziehungsweise hinterlegten Lohneingang und endet am Tag vor dem nächsten Lohntag.
- Übersicht mit Budget-Ist-Vergleich, KPIs für Einnahmen, Ausgaben, Sparen und Saldo.
- Plan/Ist-Donut, Kategorien-Ranking, Konto-Vergleich als Balken, Monatsverlauf, Monatsbilanz und Top-Buchungen.
- Filter nach Jahr, Monat und Zeitraum.

### Export und Berichte

- XLSX-Arbeitsmappen mit getrennten Tabellenblättern.
- Schwarzweiss-taugliche A4-PDF-Berichte.
- CSV-/Excel-Export der Buchungen.
- Diagnose-ZIP mit anonymisierten Qt-/Skalierungsdaten und Datenbank-Gesundheitsprüfung — ohne Buchungen, Namen oder Beträge.

### App und Komfort

- Mehrsprachig: Deutsch, Englisch, Französisch.
- Währungssymbol und Zahlenformat konfigurierbar.
- 26 gemeinsame Designprofile, Kontrast- und Farbfehlsichtigkeitsprüfung, optional „Wie das System“.
- Lokale SQLite-Datenbank, Backup/Restore, persistentes Undo/Redo.
- Multi-Account-System mit Quick-, PIN- und Passwort-Modus.
- Portable Update-Mechanik für Windows und Linux.
- Betrieb als LifePlanner-/LiveManager-Modul oder vollständig standalone.

---

## Neu in v2.2.70

- **Brücke zu FPM abgesichert:** Ordner und Dateien der Austauschbrücke bekommen `0700` beziehungsweise `0600` — es sind dieselben Buchungen und Sparziele wie in der Datenbank.
- **Update-Archive** werden beim Entpacken zusätzlich auf die Zahl der Einträge geprüft.
- **Unlesbare Einstellungsdateien** werden als `.kaputt-<zeitstempel>` beiseitegelegt statt überschrieben; oft ist nur ein Zeichen falsch und die Datei liesse sich von Hand retten.
- **Radien und Innenabstände** wachsen mit der eingestellten Schriftgrösse, wie Schriftgrössen und Mindesthöhen seit v2.2.68.

### Kürzlich davor

- **v2.2.69:** Radien und Abstände folgen der Schrifteinstellung; bei 10 pt bleibt das Aussehen unverändert.
- **v2.2.68:** Die Brücke zu FPM wird nach jeder Datenänderung, beim Schliessen und einmal beim Start nachgezogen — bisher nur auf Knopfdruck im LifePlanner-Dialog. Neue Kontrakttests prüfen beide Richtungen. Neue Designwahl „Wie das System“.
- **v2.2.67:** Hotfix für den Theme-Editor (`NameError: name 'outer' is not defined`); Signatur- und Vertrauensfehler des Updaters werden nicht mehr als Netzwerkfehler gemeldet.
- **v2.2.65:** Die Kette für Update-Signaturen ist vollständig verdrahtet: Der Vertrauensanker wird vor dem Build eingebettet, `latest.json.sig` entsteht im Release und das Gate lässt ein Release ohne Signatur nicht mehr durch.
- **v2.2.64:** Ein gemeinsamer Designkatalog mit 26 Designs und 55 Rollen für LifePlanner, BudgetManager, FountainPen Manager und FreizeitManager, erzeugt und geprüft von `tools/design_sync.py`. Lesbarkeit ist Bedingung: 4,5:1 für jede Schrift auf jedem Grund, Signalfarben mindestens 2,6:1 gegen die Karte, Prüfung auf Protanopie, Deuteranopie und Tritanopie.
- **v2.2.63:** Im LifePlanner übernimmt BudgetManager das dort gewählte Designprofil beim Start (`LIFEPLANNER_THEME_FILE`, Format `lifeplanner.theme.v1`), ohne die lokale Profilwahl zu überschreiben.
- **v2.2.62:** Der GitHub-Release enthält bewusst unsigned `.lpmodule`-Pakete für Windows und Linux x86_64, jeweils mit eigener SHA-256-Datei.
- **v2.2.60:** Review-Inbox für externe Finanzdaten — nichts wird ungeprüft gebucht; getrennte Daten- und Bridge-Ordner unter LifePlanner bei weiterhin standalone startbarer App.

Die vollständige Versionsgeschichte steht in [CHANGELOG.md](CHANGELOG.md), die Funktionsliste je Version in [FEATURES.md](FEATURES.md).

---

## Für Entwickler

### Projektstruktur

```text
BudgetManager/
├── main.py                         # App-Start
├── app_info.py                     # zentrale Versionsquelle
├── settings.py                     # robuste App-Einstellungen
├── settings_dialog.py              # Einstellungsdialog
├── theme_manager.py                # Designprofile und Farbrollen
├── model/                          # Datenbank, Migrationen, Geschäftslogik
├── views/                          # PySide6-Dialoge und Tabs
├── utils/                          # i18n, Geldformatierung, Hilfsfunktionen
├── locales/                        # de/en/fr JSON-Übersetzungen
├── resources/                      # Icons und eingebettete Ressourcen
├── data/default_categories.json    # Standard-Kategorien
├── docs/                           # Handbücher, Hilfe, Release-Dokumentation
├── installer/                      # Inno-Setup-Skript
├── updater/                        # Update-Manifest und Updater
├── tools/                          # Audit-, Design- und Release-Hilfen
└── tests/                          # Core- und GUI-Smoke-Tests
```

### Entwicklungsumgebung

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

Für reproduzierbare Läufe wie in der CI stattdessen die gehashten Lockfiles verwenden:

```bash
python tools/verify_hashed_lock.py
python -m pip install --require-hashes -r requirements-build.lock
python -m pip install --require-hashes -r requirements-dev.lock
```

### Tests und Checks

Dieselben Gates laufen bei jedem Push auf `main` (`.github/workflows/push-checks.yml`):

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/exception_audit.py
python -m ruff check . --select E9,F63,F7,F82
python -m mypy model/
python -m black --check model/
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
python -m pytest tests/ -q
```

Ergänzend:

```bash
python tools/i18n_audit.py          # Übersetzungsschlüssel
python tools/verify_qt_translations.py
python tools/design_sync.py check   # Designkatalog und Kontraste
```

GUI-Tests werden ohne PySide6 automatisch übersprungen. Headless läuft alles mit `QT_QPA_PLATFORM=offscreen`.

### Versionierung

`app_info.py` ist die einzige manuelle Versionsquelle:

```python
APP_VERSION = "2.2.70"
APP_RELEASE_DATE = "21. August 2026"
```

Prüfen und synchronisieren:

```bash
python tools/sync_version.py --check
python tools/sync_version.py
```

`sync_version.py` zieht Version und Datum in `version.json`, `module.json`, `VERSION_INFO.txt`, das Installer-Skript, die `latest.json`-Templates, die Lockfile-Kopfzeilen und die Versionsköpfe der aktiven Dokumentation nach.

### Release

Ein Release entsteht aus einem Tag `v<version>` oder einem `[release]`-Commit auf `main` (`.github/workflows/build.yml`). Ein Lauf erzeugt portable ZIPs für Windows und Linux, den Windows-Installer inklusive Silent-Install-/Uninstall-Test, SBOM, unsigned `.lpmodule`-Pakete und die Updater-Dateien.

Das Update-Manifest wird aus dem Template generiert:

```bash
python -m updater.generate_manifest \
  --version 2.2.70 \
  --release-tag v2.2.70 \
  --channel stable \
  --windows-zip dist/BudgetManager-v2.2.70-portable-windows.zip \
  --linux-zip dist/BudgetManager-v2.2.70-portable-linux.zip \
  --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.2.70 \
  --out latest.json
```

`latest.json` wird zusammen mit den Plattform-ZIPs, den Installer-Artefakten, den `.lpmodule`-Paketen und den Prüfsummen in das GitHub-Release hochgeladen. Die vollständige Abfolge steht in [docs/release-checklist.md](docs/release-checklist.md), die Signaturkette in [docs/release-signing.md](docs/release-signing.md).

---

## Datenschutz

Alle Daten bleiben lokal. Standardmässig nutzt BudgetManager den portablen Datenordner `data/` neben der Anwendung. Über den Konto-Hub kann ein anderer Datenordner gewählt werden; Datenbank, verschlüsselte Konto-Dateien und Standard-Backups folgen dann diesem Ordner. Diagnose-ZIPs enthalten keine Buchungen, Namen oder Beträge.

---

## Weitere Dokumentation

- [README_INSTALLATION.md](README_INSTALLATION.md) — Installation, Start und Update im Detail.
- [docs/USER_GUIDE.de.md](docs/USER_GUIDE.de.md) — vollständige Anleitung ([EN](docs/USER_GUIDE.en.md), [FR](docs/USER_GUIDE.fr.md)).
- [docs/help/index.html](docs/help/index.html) — lokale HTML-Wissensdatenbank.
- [docs/help/README.md](docs/help/README.md) — Markdown-Version der Wissensdatenbank.
- [docs/help/mindmap.html](docs/help/mindmap.html) — Mindmap / Informations-Laufplan.
- [docs/SOFT_ZERO_BUDGET.de.md](docs/SOFT_ZERO_BUDGET.de.md) — Soft-0-Budget erklärt.
- [FEATURES.md](FEATURES.md) — Funktionsübersicht je Version.
- [CHANGELOG.md](CHANGELOG.md) — Änderungen nach Version.
- [docs/architecture.md](docs/architecture.md) — Aufbau der Anwendung.
- [docs/database.md](docs/database.md) — Datenbankschema und Migrationen.
- [docs/themes.md](docs/themes.md) — Designprofile und Farbrollen.
- [docs/release-checklist.md](docs/release-checklist.md) — Release-Ablauf.
- [docs/open-tasks.md](docs/open-tasks.md) — verbleibende externe Release-Schritte.
- [LICENSE.txt](LICENSE.txt) — Lizenz.
