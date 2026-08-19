# BudgetManager v2.2.24 – Behebung der Release-Warnungen

**Stand:** 16. Juli 2026  
**Basis:** `BudgetManager_Source_2_2_24_FINAL_MERGED_AUDIT_FIXED.zip`

## Ergebnis

Die vier gemeldeten Release-Warnungen wurden im Quellcode und in der Release-Pipeline bearbeitet. Die Anwendungssuite besteht 506 Tests. Das Enterprise-UI-/ADHS-Audit endet mit 0 WARN und 0 FAIL.

## 1. Modale Meldungen

Die ursprüngliche Zahl 419 enthielt auch Enum- und Button-Konstanten. Eine AST-Auswertung der tatsächlichen Aufrufe ergab vor der Änderung:

- 107 Informationsdialoge
- 102 Warnungsdialoge, davon 97 ohne ausgewertete Benutzerentscheidung
- 70 Fehlerdialoge
- 26 Entscheidungsdialoge
- insgesamt 305 tatsächliche `QMessageBox`-Aufrufe

Nach der Änderung:

- 0 modale Informationsdialoge
- 0 passive modale Warnungen
- 5 Warnungsdialoge mit ausgewerteter Entscheidung
- 70 echte Fehlerdialoge
- 26 Entscheidungsdialoge
- insgesamt 101 bewusst modale Sicherheits-, Fehler- oder Entscheidungsdialoge

Die 204 unterbrechenden Hinweise wurden durch nicht-modale Statusmeldungen beziehungsweise Dialog-Toasts ersetzt. Sie behalten den Eingabefokus, sind nicht per Enter auslösbar und besitzen Accessibility-Name, Beschreibung und Qt-Alert-Event.

## 2. Tab-Reihenfolge

`utils/accessibility.py` setzt eine deterministische Tab-Kette anhand der visuellen Layout-Reihenfolge und ergänzt dynamisch registrierte Felder am Ende des Ereigniszyklus.

Abgedeckt sind:

- 13 komplexe Dialogdateien
- 20 Dialogklassen
- verzögert erzeugte Widgets und Seitencontainer
- Regressionstest für Fokus-Kette und Quellabdeckung

## 3. Plattform, Accessibility, Installer und Updater

Neue verpflichtende Release-Gates:

- Fedora 42 und `latest` mit nativem Headless-Weston/Wayland bei 100, 125, 150 und 200 Prozent Skalierung
- Windows `latest` bei 100, 125 und 150 Prozent Skalierung
- Qt-Accessibility-Vertrag mit AT-SPI-Laufzeit, GUI- und Tastaturtests
- installationsnaher GUI-Selbsttest ohne Produktivdaten
- Windows-Silent-Installation, Start der installierten EXE, Silent-Deinstallation und Prüfung des erhaltenen Nutzerdatenordners
- isolierter Updater-E2E aus Source und installierter EXE

Der Updater-E2E prüft Staging-Hash, Payload-Erkennung, Rollback-Backup, Austausch der Programmdateien und Erhalt der Nutzerdaten. Dabei wurde ein Randfehler behoben: `_update_marker.json` verhindert nicht mehr die Erkennung eines einzelnen Top-Level-Ordners im Update-ZIP.

Die Tag-Build-Pipeline hängt direkt von `platform-release-gates` und `dependency-security-gate` ab. Scheitert eines dieser Gates, werden keine Release-Binaries gebaut.

## 4. Abhängigkeitssicherheit

Ergänzt wurden:

- `pip-audit==2.10.1` als festes Auditwerkzeug
- Online-Audit des kompletten `requirements.lock`
- JSON-Audit-Artefakt mit `if-no-files-found: error`
- wöchentlicher Auditlauf
- Dependabot für Python und GitHub Actions
- `pip check` nach Installation des Lockfiles

Der lokale Online-Aufruf scheitert in der Prüfumgebung weiterhin an deren DNS-Auflösung zu `pypi.org`. Das ist keine Anwendungs- oder Lockfile-Störung. Der Tag-Build ist deshalb an den Online-Workflow gekoppelt und kann ohne erfolgreiches Audit nicht fortfahren.

Zusätzlich wurde der aktuelle Stand der direkten Lockfile-Pakete gegen die PyPA-Advisory-Datenbank geprüft. Die dokumentierten Versionsgrenzen liegen unter den eingesetzten Versionen. Dieser Direktvergleich ersetzt nicht das vollständige transitive Online-Audit; er ergänzt dessen CI-Nachweis.

## Abschlussmatrix

| Gate | Ergebnis |
|---|---:|
| pytest Qt-Offscreen | 506 bestanden |
| Enterprise UI/ADHS | 1000 Loops, 4300 Checks, 0 WARN, 0 FAIL |
| UI/ADHS | 1000 Loops, 15.623 Checks, 0 Findings |
| Mega Release | 1000 Loops, 6.812 Checks, 0 Findings |
| Deep Logic | 500 Loops, 3.500 Checks, 0 Findings |
| Stabilität | 300 Loops, 2.400 Checks, 0 Findings |
| Release Logic | 100 Loops, 0 Findings |
| Fresh Logic | 100 Loops, 0 Findings |
| Version / Compile / I18N / DAU / Lint | bestanden |
| Black | bestanden |
| Mypy | 40 Dateien, 0 Fehler |
| GUI-Selbsttest | bestanden |
| Updater-E2E | bestanden |
| `pip check` | bestanden |
| Workflow-YAML | gültig |

## Freigabe

**Source-Release: GO.**

Die Plattform-, Installer- und vollständigen Online-Abhängigkeitsprüfungen sind keine unverbindlichen manuellen Warnungen mehr, sondern verpflichtende technische Gates des Tag-Builds. Öffentliche Binaries werden nur erzeugt, wenn diese externen GitHub-Runner erfolgreich durchlaufen.
