# BudgetManager v2.2.52 – Startup Scope Hotfix Audit

**Audit-Datum:** 2. August 2026  
**Release-Typ:** Kritischer Start-Hotfix  
**Entscheidung Source-Release:** **GO**  
**Öffentliche Installer/Binaries:** **CONDITIONAL GO** nach realem Fedora- und Windows-GUI-Smoke-Test

## 1. Behobener Release-Blocker

Beim Import von `views/tabs/cockpit_tab.py` brach BudgetManager vor dem Aufbau des Hauptfensters ab:

```text
NameError: name 'LEFT_COLUMN_PANELS' is not defined
```

### Ursache

`DEFAULT_PANEL_COLUMNS` wurde durch eine Dictionary-Comprehension innerhalb des Klassenkörpers von `CockpitTab` erzeugt. Python führt Comprehensions in Klassenkörpern in einem eigenen Scope aus. Dadurch war das unmittelbar zuvor definierte Klassenattribut `LEFT_COLUMN_PANELS` innerhalb der Comprehension nicht sichtbar.

### Korrektur

Die unveränderlichen Cockpit-Layoutvorgaben werden nun auf Modulebene erzeugt:

- `_COCKPIT_LEFT_COLUMN_PANELS`
- `_COCKPIT_DEFAULT_PANEL_COLUMNS`

`CockpitTab` übernimmt daraus nur noch sichere Klassenkopien. Damit existiert beim Klassenaufbau kein Zugriff mehr aus einer Klassen-Comprehension auf vorherige Klassenattribute.

## 2. Regressionstest

Neu: `tests/test_release_2252_cockpit_scope_startup.py`

Der Test analysiert den Klassenkörper per AST und blockiert künftig Klassen-Comprehensions, die vorher definierte Klassenattribute unqualifiziert lesen. Damit wird genau die Ursache dieses Startabbruchs dauerhaft abgesichert.

## 3. Prüfergebnisse

| Prüfung | Ergebnis |
|---|---:|
| Gesamte Pytest-Suite | **768 bestanden, 13 übersprungen, 0 fehlgeschlagen** |
| Finale Release-Audit-Matrix | **1'000 Schleifen / 19'335 Checks / 0 Warnungen / 0 Fehler** |
| Release-Logik-Audit | **100 Schleifen / 0 Findings** |
| Cockpit-/Dashboard-Regressionsblock | **68 bestanden** |
| Release-/Versions-Regressionsblock | **93 bestanden** |
| DAU-Erststartprüfung | **PASS** |
| Übersetzungs-Audit DE/EN/FR | **PASS** |
| Versionssynchronisierung | **PASS – 2.2.52** |
| Bytecode-/Syntaxprüfung | **PASS** |
| Release-Lint und Sicherheitslint | **PASS** |

## 4. Releasebewertung

### Source-Paket

**GO.** Der gemeldete Importabbruch ist ursächlich behoben, die Version ist auf `2.2.52` angehoben und alle lokalen Release-Gates sind grün.

### Installer und öffentliche Binärpakete

**CONDITIONAL GO.** In der Audit-Umgebung stand PySide6 nicht als installierbares Paket zur Verfügung. Deshalb konnte dort kein echtes Fenster unter Fedora/Wayland beziehungsweise Windows geöffnet werden. Vor Veröffentlichung der Binärpakete bleiben diese zwei kurzen Zielsystem-Smoke-Tests Pflicht:

1. Fedora: `./run.sh`, Benutzer anlegen/anmelden und Cockpit vollständig anzeigen.
2. Windows: Installer sowie Portable-Paket starten und Cockpit vollständig anzeigen.

## 5. Erwartetes Verhalten beim erneuten Start

Nach `./run.sh` darf der bisherige Traceback nicht mehr erscheinen. Nach der Datenbankmigration soll das Hauptfenster mit dem Cockpit geladen werden.
