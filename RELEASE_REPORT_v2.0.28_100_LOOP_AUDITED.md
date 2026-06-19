# BudgetManager v2.0.28 – Release-Report nach 100-Loop-Logiktest

Datum: 19. Juni 2026  
Basis: `BudgetManager_Source_2_0_28_ICON_INSTALLER_READY.zip`  
Ergebnis: **GO als Source-Release-Candidate** mit Pflicht-Smoke-Test der echten GitHub-Binärartefakte.

## 1. Kurzurteil

Die Version ist als **Source-Release-Candidate v2.0.28** releasefähig. Die statischen und automatisierten Prüfungen sind grün:

| Bereich | Ergebnis |
|---|---:|
| Python-Syntax / Compileall | ✅ PASS |
| Testsuite | ✅ 154 passed, 2 skipped |
| Versions-Sync | ✅ 2.0.28 synchron |
| i18n-Audit | ✅ keine verdächtigen hardcoded UI-Strings |
| DAU-Erststart-Check | ✅ PASS |
| 100-Loop-Release-Logiktest | ✅ 100/100 PASS, 0 Findings |
| Private Runtime-Daten im Paket | ✅ keine `users.json`, keine `.enc`-DBs |

**Wichtige Einschränkung:** In dieser Linux-Sandbox wurden keine echten PyInstaller-Binaries und kein echter Inno-Setup-Installer gebaut. Die GitHub-Actions-Datei wurde statisch und per Regressionstest geprüft. Vor öffentlichem Release müssen die durch GitHub erzeugten Artefakte auf Windows und Linux kurz gestartet und der Updater real durchgeklickt werden.

## 2. Während des Audits gefundene und behobene Punkte

### 2.1 Anleitung DE/EN/FR ergänzt

Neu erstellt:

- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`

Die Anleitungen erklären für normale Anwender:

- Grundidee der App
- Kategorien und Konten
- Budget erfassen
- Buchungen/Tracking
- Forecast/Budgetvorschläge
- Übersicht und Graphen
- Updatewege
- Backup/Restore und Datenordner

`README.md` verweist jetzt direkt auf alle drei Anleitungen.

### 2.2 Installer-Lokalisierung gehärtet

`installer/budgetmanager_setup.iss` wurde erweitert:

- Deutsch, Englisch und Französisch sind als Installer-Sprachen vorhanden.
- Eigene Wizard-Seiten nutzen jetzt `CustomMessage(...)` statt hart deutscher Texte.
- Datenordner-Seite, Sprache/Währung/Buchungstag und Hinweistexte sind lokalisiert.
- Die dreisprachigen Anleitungen werden in `docs/` mit in die Installation kopiert.

### 2.3 Sichtbares `TOTAL` im Budget-Footer entfernt

Im Budget-Reiter wurde ein sichtbarer harter Footer-Text behoben:

- Vorher: Footer-Erkennung hing am Text `TOTAL`.
- Nachher: Footer-Erkennung nutzt eine stabile Row-Rolle `ROLE_ROW_KIND`.
- Sichtbarer Text kommt jetzt aus `tr("header.total")`.

Damit erscheint der Footer je nach Sprache sauber als Gesamt/Total/Total und die Logik ist nicht mehr vom sichtbaren Text abhängig.

### 2.4 Regressionstests ergänzt

`tests/test_release_integrity.py` enthält zusätzliche Tests für:

- übersetzten Budget-Footer statt hartem `TOTAL`
- DE/EN/FR-lokalisierte Installer-Seiten
- vorhandene dreisprachige Anleitung
- Erklärung von Graphen, Forecast und Updates in der Anleitung

### 2.5 100-Loop-Audit-Script ergänzt

Neu:

- `tools/release_logic_audit_100.py`

Das Script führt 100 deterministische Release-Logik-Loops aus und prüft jedes Mal dieselben kritischen Bereiche. Ergebnis dieses Laufs:

```text
BudgetManager Release-Logik-Audit
Loops: 100
Status: PASS
Findings: 0
```

## 3. Abdeckung deiner geforderten Punkte

### 3.1 Anleitung in DE/FR/ENG

**Status: abgedeckt.**

Geprüft wurden:

- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`
- README-Verlinkung
- Installer nimmt die Dateien mit

### 3.2 Forecast-Logik auf Denkfehler geprüft

**Status: automatisiert geprüft.**

Der 100-Loop-Test prüft insbesondere:

- `0` allein darf bei Fixkosten kein Vorschlag-Auslöser sein.
- Echte wiederkehrende Fixkosten dürfen bei wiederholter Überschreitung angehoben werden.
- Flexible Budgets wie Hobby 40 CHF mit 20/30/0 dürfen nicht wegen einer Null starr nach unten gezogen werden.
- Gegensätzliche Ausreißer wie 450 CHF und danach 350 CHF bei 400 CHF Budget erzeugen keinen unnötigen Vorschlag.
- Ein einzelner Buchungsmonat erzeugt keinen Fantasie-Vorschlag.

### 3.3 Hardcoded Strings ersetzt

**Status: geprüft und nachgehärtet.**

Ausgeführt:

- `python tools/i18n_audit.py`
- 100-Loop-Release-Audit
- Regressionstest gegen bekannten `TOTAL`-Rückfall
- Regressionstest gegen bekannte deutsche EN/FR-Restwerte

Ergebnis: keine verdächtigen hardcoded UI-Strings im Audit.

### 3.4 Git / Release Platform

**Status: statisch abgedeckt, echte Ausführung noch nötig.**

Die GitHub-Action `.github/workflows/build.yml` deckt ab:

- Windows-Build mit PyInstaller
- Linux-Build mit PyInstaller
- Windows-Installer mit Inno Setup
- Portable-ZIP mit stabilen Startnamen
  - `BudgetManager.exe`
  - `BudgetManager`
  - `start-windows.cmd`
  - `start-linux.sh`
- `latest.json` für den Updater
- Upload der Artefakte ins GitHub Release

Die Action enthält zusätzlich:

- Versions-Sync-Check
- Compileall
- Black-Check für `model/`
- mypy für `model/`
- komplette Testsuite

Nicht lokal ausgeführt: echte GitHub-Actions-Runner, weil diese Sandbox keine Windows/Inno-Setup-Buildumgebung ist.

### 3.5 DAU-freundlich

**Status: geprüft.**

Der vorhandene Check `tools/dau_first_run_check.py` ist grün. Zusätzlich wurden die Anleitungen so geschrieben, dass ein normaler Anwender versteht:

- Wo Daten liegen
- Wie man Kategorien/Budget/Buchungen nutzt
- Was Forecast-Vorschläge bedeuten
- Was die Graphen zeigen
- Wie Updates und Backups funktionieren

### 3.6 Graphen logisch inklusive Erklärung

**Status: abgedeckt.**

Geprüft wurden:

- bestehende Overview-/Graphen-Tests
- Top-Buchungen nach Betrag
- Budget-vs-Tracking-Darstellungen
- Anleitung erklärt Balken-, Kreis-/Donut- und Verlaufsgrafiken
- Verhalten bei fehlenden Daten: Hinweis statt leerer Graph

### 3.7 Updater auf allen Ebenen funktionsfähig

**Status: automatisiert und statisch geprüft, echter Live-Smoke noch nötig.**

Abgedeckte Updatewege:

- Windows/Linux bevorzugen das portable ZIP aus `latest.json`.
- `windows_installer` ist zusätzlich im Manifest vorhanden.
- Direkte Windows-EXE und Linux-Binary sind als Release-Assets vorhanden.
- Check-Update schreibt ein strukturiertes Ergebnis für das GUI.
- Apply-Update verwendet die tatsächlich geprüfte/staged Version, nicht versehentlich eine alte höhere Staging-Version.
- Stable Startnamen werden im Portable-ZIP verwendet, damit der Updater nicht an versionierten Dateinamen scheitert.

Echter Pflicht-Smoke nach GitHub Build:

1. Windows Installer installieren und App starten.
2. Windows Portable-ZIP starten.
3. Linux Portable-ZIP starten.
4. Update-Dialog öffnen: Check → Download/Staging → Jetzt aktualisieren & neu starten.
5. Prüfen, dass `data/` und Backups erhalten bleiben.

## 4. Ausgeführte Befehle

```bash
python -m compileall -q .
python tools/sync_version.py --check
python tools/i18n_audit.py
python tools/dau_first_run_check.py
pytest -q
python tools/release_logic_audit_100.py
```

Ergebnisse:

```text
Alle Versionsdateien synchron: 2.0.28
[OK] Keine verdächtigen hardcoded UI-Strings gefunden
ERGEBNIS: ALLE CHECKS BESTANDEN
154 passed, 2 skipped
100/100 Loops PASS, 0 Findings
```

## 5. Nicht lokal ausführbar / nicht behauptet

Folgende Punkte wurden in dieser Umgebung nicht real ausgeführt:

- PyInstaller-Frozen-Build auf Windows
- PyInstaller-Frozen-Build auf Linux als echtes Release-Binary
- Inno-Setup-Installer-Build auf Windows
- echter Updater-Live-Test gegen ein GitHub Release

Diese Punkte sind in GitHub Actions vorbereitet und müssen dort + auf echten Systemen gesmoke-testet werden.

## 6. Release-Empfehlung

Empfehlung:

1. Diese ZIP als Source-Release-Candidate verwenden.
2. Tag `v2.0.28` setzen oder bestehenden Tag auf diese finale Quelle bringen.
3. GitHub Actions durchlaufen lassen.
4. Die drei echten Artefakte testen:
   - Windows Installer
   - Windows Portable
   - Linux Portable
5. Danach öffentliches Release freigeben.

**Endurteil:** Für Source/Logik/i18n/Tests ist v2.0.28 releasefähig. Für öffentliche Binärverteilung fehlt nur noch der echte GitHub-Build- und Smoke-Test.
