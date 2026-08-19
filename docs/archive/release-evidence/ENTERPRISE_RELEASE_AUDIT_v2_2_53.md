# BudgetManager v2.2.53 – Setup-Finish-Segfault-Hotfix-Audit

**Audit-Datum:** 2. August 2026  
**Release-Typ:** Kritischer Fedora-/Qt-Startablauf-Hotfix  
**Entscheidung Source-Testpaket:** **GO FÜR ZIELSYSTEM-SMOKE-TEST**  
**Öffentliche Freigabe:** **HOLD**, bis der reale Fedora-Test nach „Fertig“ ohne Segfault bestanden ist

## 1. Beobachteter Release-Blocker

BudgetManager startete, öffnete die verschlüsselte Datenbank und führte den Setup-Assistenten aus. Direkt nach dessen Abschluss wurde das verschobene Auto-Backup geprüft. Der letzte erfolgreiche Logeintrag war:

```text
model.database: Verschlüsselte DB gespeichert: c.enc
```

Danach beendete Linux den Prozess mit:

```text
segmentation fault (core dumped)
```

Ein Python-Traceback existierte nicht. Daher ist die genaue native Absturzstelle ohne Core-Stack nicht abschließend beweisbar. Der zeitliche und strukturelle Befund zeigt jedoch eindeutig auf den synchronen Übergang **QDialog.finished → Referenzfreigabe → verschlüsseltes Auto-Backup/ZIP-I/O**.

## 2. Technische Härtung

### Qt-Dialogabbau und Backup getrennt

- `_check_auto_backup()` wird nicht mehr direkt aus dem nativen `finished`-Signal des Setup-Assistenten aufgerufen.
- Die Python-Referenz auf den Setup-Dialog bleibt während des vollständigen Qt-Schliess-Stacks erhalten.
- Ein parent-gebundener 250-ms-Timer markiert den Dialog erst nach dem nativen Schliesspfad mit `deleteLater()` zur Löschung vor.
- Ein zweiter, ebenfalls am Hauptfenster gebundener Timer startet die Backup-Prüfung mit weiterem Event-Loop-Abstand.
- Der normale Startpfad nutzt denselben zentralen Scheduler; doppelte oder auf bereits zerstörte Fenster zielende Timer werden verhindert.

### Abschluss gegen Doppelaufruf geschützt

- `_finish()` ist idempotent: Doppelklick beziehungsweise Enter während des Abschlussdialogs startet den QDialog-Schliesspfad nicht erneut.
- Erfolgreicher Abschluss verwendet `accept()` statt eines semantisch abgelehnten `close()`.

### Sicherer Notstart

Bei einem weiterhin auftretenden systemspezifischen Backup-Absturz kann ausschließlich die automatische Startprüfung deaktiviert werden:

```bash
BM_SKIP_STARTUP_AUTO_BACKUP=1 ./run.sh
```

Manuelle Backups und Wiederherstellungen bleiben dabei vollständig verfügbar.

## 3. Regressionstest

Neu: `tests/test_release_2253_setup_finish_segfault.py`

Der Test sichert:

1. kein direkter `_check_auto_backup()`-Aufruf im Setup-`finished`-Signal,
2. parent-gebundene Timer für Dialogabbau und Backup,
3. zentralen Scheduler im normalen Startpfad,
4. vorhandenen Notstartschalter,
5. idempotenten Setup-Abschluss über `accept()`.

## 4. Prüfergebnisse

| Prüfung | Ergebnis |
|---|---:|
| Vollständige Pytest-Suite, in vier Zeitlimit-sicheren Blöcken | **771 bestanden, 13 übersprungen, 0 fehlgeschlagen** |
| Finale Release-Audit-Matrix | **1'000 Schleifen / 19'335 Checks / 0 Warnungen / 0 Fehler** |
| Release-Logik-Audit | **100 Schleifen / 0 Findings** |
| Neue Segfault-Regressionen | **3 bestanden** |
| DAU-Erststartprüfung | **PASS** |
| Übersetzungs-Audit DE/EN/FR | **PASS** |
| Versionssynchronisierung | **PASS – 2.2.53** |
| Bytecode-/Syntaxprüfung | **PASS** |
| Release-Lint | **PASS** |

Die 13 übersprungenen Prüfungen sind optionale GUI-/Umgebungstests, weil in der Audit-Umgebung keine echte PySide6-Fenstersitzung verfügbar ist.

## 5. Releasebewertung

### Source-Testpaket

**GO FÜR DEN REALEN FEDORA-SMOKE-TEST.** Der gefährliche synchrone Qt-/Backup-Pfad ist entfernt und durch Regressionstests abgesichert.

### Öffentliche Freigabe

**Noch HOLD.** Ein nativer Segfault kann durch Headless-Tests nicht endgültig ausgeschlossen werden. Vor Veröffentlichung muss auf dem betroffenen Fedora-System mindestens dieser Ablauf erfolgreich sein:

1. neue v2.2.53 in einen eigenen Ordner entpacken,
2. `./run.sh` starten,
3. Setup-Assistent bis „Fertig“ abschliessen,
4. mindestens 10 Sekunden warten,
5. App bedienen und sauber schliessen,
6. erneut starten und prüfen, ob das Auto-Backup ohne Absturz läuft.

Falls es erneut abstürzt, sind `data/budgetmanager_crash.log` und `coredumpctl info` beziehungsweise `coredumpctl gdb` für die exakte native Stackanalyse erforderlich. Bis dahin ermöglicht der Notstartschalter den sicheren Zugriff auf die Anwendung.
