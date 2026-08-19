# BudgetManager – Versionsvergleich und Merge-Bericht v2.2.27

**Verglichene Quellen**

- `BudgetManager Source 2 2 25 KILLCRITIC MERGED`
- `BudgetManager_Source_2_2_26_KILLCRITIC_X10THINK_USABILITY_10000_AUDITED`

**Ergebnis:** Ein Merge war zwingend notwendig. v2.2.26 ist UI-technisch ausgereifter, hatte aber mehrere sicherheits- und datenrelevante Korrekturen aus v2.2.25 nicht mehr enthalten. Die neue v2.2.27 verwendet deshalb v2.2.26 als UI-Basis und führt die verlorenen Kernkorrekturen aus v2.2.25 zurück.

## 1. Technischer Vergleich

| Bereich | v2.2.25 | v2.2.26 | Bewertung |
|---|---|---|---|
| UI/Usability | Gut und bereits gehärtet | Besser: Scrollbarkeit, Accessibility, lokalisierte Standardbuttons, bessere Größen und Kontraste | **v2.2.26** |
| Datenintegrität | Schema v17, Tag-Waisenbereinigung, Monatsende-Fälligkeit korrekt | Mehrere dieser Fixes fehlten wieder | **v2.2.25** |
| Sicherheit | Zusätzliche SQL-Identifier- und Whitelist-Guards | Guards teilweise entfernt | **v2.2.25** |
| Undo/Redo | Tags werden beim Löschen symmetrisch bereinigt | Tag-Waisen konnten wieder entstehen | **v2.2.25** |
| Dokumentation | Vollständige Kapitel zu Erststart, Cockpit, Tags, Konten und Monatsabschluss | Diese Kapitel waren teilweise entfernt | **v2.2.25** |
| Audit-Infrastruktur | Final-/KILLCRITIC-Audits und Regressionstests | Neuer isolierter Qt-Usability-Audit und CI-Gate | **Beide zusammenführen** |

Dateivergleich der Ausgangsstände:

- 317 Dateien waren bytegleich.
- 55 gemeinsame Dateien unterschieden sich.
- 8 Dateien existierten nur in v2.2.25.
- 3 Dateien existierten nur in v2.2.26.

## 2. Übernommene Verbesserungen aus v2.2.26

- Verschachtelte Formularfelder erhalten bessere Screenreader-Namen.
- Qt-Standardbuttons werden in Deutsch, Englisch und Französisch lokalisiert.
- Tab-Reihenfolgen berücksichtigen nur sichtbare Widgets desselben Fensters.
- Budget-Erfassungsfenster ist auf kleinen Displays scrollbar.
- Setup-Assistent ist scrollbar und notebooktauglich dimensioniert.
- Kleine Icon-Aktionen erhielten größere Bedienflächen.
- Datenbankstatistik und Hilfeinhalt erhielten Accessibility-Namen.
- Kategorie-Schnellaktionen verwenden kürzere, besser lesbare Texte mit erklärenden Tooltips.
- Versionsanzeige in der Seitenleiste besitzt besseren Kontrast.
- Nicht editierbare Kategorie-Comboboxen erzeugen keine unnötigen Completer-Warnungen mehr.
- Zusätzliches KILLCRITIC-Usability-Gate bleibt im Build-Workflow aktiv.

## 3. Wiederhergestellte Korrekturen aus v2.2.25

### Kritisch

1. **Datenbankschema v17 wiederhergestellt**  
   Die Migration bereinigt verwaiste `entry_tags` aus bestehenden Datenbanken.

2. **Fixkosten-Fälligkeit am Monatsende korrigiert**  
   Fälligkeitstage 29–31 werden auf den tatsächlichen letzten Tag des Monats begrenzt. Dadurch werden Positionen im Februar und in 30-Tage-Monaten zuverlässig fällig.

3. **Undo/Redo-Tagbereinigung wiederhergestellt**  
   Beim Löschen einer Trackingposition werden zugehörige `entry_tags` explizit entfernt, auch wenn SQLite-Fremdschlüssel nicht aktiv sind.

4. **SQL-Härtungen wiederhergestellt**  
   Identifier-/Whitelist-Prüfungen sind wieder aktiv in:
   - `model/category_model.py`
   - `model/migrations.py`
   - `model/tags_model.py`
   - `model/tracking_model.py`
   - `model/undo_redo_model.py`

### Usability und Dokumentation

- Sichtbarer Schließen-Button im Theme-Editor wiederhergestellt.
- Menütext `Backup && Wiederherstellen` wieder korrekt für Qt maskiert.
- Vollständige Benutzeranleitungen in DE/EN/FR wiederhergestellt.
- Neue v2.2.26-Übersetzungsschlüssel beibehalten; Parität nun 2319 Schlüssel je Sprache.
- Auditwerkzeuge und Regressionstests beider Zweige zusammengeführt.

## 4. Zusätzliche Merge-Korrektur

Das ältere KILLCRITIC-Werkzeug verwendete einen rohen DB-Typ-String. Es nutzt jetzt die zentralen Konstanten `TYP_EXPENSES` und `TYP_INCOME`. Dadurch besteht auch das Release-Gate gegen verstreute Datenbank-Typliterale.

## 5. Prüfergebnisse v2.2.27

| Prüfung | Ergebnis |
|---|---:|
| Python Compile-All | PASS |
| Versionssynchronisation | PASS |
| Release-/Lint-Prozedur | PASS |
| i18n-Audit DE/EN/FR | PASS – 2319 Schlüssel je Sprache |
| Vollständige PySide6-Offscreen-Testsuite | **552 bestanden, 0 fehlgeschlagen** |
| Final Release Audit | **1000 Loops, 20.895 Checks, 0 Fehler** |
| KILLCRITIC X10THINK | **10.000 Loops, 327.170 Checks, 0 Fehler** |
| Release Logic | 100 Loops, 0 Findings |
| Fresh Logic | 100 Loops, 0 Findings |
| Deep Logic | 500 Loops, 3500 Checks, 0 Findings |
| Stability Audit | 300 Loops, 2400 Checks, 0 Findings |
| Mega Release Audit | 1000 Loops, 6813 Checks, 0 Findings |
| DAU-Erststartprüfung | PASS |
| Qt-Usability Worker-Smoke | 100 Loops, 742 Checks, 0 Findings |

### Hinweis zum separaten Qt-Langzeitaudit

Der dialogbasierte Controller für 10.000 isolierte Qt-Worker überschritt das maximale Laufzeitfenster dieser Analyseumgebung. Deshalb wird kein neuer vollständiger 10.000er-Nachweis dieses speziellen Controllers behauptet. Der zugehörige Worker wurde mit 100 Loops erfolgreich geprüft, die komplette PySide6-Testsuite ist grün und der unabhängige KILLCRITIC-Fach-/Regressionsaudit lief vollständig über 10.000 Loops.

## 6. Releasebewertung

**v2.2.25 allein:** kern- und sicherheitstechnisch stärker, aber UI-technisch schwächer.  
**v2.2.26 allein:** UI-technisch klar besser, wegen zurückgenommener Kernkorrekturen nicht als alleinige Releasebasis empfohlen.  
**v2.2.27 Merge:** aktuell vollständigster und sicherster Stand.

### Empfehlung

v2.2.27 als **Release Candidate** verwenden. Vor dem öffentlichen Release sollte nur noch ein kurzer realer Sichttest auf Fedora/Wayland und Windows mit Skalierung 100 %, 125 % und 150 % erfolgen. Es bestehen keine bekannten automatisiert reproduzierbaren Funktions-, Logik- oder Datenintegritätsfehler.
