# Enterprise UI-/Usability-/ADHS-Audit – BudgetManager v2.2.23

**Auditdatum:** 15. Juli 2026  
**Ausgangsbasis:** BudgetManager v2.2.22 UI ADHS Audit Fixed  
**Ziel:** unabhängige Gegenprüfung, Behebung konkreter UI-/Usability-Risiken und erneuter 1000er-Audit

## 1. Gesamturteil

**Automatisierte Release-Gates: GRÜN.**  
**Enterprise-UI-Freigabe: BEDINGT GRÜN / Release Candidate.**

Die korrigierte Version v2.2.23 hat keine automatisiert erkannten Release-Blocker. Zwei UX-Bereiche bleiben bewusst als Warnung offen und wurden nicht schöngerechnet:

1. hohe Zahl modaler Informationsdialoge,
2. fehlende explizite Tab-Reihenfolge in komplexen Dialogen.

Für eine endgültige Enterprise-Freigabe sind deshalb noch reale Tastatur-, Skalierungs- und Screenreader-Tests auf Fedora/Wayland und Windows notwendig.

## 2. GitHub-Abgleich

Das verbundene Repository ist `sloogy/Budgetmanager`, Standardbranch `main`. Der sichtbare Hauptbranch liegt gegenüber dem Upload zurück und enthält als jüngsten ermittelten Stand noch v2.2.6-nahe Commits. Daher wurde der hochgeladene Quellstand v2.2.22 als maßgebliche Audit-Basis verwendet.

Es wurde **nichts ungefragt auf GitHub veröffentlicht, gepusht oder gemergt**.

## 3. Kritische Gegenfunde in v2.2.22

Der mitgelieferte Auditbericht meldete keine Findings. Die unabhängige Gegenprüfung fand dennoch reale Schwachstellen:

### Release-Sauberkeit

- Die vollständige Qt-Testsuite erzeugte `data/budgetmanager_settings.json` im Projektbaum.
- `tools/clean_release_tree.py` entfernte diese Datei entgegen der eigenen Release-Regel nicht.
- Folge: 3 fehlgeschlagene Release-Sauberkeitstests nach einem vollständigen Testlauf.
- Das ursprüngliche ZIP enthielt die Datei nicht; das Risiko entstand durch einen unvollständigen Bereinigungsprozess vor einem möglichen späteren Packvorgang.

### Fokus und Fehlerprävention

- Vorbefüllte Eingabefelder wurden beim Fokus komplett markiert.
- Ein versehentlicher Tastendruck konnte dadurch den gesamten bestehenden Inhalt ersetzen.
- Icon-only-Löschaktionen wurden bei der Enter-Schutzlogik nicht zuverlässig als destruktiv erkannt.

### Accessibility und Sprache

- Formularbeschriftungen aus `QFormLayout` wurden nicht zuverlässig als verständliche Accessible Names übernommen.
- Automatisch erzeugte Accessibility-Texte konnten nach einem Sprachwechsel in der alten Sprache verbleiben.
- Der bisherige Live-Sprachwechsel übersetzte nur Teile des Hauptfensters und konnte eine gemischtsprachige Oberfläche erzeugen.

### Farben und Kontrast

- In den 25 mitgelieferten Designs bestanden Kontrastverletzungen, insbesondere bei Auswahlflächen, Schaltflächen, Tabs, Menüs, Gruppentiteln und Tabellenköpfen.
- Schlechtester gemessener Kontrast vor der Korrektur: **1,21:1**.
- Zielwert für normalen Text: mindestens **4,5:1** nach WCAG AA.

### Bedienziele und Layout

- Ein Icon-Farbbutton im Tag-Manager war mit 30 × 24 px zu klein.
- Im Theme-Editor wurde dasselbe Scroll-Widget doppelt in das Layout eingefügt.

### CI-/Format-Gate

- 21 Model-Dateien entsprachen nicht dem festgelegten Black-Format.
- Das war kein Funktionsfehler, hätte aber das CI-Release-Gate blockiert.

## 4. Umgesetzte Korrekturen in v2.2.23

### Release-Härtung

- Release-Cleaner entfernt nun Settings-, Datenbank-, Backup-, Log-, Cache-, Build- und Laufzeit-Theme-Artefakte zuverlässig.
- Regressionstest verhindert erneut verunreinigte Release-ZIPs.

### ADHS-freundliche Eingaben

- Vorbefüllte Textfelder werden beim Fokussieren nicht mehr vollständig markiert.
- Der Cursor wird stattdessen ans Ende gesetzt.
- Das reduziert unbeabsichtigtes Überschreiben und kognitive Wiederholungsarbeit.

### Destruktive Aktionen

- Erkennung berücksichtigt nun Text, Tooltip, Accessible Name und What’s This.
- Icon-only-Löschaktionen erhalten keinen gefährlichen Standard-/Enter-Status.

### Accessibility

- Zugeordnete Formularlabels werden als verständliche Accessible Names genutzt.
- Automatisch erzeugte Accessibility-Texte sind erkennbar und können erneuert werden.
- `LanguageChange` löst eine erneute Accessibility-Härtung aus.
- `QDateTimeEdit` wird in die zentrale UI-Härtung einbezogen.

### Sprachkonsistenz

- Sprachwechsel wird vollständig gespeichert und nach Neustart konsistent angewendet.
- Dadurch entsteht keine halb übersetzte Oberfläche mehr.
- Neue Neustart-Hinweise wurden in Deutsch, Englisch und Französisch ergänzt.

### Theme-Kontrast

- Alle 25 Standarddesigns wurden auf mindestens WCAG-AA-Kontrast für die relevanten Text-/Flächenpaare gehärtet.
- Neue getrennte Vordergrundfarben für Akzentflächen, Akzent-Panels und Tabellenköpfe.
- Theme-Editor unterstützt diese Farben direkt.
- 47 problematische Vordergrundwerte wurden mit möglichst geringer visueller Abweichung korrigiert.

### Bedienflächen

- Icon-Farbbutton im Tag-Manager auf 36 × 32 px vergrößert.
- Doppelte Scroll-Widget-Einfügung im Theme-Editor entfernt.

### Dokumentation und Versionierung

- Versionsstand auf **2.2.23** und Datum **15. Juli 2026** synchronisiert.
- Aktive README-, Handbuch-, Hilfe-, Installer-, Updater- und Release-Dokumente aktualisiert.
- Historische Changelog-Angaben wurden nicht umgeschrieben.

### Tests

- 8 neue Regressionstests für Release-Sauberkeit, Fokus, Accessibility, destruktive Icon-Aktionen, Sprachkonsistenz, Zielgrößen und Theme-Kontrast.
- 21 Model-Dateien ausschließlich mit Black formatiert.

## 5. Ergebnisse der Abschlussprüfung

| Prüfung | Ergebnis |
|---|---:|
| Vollständige Qt-Offscreen-Testsuite | **491 bestanden, 0 fehlgeschlagen** |
| Neuer Enterprise UI/ADHS Audit | **1000 Loops, 4300 Checks, 0 FAIL** |
| Davon PASS / WARN | **800 PASS / 200 WARN** |
| Bestehender UI/ADHS Audit | **1000 Loops, 15.623 Checks, 0 Findings** |
| Mega Release Audit | **1000 Loops, 6812 Checks, 0 Findings** |
| Deep Logic Audit | **500 Loops, 3500 Checks, 0 Findings** |
| Stability Audit | **300 Loops, 2400 Checks, 0 Findings** |
| Release Logic Audit | **100 Loops, 0 Findings** |
| Fresh Logic Audit | **100 Loops, 0 Findings** |
| Black Model | **40 Dateien sauber** |
| Mypy Model | **0 Fehler in 40 Dateien** |
| Versionssynchronisierung | **PASS – 2.2.23** |
| Lint-/Release-Prozedur | **PASS** |
| I18N-Audit | **PASS** |
| Headless DAU-Erststart | **alle Checks bestanden** |

## 6. Offene Warnbereiche

### WARN 1 – Modale Unterbrechungen

- Quellscan: **419 `QMessageBox`-Aufrufe**, davon **107 Informationsdialoge**.
- Nicht jeder Aufruf ist problematisch, aber Erfolgsmeldungen und reine Hinweise unterbrechen häufig den Arbeitsfluss.
- ADHS-Risiko: Kontextverlust, Klickmüdigkeit und verlangsamte Massenerfassung.

**Empfohlene nächste Stufe:** nichtkritische Bestätigungen schrittweise durch Statusleiste, Toast oder Inline-Rückmeldung ersetzen. Fehler, Sicherheitswarnungen und irreversible Bestätigungen bleiben modal.

### WARN 2 – Tastaturreihenfolge

- **13 komplexe Dialogdateien** besitzen keine explizite `setTabOrder`-Definition.
- Qt nutzt dadurch die Erstellungsreihenfolge, die nicht zwingend dem visuellen Arbeitsablauf entspricht.

**Empfohlene nächste Stufe:** reale Tastaturprüfung je Dialog und anschließend explizite Tab-Ketten für die wichtigsten Erfassungs- und Verwaltungsdialoge.

## 7. Release-Empfehlung

v2.2.23 ist als **technisch sauberer Release Candidate** geeignet. Die Version behebt konkrete Schwächen, die der ursprüngliche 1000er-Audit nicht erkannt hatte.

Vor einem öffentlichen finalen Release sollten noch folgende manuelle Abnahmen erfolgen:

1. Fedora/Wayland bei 100 %, 125 %, 150 % und 200 % Skalierung,
2. Windows bei 100 %, 125 % und 150 % Skalierung,
3. vollständige Tastaturbedienung der 13 komplexen Dialoge,
4. Screenreader-Stichprobe in Deutsch, Englisch und Französisch,
5. visueller Smoke-Test aller 25 Designs.

**Freigabestatus:** `RC – automatisierte Release-Gates grün, manuelle Enterprise-UI-Abnahme offen`.
