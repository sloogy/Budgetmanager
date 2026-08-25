# Release-Audit-Historie v2.1.7 bis v2.2.60

**Zusammengefasst am:** 25. August 2026 (Release v3.0.6)
**Ersetzt:** 49 einzelne Audit-, Merge- und Fix-Berichte (zusammen rund 240 KB)

Dieses Dokument fasst die Auditberichte der Versionsreihen 2.1.x und 2.2.x zu
einer durchsuchbaren Chronik zusammen. Grund für die Zusammenfassung: Der Ordner
enthielt für nahezu jede Patchversion einen eigenen Bericht mit stark
überlappendem Rahmentext. Wer einen bestimmten Befund suchte, musste 49 Dateien
öffnen.

**Was hier steht:** je Version der Anlass, die tatsächlich gefundenen Fehler und
deren Behebung. **Was hier nicht steht:** die vollständigen Prüfprotokolle und
Zwischenstände. Die maschinell erzeugten Nachweise (Matrizen als `.csv`,
Ausführungsprotokolle als `.txt`, Messwerte als `.json`) bleiben unverändert in
diesem Ordner erhalten — sie sind Rohdaten, keine Prosa, und werden von Gates
teilweise direkt referenziert.

Zwei Berichte bleiben zusätzlich als Einzeldatei bestehen, weil Regressionstests
sie namentlich prüfen:

- `KILLCRITIC_X10THINK_10000_v2_2_25.md`
- `README.md` (Index, wird von `tools/release_evidence_index.py` erzeugt)

---

## Reihe 2.1.x — Lesbarkeit und Tracking-Erfassung

### v2.1.7

Der Schwerpunkt lag auf der Lesbarkeit der Übersicht und der Geschwindigkeit der
täglichen Erfassung.

- **Tracking-Kurzbeschriftungen:** Parent-Kategorien erschienen im Tracking als
  eigene Buchungszeile vor ihren Unterkategorien. Unterkategorien wurden auf
  Kurzanzeige umgestellt.
- **Stiller Kategorieverlust (Fehler):** `TrackerDialog._set_combo_by_data()`
  fand für eine Preset-Kategorie wie `Wohnen` — ein Parent mit Kindern, der seit
  2.1.7 nicht mehr im Picker gelistet wird — weder einen itemData- noch einen
  Text-Treffer und kehrte still zurück. Die Auswahl blieb auf dem ersten
  Picker-Eintrag stehen; beim Speichern wäre die Buchung ungewollt umgehängt
  worden.
- **Diagramme:** Der Plan/Ist-Donut wurde nach einem zu weitgehenden Umbau
  wiederhergestellt; der daneben liegende, verwirrende Kreis blieb ersetzt.
- **Wiki/Integration:** Vergleich von RC- und integriertem Stand, Zusammenführung
  der Wiki-Korrekturen.

*Ursprüngliche Berichte: `AUDIT_FIX_REPORT_v2_1_7_TRACKING_SHORT_LABELS`,
`PRE_RELEASE_FIX_REPORT_v2_1_7_RC2_FIX12`,
`RELEASE_COMPARE_INTEGRATION_REPORT_v2_1_7`,
`RELEASE_REPORT_v2_1_7_DONUT_READABILITY`,
`RELEASE_REPORT_v2_1_7_GRAPH_READABILITY`,
`RELEASE_REPORT_v2_1_7_RC_vs_INTEGRATED_WIKI_FIXED`,
`RELEASE_REPORT_v2_1_7_TRACKING_SHORT_LABELS`*

---

## Reihe 2.2.x — Härtung, Sicherheit und Auditdisziplin

### v2.2.1 bis v2.2.3 — Einführung der KILLCRITIC-Batterie

Erste systematische Auditläufe. Ergebnis jeweils „releasefähig als Source-Paket"
mit der von Anfang an mitgeführten Einschränkung: GUI-Smoke sowie echte Windows-
und Linux-Build-Smokes müssen in GitHub Actions beziehungsweise auf den
Zielsystemen laufen, weil PySide6 in der Audit-Umgebung fehlt. Diese
Einschränkung gilt bis heute unverändert.

In v2.2.2 zusätzlich behoben: falscher Standardwert für den Fälligkeitstag
wiederkehrender Positionen (`recurring_day`).

### v2.2.6 — Lern-Zustand-Kaskade

Statt die bereits grünen Audits erneut laufen zu lassen, wurde tiefer geprüft.
Gefunden wurde eine Kaskade im Lern-Zustand der Kategoriezuordnung.

### v2.2.7 — Restore-Code gehärtet

Härtung der Wiederherstellungskette auf Basis von v2.2.6.

### v2.2.11 — Sicherheitsanalyse (schwerwiegend)

Randbedingung des Projekts: Die Datenbank ist immer verschlüsselt. Damit
verschiebt sich die Angriffsfläche vom Chiffrat auf den Schlüssel und den Weg in
die Installation. Beide Achsen wurden geprüft.

**Befund HOCH — Schlüsselmaterial war world-readable.** `users.json` wurde mit
dem Standard-umask geschrieben, auf typischen Linux-Systemen `0644`. Bei
Quick-Konten liegt `db_key_b64` dort im Klartext. Jeder andere lokale Benutzer
konnte die Datei lesen und die `.enc`-Datenbank vollständig entschlüsseln. Die
Verschlüsselung war gegenüber lokalen Mitbenutzern damit wirkungslos. Empirisch
bestätigt und behoben.

### v2.2.12 — Updater-Staging

Nach jedem heruntergeladenen und per SHA-256 geprüften Asset wird der komplette
Staging-Ordner gelöscht und neu aufgebaut. Alte, manipulierte oder
unvollständige Dateien können dadurch nicht mehr in ein neues Update gelangen.

### v2.2.13 — UX-Test

### v2.2.17 — Logikfehler mit frischem Blick

Die bestehenden Audits (Logik 100, Deep 500/3500, KILLCRITIC 100) waren grün.
Geprüft wurden deshalb gezielt die Nahtstellen der jüngsten Konsolidierung:
Edit-Modus, Fixkosten-Dialog und angrenzende Pfade.

### v2.2.20 — Vollständige Batterie mit 1000 Schleifen

Basis v2.2.19, die das Label `FULL_RELEASE_AUDITED` trug.

### v2.2.22 — Falsche Erfolgsmeldungen im Vorgängerbericht

Der mitgelieferte v2.2.21-Bericht meldete „1000 PASS / 0 FAIL". Die Verifikation
am Code ergab ein anderes Bild: **zwei seiner Kernaussagen waren falsch.** Dieser
Vorfall prägte die spätere Auditmethodik.

### v2.2.23 — UI-/ADHS-Audit

Keine automatisiert erkannten Release-Blocker. Zwei UX-Bereiche blieben bewusst
als Warnung offen und wurden ausdrücklich nicht schöngerechnet.

### v2.2.24 — Merge zweier unvollständiger Zweige

Beide Eingangsbäume waren parallele, jeweils unvollständige Merges derselben
Basis (v2.2.22 ↔ v2.2.23). Keiner war allein releasefähig.

Die Session-Erfahrung — v2.2.19 trug das Label `FULL_RELEASE_AUDITED` und
enthielt trotzdem einen passwortumgehenden Notfall-Reset — diktierte die
Methode: **jede Behauptung der Vorberichte wurde am Code nachgeprüft**, per Diff,
per AST-Vergleich, per eigener Nachmessung, per Live-Ausführung der Logik. Das
ist bis heute das Vorgehen.

Zusätzlich behoben: reproduzierbarer Fedora-/Python-3.13-Paketierungsfehler im
Lockfile. Vier gemeldete Release-Warnungen wurden abgearbeitet; die Suite bestand
506 Tests.

### v2.2.25 — Auditwerkzeuge auf 10 000 Schleifen

`tools/final_release_audit_1000.py`: 10 bislang ungeprüfte Domänen × 100 Loops =
1000 Loops, 20 855 Prüfungen, mit echten Funktionsläufen statt reiner
Quelltextmuster. Der Zustandsaudit lief mit 10 000 Loops und 112 000
Einzelprüfungen bei 0 Findings. In der Vorprüfung wurden drei reale
Datenintegritätsfehler gefunden und behoben.

### v2.2.27, v2.2.29, v2.2.30 — Gate-Resynchronisierung und Deep-Audit-Fixes

Auditgates und Quellbaum waren auseinandergelaufen; Resynchronisierung sowie
Abarbeitung offener Punkte aus dem Deep Audit.

### v2.2.34 — Soft-Zero-Budget auffindbar gemacht

Die Einstellung war fachlich implementiert, aber unter der Bezeichnung „sanfte
Null-Bilanz-Regel" schwer auffindbar und in der Anleitung nicht ausreichend
erklärt.

### v2.2.35 und v2.2.48 — Handbuchvollständigkeit

Die Benutzerhilfe wurde gegen das tatsächliche Funktionsinventar geprüft und
ergänzt: vollständig, dreisprachig, widerspruchsfrei. Beide Berichte halten
ausdrücklich fest, dass keine neue Druck- oder PDF-Funktion implementiert wurde
und dass die Dokumentation dieses Fehlen transparent benennt.

### v2.2.43 bis v2.2.45 — Dashboard-Zusammenführung

Die Dashboard-Optik aus v2.2.42 blieb erhalten, die robustere Layout-,
Persistenz- und Drag-and-drop-Logik aus v2.2.41 wurde übernommen.

### v2.2.48 — Freigabekriterien für Binaries festgeschrieben

Fünf Bedingungen für eine öffentliche Binärfreigabe: GitHub Actions inklusive
Bandit und `pip-audit`; PySide6-GUI-Smoke unter Fedora/Wayland und Windows;
Starttest von Installer und portablen Paketen auf sauberen Systemen;
Authenticode-Signatur und Build-Attestation; signiertes `latest.json` samt
passenden SHA-256-Summen. Diese Liste gilt weiterhin.

### v2.2.51 — Absturz im Sprachwahldialog

Der reale Fedora-/Python-3.14-Erststart brach im Sprachwahldialog ab.

### v2.2.52 — Comprehension im Klassenkörper (Startabbruch)

Beim Import von `views/tabs/cockpit_tab.py` brach die Anwendung vor dem Aufbau
des Hauptfensters ab:

```text
NameError: name 'LEFT_COLUMN_PANELS' is not defined
```

**Ursache:** `DEFAULT_PANEL_COLUMNS` wurde durch eine Dictionary-Comprehension
innerhalb des Klassenkörpers von `CockpitTab` erzeugt. Python führt
Comprehensions in Klassenkörpern in einem eigenen Scope aus; das unmittelbar
zuvor definierte Klassenattribut `LEFT_COLUMN_PANELS` war darin nicht sichtbar.

**Korrektur:** Die unveränderlichen Layoutvorgaben werden auf Modulebene erzeugt
(`_COCKPIT_LEFT_COLUMN_PANELS`, `_COCKPIT_DEFAULT_PANEL_COLUMNS`); die Klasse
übernimmt daraus nur noch Kopien. Abgesichert durch
`tools/class_scope_audit.py`.

### v2.2.53 und v2.2.54 — Segmentation Fault ohne Python-Ausnahme

In v2.2.53 lief die Anwendung nach dem Setup-Assistenten in die verschobene
Auto-Backup-Prüfung und brach dort ab. In v2.2.54 stürzte sie nach Abschluss des
Assistenten beziehungsweise nach dem Hinzufügen von Buchungen mit
`Segmentation fault (core dumped)` ab — ohne Python-Traceback. Beides waren
Qt-Lebensdauerprobleme auf C++-Ebene, die für reine Python-Tests unsichtbar sind.

### v2.2.55 und v2.2.56 — Cockpit-Layout

Im fixierten Layout liessen sich die Kacheln nicht frei verschieben. Beide
Spalten waren über gemeinsame Rasterzeilen gekoppelt: Eine hohe Kachel links
reservierte dieselbe Zeilenhöhe rechts, sodass eine rechte Kachel nicht in den
sichtbar freien Bereich hochrücken konnte. Zusätzlich fehlte während des Ziehens
eine eindeutige Vorschau.

### v2.2.59 — Selektive Übernahme

v2.2.56 blieb führend; v2.2.58 wurde nicht vollständig darüberkopiert, sondern
nur die zuvor vereinbarten Verbesserungen wurden übernommen.

### v2.2.60 — Zwölf Release-Blocker

Die eingereichte v2.2.59 war funktional weit fortgeschritten, aber nicht sauber
releasefähig. Der alte Auditbericht meldete einen synchronen Versionsstand und
ein grünes Architektur-Gate, obwohl der reale Quellbaum beides widerlegte.

| ID | Befund | Behebung |
|---|---|---|
| R-01 | `app_info.py` und `VERSION_INFO.txt`/Changelog nannten verschiedene Daten | Version und Datum zentral synchronisiert |
| R-02 | `views/main_window.py` mit 3664 Zeilen über dem Limit von 3500 | 255-zeiliger Einstellungsworkflow nach `views/main_window_settings.py` ausgelagert |
| R-03 | Release-Checkliste, Open-Tasks, Updater-Beispiele und zwei Lockfile-Köpfe zeigten auf v2.2.52 | Aktive Dokumentation und drei Lockfiles synchronisiert |
| R-04 | Versionsabhängige Auditmatrix fehlte | Neu erzeugt: 1000 Schleifen, 19 755 Prüfungen, 0 Warnungen, 0 Fehler |
| R-05 | Leerabsatz in `VERSION_INFO.txt` trennte Releaseblock vom Kopf | Format normalisiert |
| R-06 | Historische Auditdateien v2.2.51–v2.2.59 lagen im Projekt-Hauptordner | 31 Nachweise nach `docs/archive/release-evidence/` verschoben |
| R-07 | Test-/Python-Caches wurden während Prüfungen erzeugt | Cleaner ausgeführt, Lint-Prozedur danach grün |
| R-08 | `QChart.removeAllSeries()` löste beim Cockpit-Refresh unter Fedora/Wayland einen nativen Abort aus | Diagramm wird atomar ersetzt und erst im nächsten Event-Loop-Durchlauf entsorgt |
| R-09 | Diagnose-ZIPs enthielten rohe App- und Crash-Logs | Freie App-Logtexte entfernt, technische Crash-Pfade maskiert |
| R-10 | LifePlanner-Import nutzte blockierende Warnfenster; Dialogtest erwartete starre Anzahl | Nicht-modale Warnung, struktureller Tastaturtest ohne Zählkonstante |
| R-11 | Black, Mypy und Dependency-Audit nicht grün; `cryptography` 49.0.0 verwundbar | Format-/Typfehler behoben, `cryptography` auf 50.0.0 angehoben, Lock-Hashes erneuert |
| R-12 | LifePlanner-Checks und ein `.lpmodule`-Tag-Workflow im BudgetManager-Repository verdrahtet | LifePlanner-Workflows entfernt |

---

## Wiederkehrende Muster

Vier Fehlerklassen traten über die Reihe hinweg mehrfach auf. Sie sind der Grund
für die heute vorhandenen strukturellen Gates:

1. **Berichte, die nicht dem Code entsprachen** (v2.2.19, v2.2.21, v2.2.59).
   Gegenmaßnahme: Jede Behauptung wird am Quellbaum nachgemessen, nicht
   übernommen.
2. **Qt-Lebensdauerfehler ohne Python-Traceback** (v2.2.53, v2.2.54, v2.2.60
   R-08). Für Python-Tests unsichtbar; Gegenmaßnahme sind AST-basierte
   Strukturgates.
3. **Startabbrüche trotz grüner Testbatterie** (v2.2.51, v2.2.52). Ursache: Alle
   GUI-Tests hängen an `pytest.importorskip("PySide6")`; Importfehler in
   App-Modulen waren dadurch unsichtbar.
4. **Versionsdrift über parallele Dokumente** (v2.2.29, v2.2.60 R-01/R-03).
   Gegenmaßnahme: `tools/sync_version.py` und
   `docs/version_references.lock.json`.

---

## Anhang: eingegliederte Einzeldokumente aus `docs/`

Diese fünf Dokumente lagen als versionsgestempelte Einmal-Berichte im aktiven
`docs/`-Ordner und wurden in v3.0.6 hierher überführt. Keines war im Code oder
in Gates referenziert.

### Budget-Tab als Baum (V2.0-Patch, `CHANGES_TREE_BUDGET.md`)

Kategorien werden im Budget-Reiter als Baum angezeigt: Parent mit `▸`, Blatt mit
`•`, Einrückung zeigt die Tiefe. Parent- und Child-Summen werden getrennt
ausgewiesen.

### v2.2.33 — Seitenleiste blieb dunkel (`release-verification-v2.2.33-sidebar-doc-cleanup.md`)

Stand: 25. Juli 2026. Bei einem hellen BudgetManager-Design konnte die linke
Navigation dennoch dunkel bleiben. Ursache war eine lokale Stylesheet-Regel in
`views/main_window.py`, die Farben über Qt-`palette(...)` bezog. Diese Palette
stammte unter GNOME aus dem dunklen Systemdesign und war spezifischer als das
allgemeine App-Stylesheet. Derselbe Fehlertyp trat später erneut in
`views/tabs/budget_tab.py:_apply_table_styles()` auf.

### v2.2.36 — Hilfe-Einstieg fehlte unter Linux (`release-verification-v2.2.36-wiki-linux-help.md`)

In der linken Seitenleiste fehlte auf Linux/Fedora der erwartete Hilfe-Einstieg
mit Fragezeichen. Der neue Knopf verwendet bewusst normalen ASCII-Text (`? Hilfe`)
statt eines Emojis, weil die Emoji-Darstellung nicht auf allen Zielsystemen
verfügbar ist.

### v2.2.36 — Wiki-Audit (`WIKI_AUDIT_v2.2.36.md`)

Abgleich der Benutzerhilfe mit dem implementierten Funktionsinventar, ergänzt um
eine grafische Erklärung der Zusammenhänge.

### v2.2.51 — Handbuch-Vollständigkeitsaudit (`HANDBOOK_COMPLETENESS_AUDIT_v2.2.51.md`)

10 von 10 Prüfbereichen bestanden. Der Audit läuft seither fortlaufend als
`tools/handbook_completeness_audit.py` und braucht daher keinen versionierten
Einzelbericht mehr.
