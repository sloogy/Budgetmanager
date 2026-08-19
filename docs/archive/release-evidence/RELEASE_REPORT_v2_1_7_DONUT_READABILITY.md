# Release-Bericht – v2.1.7 RC Donut Readable

## Anlass

In der vorherigen Lesbarkeits-Version wurden die Übersichtsgrafiken zu stark umgebaut. Der Plan/Ist-Donut war gewünscht und wurde deshalb wiederhergestellt. Der danebenliegende/verwirrende Kreis bleibt ersetzt.

## Ergebnis

Basis: `BudgetManager_Source_2_1_7_RC_GRAPH_READABLE`

Neue Variante: `BudgetManager_Source_2_1_7_RC_DONUT_READABLE`

## Änderungen in der Übersicht

### Beibehalten / zurückgeholt

- Der Haupt-Donut im Übersicht-Reiter ist wieder aktiv.
- Der Donut zeigt weiterhin den Status je Konto:
  - äußerer Ring: Einnahmen
  - mittlerer Ring: Ausgaben
  - innerer Ring: Ersparnisse
- Jeder Ring zeigt:
  - gebucht
  - offen
  - über Budget
- Die Donut-Labels wurden erweitert, damit direkt am Segment steht, zu welchem Konto es gehört.

### Entfernt / ersetzt

- Der danebenliegende verwirrende Kreis für Einnahmen/Ausgaben/Ersparnisse bleibt entfernt.
- Dieser Vergleich wird weiterhin als Balkendiagramm dargestellt, weil Einnahmen, Ausgaben und Ersparnisse keine Anteile desselben Topfs sind.
- Kategorien bleiben als Ranking-Balken, weil lange Kategorienamen so besser lesbar sind als im Kreisdiagramm.

## Dokumentation / Wiki angepasst

Aktualisiert wurden:

- `README.md`
- `FEATURES.md`
- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`
- `docs/help/README.md`
- `docs/help/index.html`
- `views/help_content.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`

Die Anleitung beschreibt jetzt klar:

- Der Plan/Ist-Donut bleibt absichtlich erhalten.
- Der Donut ist ein Status je Konto, kein Vergleich der Konten untereinander.
- Der Konto-Vergleich daneben ist ein Balkendiagramm, weil das fachlich ehrlicher ist.

## Tests / Validierung

Ausgeführt:

```bash
python -m compileall -q .
python tools/sync_version.py --check
python tools/i18n_audit.py --lang de --lang en --lang fr
python -m pytest -q tests/test_overview_charts.py tests/test_release_217_blocker_fixes_static.py
python -m pytest -q
```

Ergebnis:

```text
Alle Versionsdateien synchron: 2.1.7
i18n: de/en/fr vollständig
Keine verdächtigen hardcoded UI-Strings
279 passed, 2 skipped
```

## Release-Einschätzung

Diese Version ist gegenüber `RC_GRAPH_READABLE` näher an deinem Wunsch:

- guter Donut bleibt
- verwirrender Nebenkreis weg
- Ranking/Balken dort, wo sie besser lesbar sind
- Wiki und Hilfe stimmen wieder mit dem UI-Konzept überein

Einschränkung: Ein echter PySide6-GUI-Start wurde in der Sandbox nicht ausgeführt, da die Umgebung dafür nicht vorbereitet ist. Statische Prüfung, i18n und Tests sind erfolgreich.
