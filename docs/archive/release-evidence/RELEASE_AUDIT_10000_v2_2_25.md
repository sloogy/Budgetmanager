# BudgetManager v2.2.25 – Enterprise Release-Audit mit 10.000 Loops

**Datum:** 17. Juli 2026  
**Basis:** v2.2.24 `RELEASE_WARNINGS_FIXED`  
**Ergebnis Source:** **GO**  
**Öffentliche Windows-/Linux-Binaries:** Freigabe erst nach grünen externen GitHub-Actions-Gates.

## Zusammenfassung

Die Ausgangsversion wurde funktional, strukturell, sicherheitsbezogen und hinsichtlich Release-Prozess geprüft. Der neue reproduzierbare Zustandsaudit lief vollständig mit **10.000 Loops**, **112.000 Einzelprüfungen** und **0 Findings**. Während der Vorprüfung wurden drei reale Datenintegritätsfehler sowie vier Release-Prozess-/Nachweisprobleme gefunden und behoben.

## Gefundene und behobene Fehler

### 1. Veraltete feste Tags nach Kategorienwechsel

Beim Wechsel einer Buchung auf eine andere Kategorie blieb ein fest an der alten Kategorie hinterlegter Tag an der Buchung. Jetzt werden nur veraltete feste Kategorie-Tags entfernt; manuell gesetzte sowie gemeinsam verwendete feste Tags bleiben erhalten.

### 2. Tag-Verlust bei Undo/Redo

Undo/Redo von Anlegen, Bearbeiten und Löschen stellte die Tag-Belegung einer Buchung nicht vollständig wieder her. Die Undo-Metadaten enthalten nun den exakten Tag-Zustand und stellen ihn atomar wieder her.

### 3. Buchungsquelle ging beim Lesen verloren

Automatische Quellen wie `auto_fixcost`, `auto_recurring` oder `auto_optional` wurden in mehreren Listen als `manual` zurückgegeben. Alle Tracking-Lesewege geben jetzt die gespeicherte Quelle zurück; alte Datenbanken ohne Spalte erhalten den sicheren Fallback `manual`.

### 4. Zusätzliche SQL-Heuristiken durch den Source-Fix

Die erste Korrektur erzeugte drei zusätzliche mittlere Bandit-B608-Hinweise. Die betreffenden Abfragen wurden auf vollständig statische SQL-Varianten umgestellt. Der Sicherheitsstand entspricht nun wieder exakt der freigegebenen v2.2.24-Baseline: **0 neue mittlere/hohe Findings**.

### 5. 10.000er-Audit war nicht releaseverbindlich

Der Audit ist nun ein verpflichtender Tag-Build-Job. Er erzeugt ein JSON-Artefakt und blockiert die Erstellung der Windows-/Linux-Binaries bei Fehler oder fehlendem Nachweis.

### 6. Veralteter Audit-Dateiname

Das Enterprise-UI-Audit schrieb weiterhin in eine fest codierte Datei mit `v2_2_24`. Der Dateiname wird jetzt dynamisch aus `APP_VERSION` erzeugt und lautet für diesen Release `UI_USABILITY_ADHS_1000_LOOP_MATRIX_v2_2_25.csv`.

### 7. Sicherheits-Altbestand ohne Differenzsperre

Ein neues `bandit_release_gate.py` vergleicht den aktuellen Scan mengenbewusst mit der geprüften v2.2.24-Baseline. Jeder neue mittlere oder hohe Fund und jeder hohe Fund insgesamt blockiert den Release. Zeilennummernänderungen lösen keinen falschen Alarm aus.

## 10.000-Loop-Audit

| Szenario | Loops | Schwerpunkt |
|---|---:|---|
| Kategorien-/Tag-Wechsel | 1.000 | feste und manuelle Tags |
| Tag-Undo/Redo-Lebenszyklus | 1.000 | Anlegen, Löschen, Wiederherstellen |
| Buchungsquelle | 1.000 | alle Tracking-Lesewege |
| Sparziel-Zustandsmaschine | 1.000 | Add/Update/Delete/Undo/Redo |
| Filter-Orakel | 1.000 | kombinierte Filter gegen Referenzmodell |
| Kategorie-Rename-Kaskade | 1.000 | Tabellen, Referenzen und Undo/Redo |
| Budget-Jahreskopie | 1.000 | Beträge und Auswahlregeln |
| Wiederkehrende Termine | 1.000 | Kalender-/Fälligkeitslogik |
| Update-ZIP-Sicherheit | 1.000 | Pfadtraversal und sichere Extraktion |
| SQLite-Integrität | 1.000 | Foreign Keys und verwaiste Datensätze |

**Ergebnis:** 10.000 Loops · 112.000 Checks · Seed `20260717` · **0 Findings**.

## Gesamtergebnis der Release-Gates

| Prüfung | Ergebnis |
|---|---:|
| Pytest Qt-Offscreen | **519 bestanden** |
| Enterprise Release Audit | **10.000 Loops / 112.000 Checks / 0 Findings** |
| Deep Logic | 500 Loops / 3.500 Checks / 0 Findings |
| Enterprise UI/ADHS | 1.000 Loops / 4.300 Checks / 0 WARN / 0 FAIL |
| UI/ADHS | 1.000 Loops / 15.623 Checks / 0 Findings |
| Mega Release | 1.000 Loops / 6.811 Checks / 0 Findings |
| Stabilität | 300 Loops / 2.400 Checks / 0 Findings |
| Release Logic | 100 Loops / 0 Findings |
| Fresh Logic | 100 Loops / 0 Findings |
| Black – verbindlicher Modellbereich | 40 Dateien sauber |
| Black – alle neu/geänderten Auditdateien | sauber |
| Mypy | 40 Modelldateien / 0 Fehler |
| Version/I18N/Qt-Kataloge | bestanden |
| DAU-Erststart | bestanden |
| Release-/Updater-Selbsttest | bestanden |
| Reeller 10-Sekunden-Startsmoke | ohne Traceback/Crash |
| `pip check` | bestanden |
| Bandit-Differenzgate | PASS · 0 High · 0 neue blockierende Findings |
| Produktions-API-Vergleich | **0 entfernte Produktionsklassen/-funktionen/-methoden** |

## Sicherheitseinordnung

Der vollständige statische Scan enthält 64 niedrige und 34 mittlere Hinweise, identisch zur freigegebenen v2.2.24-Baseline. Die mittleren Hinweise sind überwiegend Bandit-B608-Heuristiken bei intern kontrollierten SQL-Strukturfragmenten; Parameterwerte werden weiterhin gebunden übergeben. Sie wurden nicht verschwiegen oder global unterdrückt. Das neue Differenzgate verhindert jede unbemerkte Verschlechterung.

Der lokale Online-`pip-audit` konnte wegen fehlender DNS-Auflösung zu `pypi.org` nicht abgeschlossen werden. Das Lockfile ließ sich vollständig installieren und `pip check` ist grün. Der Tag-Build hängt zwingend am Online-Workflow `dependency-audit.yml`; ohne erfolgreichen Audit und JSON-Nachweis werden keine Binaries gebaut.

## Verbleibende externe Abnahmen

Es bestehen keine offenen automatisierbaren Source-Blocker. Für veröffentlichte Binaries müssen die bereits verdrahteten externen Gates tatsächlich grün laufen:

- Fedora 42 und Fedora latest unter Wayland bei 100/125/150/200 % Skalierung,
- Windows latest bei 100/125/150/200 % inklusive Installer-/Uninstaller-E2E,
- vollständiger Online-`pip-audit` des Lockfiles.

## Freigabeurteil

**Source v2.2.25: GO.**  
**Public Release: bedingtes GO – automatisch freigegeben, sobald alle drei externen Tag-Gates grün sind.**
