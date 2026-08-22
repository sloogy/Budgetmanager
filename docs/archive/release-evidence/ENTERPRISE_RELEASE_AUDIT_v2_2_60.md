# BudgetManager v2.2.60 – DAU-, Funktions- und Enterprise-Release-Audit

**Auditdatum:** 19. August 2026  
**Eingangsbasis:** `BudgetManager_Source_2_2_59_BASELINE_LIFEPLANNER_MERGED_TARGET_TEST`  
**Ergebnisversion:** **2.2.60**  
**Freigabeurteil:** **Lokales GO für den Quellcode / Binär-GO nach grünen GitHub-Plattform- und Signatur-Gates**

## 1. Management-Zusammenfassung

Die eingereichte v2.2.59 war funktional weit fortgeschritten, aber noch nicht sauber releasefähig. Der alte Auditbericht meldete einen synchronen Versionsstand und ein grünes Architektur-Gate, obwohl der reale Quellbaum beides widerlegte. Im unabhängigen Neu-Audit wurden diese Abweichungen reproduziert, im Quellcode behoben und mit neuen Regressionen beziehungsweise bestehenden Release-Gates erneut geprüft.

Nach den Korrekturen sind die Funktions-, Datenintegritäts-, DAU-, Architektur-, Dokumentations-, Performance- und internen Enterprise-Gates grün. Die vollständige lokale PySide6-/QtCharts-Suite, Black, Mypy, Bandit und ein Online-Dependency-Audit wurden am 19. August 2026 erfolgreich ausgeführt. Für eine öffentliche Windows-/Linux-Binärfreigabe bleiben die echten GitHub-Plattform-, Installer- und Signatur-Gates verpflichtend.

## 2. Gefundene und behobene Release-Blocker

| ID | Befund in v2.2.59 | Risiko | Behebung in v2.2.60 | Status |
|---|---|---|---|---|
| R-01 | `app_info.py` nannte den 2. August, `VERSION_INFO.txt` und Changelog den 3. August | Updater-, Installer- und Nachweisinkonsistenz | Version auf 2.2.60 angehoben, Datum zentral auf 19. August 2026 gesetzt und alle aktiven Träger synchronisiert | **Behoben** |
| R-02 | `views/main_window.py` hatte 3.664 Zeilen und überschritt das eigene Limit von 3.500 | GUI-Monolith, steigendes Absturz- und Wartungsrisiko | 255-zeiligen Einstellungsworkflow nach `views/main_window_settings.py` ausgelagert; Hauptfenster jetzt 3.418 Zeilen | **Behoben** |
| R-03 | Aktive Release-Checkliste, Open-Tasks, Updater-Beispiele und zwei Lockfile-Köpfe zeigten noch auf v2.2.52 | Falsche Tags/Artefaktnamen und unsaubere Reproduzierbarkeit | Aktive Dokumentation und drei Lockfiles auf v2.2.60 / 19. August 2026 synchronisiert | **Behoben** |
| R-04 | Versionsabhängige Auditmatrix `FINAL_RELEASE_AUDIT_1000_MATRIX_v2_2_60.csv` fehlte | Release-Integritätstest rot | Auditmatrix neu erzeugt: 1.000 Schleifen, 19.755 Prüfungen, 0 Warnungen, 0 Fehler | **Behoben** |
| R-05 | Zusätzlicher Leerabsatz in `VERSION_INFO.txt` trennte den aktuellen Releaseblock vom Kopf | Release-Integritätstest rot, aktuelle Hinweise nicht zuverlässig erkennbar | Kopf- und Releaseblockformat normalisiert | **Behoben** |
| R-06 | Historische Auditdateien v2.2.51–v2.2.59 lagen weiterhin im Root | DAU-Verwechslungsgefahr, aufgeblähtes Releasepaket | 31 historische Nachweise nach `docs/archive/release-evidence/` verschoben | **Behoben** |
| R-07 | Test-/Python-Caches wurden während Prüfungen erzeugt | Unsauberes Source-ZIP | Cleaner ausgeführt; Lint-/Release-Prozedur danach grün | **Behoben** |
| R-08 | `QChart.removeAllSeries()` löste beim Cockpit-Refresh unter Fedora/Wayland einen nativen Abort aus | Programmabsturz nach Datenänderungen | Diagramm wird atomar ersetzt und erst im nächsten Event-Loop-Durchlauf entsorgt | **Behoben** |
| R-09 | Diagnose-ZIPs enthielten rohe App- und Crash-Logs | Offenlegung von Home-Pfaden, Kategorien, Beträgen, Kommentaren oder IDs | Freie App-Logtexte werden entfernt; technische Crash-Pfade werden maskiert | **Behoben** |
| R-10 | LifePlanner-Import nutzte blockierende Warnfenster; Dialogtest erwartete eine starre Anzahl | Bedien- und Regressionstor nicht robust | Nicht-modale Warnung und struktureller Tastaturtest ohne Zählkonstante | **Behoben** |
| R-11 | Black, Mypy und der Dependency-Audit waren nicht releasegrün; `cryptography` 49.0.0 war verwundbar | CI- und Sicherheitsblocker | Format-/Typfehler behoben, `cryptography` auf 50.0.0 aktualisiert und Lock-Hashes erneuert | **Behoben** |
| R-12 | LifePlanner-Checks und ein eigener `.lpmodule`-Tag-Workflow waren im BudgetManager-Repository verdrahtet | Fremder CI-Fehler und unvollständige beziehungsweise vermischte Releases | LifePlanner-Workflows entfernt; BudgetManager-Tag veröffentlicht ausschließlich BudgetManager-Artefakte | **Behoben** |

## 3. Funktionsaudit

Die Regressionen decken die wesentlichen fachlichen Bereiche ab:

- Budgetplanung, Monats-/Jahreswerte, Kategorienhierarchie, Fixkosten und wiederkehrende Positionen.
- Tracking erfassen, bearbeiten, löschen, filtern, Tag-Zuweisungen und Undo/Redo.
- Budgetlernen, Vorschlagslogik, Töpfe, Soft-0-/Zero-Balance-Regel und Forecasts.
- Jahreswechsel, Verteilungsmuster und 13. Monatslohn.
- Sparziele als Flussbestand mit Einzahlung, Bezug, Korrektur und Teilfreigabe.
- Backup/Restore, Mehrbenutzerkonten, Wiederherstellungscode und atomare Datenübernahme.
- Updater-Integrität, SHA-256-Fail-Closed-Verhalten, Staging-Bereinigung und Signaturvertrag.
- LifePlanner-Hostvertrag, getrennte Daten-/Bridge-Ordner, Review-Inbox und FPM-Outbox; Veröffentlichung bleibt strikt im externen LifePlanner-Releaseweg.
- Cockpit-Kachellayout, Lohnzyklus-Monatsstatus, QtCharts-Lebensdauer und Setup-Absturzschutz.

### Pytest-Ergebnis

- **131 Testdateien geprüft**
- **840 Tests bestanden**
- **0 Tests übersprungen**
- **PySide6-/QtCharts-Laufzeit aktiv**, einschließlich 250 Cockpit-Diagramm-Refreshes
- **0 fehlgeschlagen**

Zusätzlich bestanden der echte Release-Selbsttest mit fünf Tabs und Renderprüfungen sowie der Updater-Selbsttest vollständig.

## 4. DAU- und Usability-Audit

| Prüfung | Ergebnis |
|---|---:|
| DAU-Enterprise-Audit | **78.166 Prüfungen / 0 Findings** |
| Headless-Erststart-E2E | **Alle Schritte bestanden** |
| Menü-Konventionen | 225 / 0 Findings |
| i18n-Parität | 16.250 / 0 Findings |
| Signal-Verdrahtung | 331 / 0 Findings |
| Theme-/DesignManager-Disziplin | 252 / 0 Findings |
| Erreichbarkeit | 50 / 0 Findings |
| Anleitung gegen Oberfläche | 62 / 0 Findings |
| Destruktive Aktionen | 15 / 0 Findings |
| Leerzustände | 10 / 0 Findings |
| Sprachprüfung | 60.930 / 0 Findings |

Der Erststart-E2E hat Kontoanlage, Datenbankmigration, 44 Standardkategorien, Kategorienbaum, Budgeteintrag, Trackingbuchung, Umbenennungs-Cascade, Löschen einer Hauptkategorie und Schutz gegen `inf`/`nan` erfolgreich durchlaufen.

## 5. Enterprise-, Logik- und Stabilitätsnachweise

| Gate | Ergebnis |
|---|---:|
| Enterprise Release Audit | **10.000 Schleifen / 112.000 Prüfungen / 0 Findings** |
| Final Release Audit | **1.000 Schleifen / 19.755 Prüfungen / 0 Warnungen / 0 Fehler** |
| Deep Logic Audit | **1.000 Schleifen / 7.000 Prüfungen / 0 Findings** |
| Mega Release Audit | **1.000 Schleifen / 6.811 Prüfungen / 0 Findings** |
| Pre-Release Stability Audit | **300 Schleifen / 2.400 Prüfungen / 0 Findings** |
| Fresh Logic Audit | **100 Schleifen / 0 Findings** |
| Release Logic Audit | **100 Schleifen / 0 Findings** |
| Architektur-Gate | **Bestanden** |
| Versionsabgleich | **Bestanden – 2.2.60** |
| Hash-Lock-Prüfung | **Bestanden – 3 Lockfiles** |
| i18n-Audit | **Bestanden** |
| Handbuch-Vollständigkeit DE/EN/FR | **Bestanden** |
| Release-Lint nach Cleanup | **Bestanden** |
| Python-Syntax/Bytecode | **Bestanden** |

Der 10.000er Enterprise-Audit prüfte Tagwechsel, Tag-Undo-Lebenszyklus, Quellen-Roundtrip, Sparziel-Zustandsmaschine, Filter-Orakel, Kategorie-Rename-Cascade, Budget-Jahreskopie, wiederkehrende Kalenderfälle, ZIP-Sicherheit und SQLite-Integrität.

## 6. Performance-Audit

Testdatensatz: **100 Kategorien, 12.000 Budgetzeilen, 50.000 Buchungen**, Datenbankgröße rund **20,36 MB**.

| Vorgang | Gemessen | Release-Limit |
|---|---:|---:|
| Tracking-Jahresfilter | 0,0264 s | 2,5 s |
| Kombinierter Trackingfilter | 0,0022 s | 1,5 s |
| Jahresübersicht | 0,0080 s | 2,5 s |
| Kategorie-Übertrag | 0,0341 s | 2,5 s |
| SQLite Quick Check | 0,0369 s | 2,0 s |

**Ergebnis:** Performance-Gate bestanden; kein lokaler Skalierungsblocker festgestellt.

## 7. Sicherheits- und Backupbewertung

Lokal grün:

- Passwort-Hash und Datenbank-Wrapping-Key bleiben kryptografisch getrennt.
- Legacy-PBKDF2-Daten werden kompatibel gelesen und hochgestuft.
- Update ohne SHA-256 beziehungsweise mit falschem Hash wird abgewiesen.
- Restore- und Bundle-Integrität, Größenlimits, ZIP-Pfadsicherheit und atomare Austauschpfade sind regressionsgetestet.
- Backup-/Restore-Regressionen, Mehrbenutzererhalt und Wiederherstellungscode sind grün.
- Keine privaten Schlüssel, Zertifikate, Datenbanken, Benutzerdateien oder `.env`-Dateien im Releasebaum gefunden.
- Bandit meldet 0 blockierende Findings; Black prüft 304 Dateien ohne Abweichung; Mypy meldet 0 Fehler in 46 Dateien.
- Der Online-Dependency-Audit meldet 0 bekannte Schwachstellen in 16 Abhängigkeiten.
- `cryptography` 50.0.0 schließt CVE-2026-69247; alle drei Hash-Lockfiles sind verifiziert.
- Diagnose-ZIPs entfernen freie App-Logtexte und maskieren Home-Pfade in Crash-Informationen.

Diese Prüfungen bleiben im GitHub-Build als verpflichtende, unabhängige Wiederholung definiert.

## 8. Plattform- und Laufzeitstatus

Lokal erfolgreich ausgeführt:

- echter PySide6-/QtCharts-Start und vollständige GUI-Testsuite,
- Release-Selbsttest mit fünf Tabs, Screenshots, Render- und Accessibility-Prüfungen,
- Updater-Selbsttest einschließlich Hash-, Signatur- und Staging-Vertrag.

Nur in den GitHub-Plattform- und Signatur-Jobs vollständig prüfbar:

- Fedora/Wayland-Screenshots bei 100/125/150/200 Prozent,
- Windows-Skalierung und Installer-Lauf,
- Authenticode-Prüfung der Windows-Artefakte.

Die Workflows dafür sind vorhanden und fail-closed. Sie bleiben verpflichtende Freigabebedingungen.

## 9. Releaseentscheidung

### Quellcode

**GO.** Alle in diesem Audit reproduzierten Quellcode-, Datenschutz-, Sicherheits-, Dokumentations- und Releaseprozessfehler wurden behoben. Die vollständige lokale Suite ist grün.

### Öffentliches Windows-/Linux-Release

**GO nach grünem `Build Executables`-Workflow.** Der einzige Tag-Workflow muss
Windows- und Linux-onedir-Build, Windows-Installer, portable ZIPs, Manifest,
Prüfsummen und GitHub-Release vollständig erzeugen. Danach Windows-Setup sowie
beide portablen Pakete stichprobenartig starten und `SHA256SUMS.txt` prüfen.

## 10. Wichtigste Änderungen gegenüber v2.2.59

- Neues Modul `views/main_window_settings.py`.
- `views/main_window.py` von 3.664 auf 3.418 Zeilen reduziert.
- Version, Datum, Installer, Updater, Modulmanifest, Workflow, Tests und aktive Dokumentation auf 2.2.60 synchronisiert.
- Drei Lockfile-Köpfe synchronisiert und verifiziert.
- Fedora-/Wayland-QtCharts-Absturz beim Refresh behoben und mit 250 Aktualisierungen regressionsgetestet.
- Diagnose-ZIP gegen Kategorien-, Betrags-, Kommentar-, ID- und Home-Pfad-Leaks gehärtet.
- LifePlanner-Warnungen nicht-modal gemacht und das Dialog-Tastatur-Gate robust erweitert.
- LifePlanner-GitHub-Checks und `.lpmodule`-Uploads aus dem BudgetManager-Release entfernt; der externe LifePlanner-Onlineweg bleibt zuständig.
- Black-, Mypy-, Bandit- und Dependency-Gates lokal grün; `cryptography` 50.0.0 schließt CVE-2026-69247.
- Vollständige PySide6-Suite: 840 Tests bestanden, 0 übersprungen, 0 fehlgeschlagen.
- Neue v2.2.60-Auditmatrix und JSON-Nachweise erzeugt.
- Historische Root-Auditdateien ins Dokumentationsarchiv verschoben.
- Releasebaum vollständig von Laufzeit- und Cache-Artefakten bereinigt.
