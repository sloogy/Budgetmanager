# Enterprise Merge- und Release-Audit – BudgetManager v2.2.24

**Auditdatum:** 15. Juli 2026  
**Verglichene Versionen:** v2.2.22 UI ADHS Audit Fixed und v2.2.23 Enterprise UI ADHS Release Candidate  
**Ergebnisversion:** v2.2.24 Enterprise Merged Audited

## 1. Gesamturteil

**Automatisierte Release-Gates: GRÜN.**  
**Release-Empfehlung: technisch releasefähiger RC, öffentliche Enterprise-Freigabe nach manueller UI-Abnahme und Online-CVE-Prüfung.**

Die v2.2.23 wurde als Merge-Basis gewählt, weil sie alle Funktionen von v2.2.22 enthält, zusätzliche UI-/Accessibility-Härtungen besitzt und im unabhängigen Vergleich die sauberere Release-Basis ist. In v2.2.24 wurde zusätzlich ein reproduzierbarer Fedora-/Python-3.13-Paketierungsfehler im Lockfile behoben.

## 2. Versionsvergleich

| Kriterium | v2.2.22 | v2.2.23 | Bewertung |
|---|---:|---:|---|
| Dateien im ZIP | 323 | 329 | v2.2.23 enthält 6 zusätzliche Audit-/Testdateien |
| Vollständige Testsuite | 480 bestanden, 3 fehlgeschlagen | 491 bestanden | v2.2.23 klar besser |
| Release-Sauberkeit | 3 reproduzierbare Fehler | bestanden | v2.2.23 behebt Settings-Artefakt |
| Python-Dateien im API-/AST-Vergleich | 213 | 213+ | keine API-Verluste |
| Entfernte Klassen/Funktionen/Methoden | – | **0** | Funktionsbestand erhalten |
| Format-only geänderte Python-Dateien | – | 21 | keine Logikänderung |
| Semantisch geänderte Python-Dateien | – | 8 | Accessibility, Theme, Sprache, Cleaner |
| Neue Definitionen | – | 2 | `_associated_form_label`, `refresh_accessibility` |
| Entfernte Locale-Keys | – | **0** | keine Übersetzungsfunktion verloren |
| Neue Locale-Keys je Sprache | – | 5 | Sprache/Theme-Kontrast erweitert |
| Entfernte Theme-Keys | – | **0** | keine Theme-Funktion verloren |
| Neue Theme-Keys je Profil | – | 3 | getrennte Kontrastfarben |

### Reproduzierbarer Fehler in v2.2.22

Die Testsuite erzeugt `data/budgetmanager_settings.json`. Der Cleaner der v2.2.22 entfernte diese Laufzeitdatei nicht. Dadurch schlugen drei Release-Integritätstests fehl. v2.2.23 behebt dies vollständig.

### Merge-Entscheidung

v2.2.23 wurde vollständig übernommen. Es gab keine Funktion aus v2.2.22, die zurückgemergt werden musste. Die Merge-Prüfung war dennoch notwendig, weil sie bestätigt, dass die großen Format- und UI-Diffs keine öffentlichen Methoden oder Modelle entfernt haben.

## 3. Zusätzliche Korrekturen in v2.2.24

### Dependency-/Fedora-Härtung

Das v2.2.23-Lockfile pinnte `PySide6==6.7.3`. Dieses Paket ist unter Python 3.13 nicht installierbar; die Installation des unveränderten Release-Lockfiles brach reproduzierbar ab.

v2.2.24 verwendet die tatsächlich geprüften Versionen:

- PySide6 6.10.3
- openpyxl 3.1.5
- cryptography 49.0.0
- requests 2.34.2
- packaging 26.2
- pytest 9.0.2
- Black 25.1.0
- Mypy 1.15.0

Das Lockfile wurde in einer frischen Python-3.13-Virtualenv installiert; `pip check` meldet keine gebrochenen Abhängigkeiten.

### CI-Härtung

- CI-Matrix auf Python 3.12 und Python 3.13 erweitert.
- `python -m pip check` als Pflichtgate ergänzt.
- Neuer Regressionstest schützt Lockfile, CI-Matrix, Version und den Erhalt der v2.2.23-Enterprise-Regressionssuite.

### Versions-/Dokumentationsintegrität

Ein erster v2.2.24-Testlauf fand einen veralteten v2.2.23-Abschnitt am Anfang von `VERSION_INFO.txt`. Dieser Fund wurde behoben; die vollständige Testsuite lief danach erneut grün.

## 4. Abschlussprüfungen v2.2.24

| Prüfung | Ergebnis |
|---|---:|
| Vollständige Qt-Offscreen-Testsuite | **495 bestanden, 0 fehlgeschlagen** |
| Python-Compileall | **PASS** |
| Enterprise UI/ADHS Audit | **1000 Loops / 4300 Checks / 0 FAIL / 200 WARN** |
| Legacy UI/ADHS Audit | **1000 Loops / 15.623 Checks / 0 Findings** |
| Mega Release Audit | **1000 Loops / 6812 Checks / 0 Findings** |
| Deep Logic Audit | **500 Loops / 3500 Checks / 0 Findings** |
| Stability Audit | **300 Loops / 2400 Checks / 0 Findings** |
| Release Logic Audit | **100 Loops / 0 Findings** |
| Fresh Logic Audit | **100 Loops / 0 Findings** |
| DAU-Erststart | **PASS** |
| I18N-Audit | **PASS** |
| Versionssynchronisierung | **PASS – 2.2.24** |
| Release-/Lint-Prozedur | **PASS** |
| Black | **41 Dateien sauber** |
| Mypy Model | **0 Fehler in 40 Dateien** |
| Exaktes Release-Lockfile installieren | **PASS unter Python 3.13.5** |
| `pip check` | **PASS** |
| Headless-Startsmoke | **10 Sekunden ohne Traceback/Crash** |

Der Startsmoke wurde bewusst nach zehn Sekunden beendet, weil eine Desktop-Anwendung in der Qt-Eventloop weiterläuft. Der Exitcode 124 stammt vom Test-Timeout, nicht von einem Programmabsturz.

## 5. Sicherheitsprüfung

### Statischer Quellscan

Bandit prüfte rund 40.596 Codezeilen:

- **0 High-Severity-Funde**
- 34 Medium-Hinweise
- 65 Low-Hinweise

Alle mittleren Hinweise sind Bandit-B608-Meldungen für dynamisch zusammengesetzte SQL-Strukturen. Die betroffenen Werte werden über SQLite-Parameter gebunden. Dynamische Fragmente stammen aus:

- generierten `?`-Platzhaltern,
- fest definierten Feld-/Tabellenlisten,
- validierten Tabellen-Allowlisten,
- vorhandenen Schema-Spalten.

Es wurde keine Stelle gefunden, an der ein frei eingegebener Buchungs-, Kategorien-, Tag- oder Suchtext direkt in den SQL-String eingesetzt wird.

**Akzeptiertes Restrisiko:** Einige administrative Reset-/Diagnosepfade verwenden Tabellenbezeichner aus dem lokalen SQLite-Schema. Eine manipulierte oder beschädigte Fremddatenbank könnte dadurch eher einen Resetfehler auslösen. Für eine spätere Härtungsstufe sollten alle dynamischen SQL-Bezeichner zentral gequotet oder auf eine vollständige Allowlist reduziert werden.

### Online-Schwachstellendatenbank

`pip-audit` konnte nicht abgeschlossen werden, weil die Ausführungsumgebung `pypi.org` per DNS nicht erreichen konnte. Deshalb wird ausdrücklich **nicht** behauptet, dass die Abhängigkeiten frei von veröffentlichten CVEs sind.

**Pflicht vor öffentlicher Veröffentlichung:** `python -m pip_audit -r requirements.lock` in einer netzwerkfähigen CI ausführen und nur bei 0 ungeklärten Findings veröffentlichen.

## 6. Offene Enterprise-Warnungen

### Modale Unterbrechungen

Der Quellscan zählt 419 `QMessageBox`-Aufrufe, davon 107 reine Informationsdialoge. Dies ist kein Funktionsblocker, kann aber bei häufiger Erfassung den Arbeitsfluss unterbrechen und ist besonders bei ADHS relevant.

**Empfehlung:** Nichtkritische Erfolgsmeldungen schrittweise durch Statusleiste, Toast oder Inline-Hinweis ersetzen. Fehler, Sicherheitswarnungen und irreversible Bestätigungen bleiben modal.

### Tastaturreihenfolge

13 komplexe Dialogdateien besitzen keine explizite `setTabOrder`-Definition. Qt verwendet dort die Erstellungsreihenfolge, die nicht immer dem sichtbaren Arbeitsablauf entsprechen muss.

**Empfehlung:** Reale Tastaturtests durchführen und für die wichtigsten Erfassungsdialoge explizite Tab-Ketten hinterlegen.

### Manuelle Plattformabnahme

Noch nicht real durchgeführt:

- Fedora/Wayland bei 100 %, 125 %, 150 % und 200 % Skalierung
- Windows bei 100 %, 125 % und 150 % Skalierung
- Screenreader-Stichprobe in Deutsch, Englisch und Französisch
- visueller Smoke-Test aller 25 Themes auf realen Displays
- Windows-Installer- und Updater-End-to-End-Test

## 7. Freigabestatus

### Für internen Test / Release Candidate

**FREIGEGEBEN.** Alle lokal automatisierbaren Gates sind grün, der Merge ist funktionsvollständig und das Fedora/Python-3.13-Lockfileproblem ist behoben.

### Für öffentlichen finalen Enterprise-Release

**BEDINGT FREIGEGEBEN.** Vor Veröffentlichung sind mindestens erforderlich:

1. Online-`pip-audit` ohne ungeklärte Findings,
2. Fedora-/Wayland- und Windows-Skalierungssmoke,
3. Tastaturtest der 13 komplexen Dialoge,
4. Windows-Build/Installer/Updater-End-to-End-Test.

## 8. Mitgelieferte Nachweise

- `UI_USABILITY_ADHS_1000_LOOP_MATRIX_v2_2_24.csv`
- `audit_artifacts/MERGE_API_AST_COMPARISON_v2_2_22_vs_v2_2_23.csv`
- `audit_artifacts/MERGE_JSON_SCHEMA_COMPARISON_v2_2_22_vs_v2_2_23.csv`
- `audit_artifacts/BANDIT_STATIC_SCAN_v2_2_24.json`
- `audit_artifacts/DEEP_LOGIC_AUDIT_500_v2_2_24.json`
- `AUDIT_EXECUTION_LOG_v2_2_24.txt`
