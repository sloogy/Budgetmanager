# BudgetManager v2.2.54 – Cockpit QtCharts Lifetime Hotfix Audit

**Datum:** 2. August 2026  
**Status:** Zielsystem-Test erforderlich  
**Schweregrad des behobenen Fehlers:** Kritischer nativer Segmentation Fault

## 1. Ausgangslage

Nach dem Abschluss des Setup-Assistenten beziehungsweise nach dem Hinzufügen von Buchungen stürzte die Anwendung ohne Python-Ausnahme mit `Segmentation fault (core dumped)` ab.

Der bereitgestellte native C-Stack zeigt den Absturz in:

```text
libQt6Charts.so.6
AreaChartItem::fixEdgeSeriesDomain(LineChartItem*)
ChartPresenter::updateGeometry(...)
QGraphicsLayout::activate()
```

Der Python-Thread befand sich regulär in `QApplication.exec()`. Datenbank und Auto-Backup waren zuvor erfolgreich abgeschlossen. Damit liegt kein Datenbank-, Backup- oder Python-Exception-Fehler vor, sondern ein ungültiger QtCharts-Objektzeiger während eines späteren Layout-/Paint-Ereignisses.

## 2. Technische Ursache

`TrendAreaChart.set_data()` erzeugte bei jedem Cockpit-Refresh eine lokale `QLineSeries`, übergab sie als obere Begrenzung an `QAreaSeries` und verliess danach die Methode.

Qt dokumentiert, dass `QAreaSeries` die obere und untere Linienserie **nicht besitzt**. Ohne dauerhafte Python-Referenz konnte PySide die `QLineSeries` freigeben, während die native `QAreaSeries` intern weiter darauf zeigte. Beim nächsten Layout-/Geometrie-Update griff `AreaChartItem::fixEdgeSeriesDomain()` auf den ungültigen Zeiger zu.

Zusätzlich erhöhte der bisherige komplette Neuaufbau über `removeAllSeries()` und `createDefaultAxes()` während häufiger Cockpit-Refreshes das Risiko nativer Zwischenzustände.

## 3. Umsetzung in v2.2.54

- `QLineSeries`, `QAreaSeries`, X-Achse und Y-Achse werden genau einmal im Konstruktor erzeugt.
- Die obere Linie wird dauerhaft als `self._upper_series` gehalten und zusätzlich an das Widget geparentet.
- Neue Buchungsdaten werden atomar über `self._upper_series.replace(points)` eingespielt.
- Im Verlauf werden keine Serien oder Achsen mehr entfernt beziehungsweise neu erzeugt.
- Leere Daten schalten die vorhandene Serie nur unsichtbar und setzen sichere Achsenbereiche.
- Farben und Verlauf bleiben weiterhin vollständig vom DesignManager gesteuert.
- Notstartschalter:

```bash
BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh
```

Dieser deaktiviert ausschliesslich Ring- und Verlaufsdiagramm des Cockpits. Buchungen, Budget, Kategorien, Übersicht, Backups und Datenbank bleiben aktiv.

## 4. Regressionstests

Neue Gates prüfen:

1. dauerhafte Python-Referenz auf die obere `QLineSeries`,
2. dauerhafte Referenzen auf `QAreaSeries` und beide Achsen,
3. ausschliessliche In-place-Aktualisierung über `replace(points)`,
4. kein `removeAllSeries()` im Verlaufsrefresh,
5. kein `createDefaultAxes()` im Verlaufsrefresh,
6. kein erneutes Erzeugen von `QAreaSeries`/`QLineSeries` in `set_data()`,
7. den Notstartschalter `BM_DISABLE_COCKPIT_CHARTS`.

## 5. Prüfergebnisse

| Gate | Ergebnis |
|---|---:|
| Gesamte Pytest-Suite, in vier Gruppen | **776 bestanden, 13 übersprungen, 0 fehlgeschlagen** |
| Cockpit-/Dashboard-Zieltests | **49 bestanden** |
| Neue v2.2.54-Regressionstests | **5 bestanden** |
| Final Release Audit | **1’000 Loops / 19’335 Checks / 0 Warnungen / 0 Fehler** |
| Release-Logik-Audit | **100 Loops / 0 Findings** |
| Python-Bytecode/Syntax | **PASS** |
| i18n-Audit DE/EN/FR | **PASS** |
| DAU-Erststart headless | **PASS** |
| Versions- und Dokumentationssynchronisierung | **PASS – 2.2.54** |

Die 13 übersprungenen Tests benötigen optionale GUI-/Systemabhängigkeiten. PySide6 6.10.3 war in der isolierten Paketprüfumgebung nicht installierbar, deshalb konnte der echte native QtCharts-Stresstest dort nicht ausgeführt werden.

## 6. Releasebewertung

**Code- und Headless-Gates: grün.**  
**Nativer Fedora-/PySide6-Zieltest: noch erforderlich.**

Der Fix entspricht exakt der im Crash-Stack sichtbaren Fehlerklasse und beseitigt die objektlebenszeitbedingte Dangling-Pointer-Ursache. Da ein Segfault ausserhalb des Python-Interpreters lag, wird v2.2.54 bis zum erfolgreichen Buchungs-Stresstest auf Fedora bewusst als Zieltest-Hotfix und nicht als uneingeschränkt bestätigter Final-Release bezeichnet.

## 7. Empfohlener Zieltest

1. v2.2.54 in einen neuen Ordner entpacken.
2. Alten `data`-Ordner zunächst nicht löschen.
3. Normal mit `./run.sh` starten.
4. Cockpit öffnen.
5. Mindestens zehn Buchungen nacheinander hinzufügen, darunter mehrere am selben und an unterschiedlichen Tagen.
6. Nach jeder Buchung zum Cockpit zurückkehren oder den Cockpit-Refresh auslösen.
7. Fenster mehrfach vergrössern/verkleinern und zwischen Tabs wechseln.
8. Anwendung schliessen und erneut starten.
9. Falls erneut ein nativer Absturz auftritt, einmal mit `BM_DISABLE_COCKPIT_CHARTS=1 ./run.sh` starten und die neuen Logs sichern.
