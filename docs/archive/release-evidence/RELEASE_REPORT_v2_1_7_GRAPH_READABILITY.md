# Release-Bericht – v2.1.7 RC Graph Readability

Datum: 2026-07-02
Basis: `BudgetManager_Source_2_1_7_RC_WIKI_FIXED`
Ziel: Übersicht-Reiter verständlicher und schneller lesbar machen.

## Problem

Die bisherigen Diagramme in der Übersicht waren schwer zu verstehen, weil mehrere Werte als Kreis-/Donutdiagramme dargestellt wurden, obwohl sie fachlich keine echten Anteile desselben Ganzen sind. Besonders Einnahmen, Ausgaben und Ersparnisse dürfen nicht als einfacher Kuchen interpretiert werden: Einkommen ist der Topf, Ausgaben und Ersparnisse gehen daraus weg.

## Umsetzung

### Übersicht / Plan-Ist

- Der verschachtelte Donut wurde durch einen klaren Balkenvergleich ersetzt.
- Pro Konto stehen jetzt `Budget` und `Gebucht` nebeneinander.
- Das beantwortet direkt: Wo bin ich über oder unter Plan?

### Kategorien

- Ausgaben-Kategorien werden nicht mehr als großer Kreis dargestellt.
- Neu: horizontales Kategorien-Ranking.
- Die größten 8 Kategorien werden einzeln gezeigt.
- Kleinere Restkategorien werden als `Übrige` zusammengefasst.
- Vorteil: lange Kategorienamen und Beträge sind deutlich besser lesbar.

### Konto-Vergleich

- Einnahmen, Ausgaben und Ersparnisse werden nicht mehr als Verteilung/Kreis gezeigt.
- Neu: horizontaler Balkenvergleich nach Konto.
- Begründung: Diese Werte sind keine Anteile desselben Topfs.

### Monatsverlauf / Monatsbilanz

- Liniengraphen bleiben erhalten, weil sie für Trends über Monate logisch sind.
- Achsen wurden mit Betrag/Monat verständlicher beschriftet.
- Direkt über den Graphen steht nun eine kurze Erklärung.

### Top-Buchungen

- Top-Buchungen werden als horizontale Balken angezeigt.
- Wiederholte Buchungen gleicher Kategorie bleiben aggregiert.
- Dadurch werden große Ausreißer schneller sichtbar.

## Geänderte Dateien

- `views/tabs/overview_kpi_panel.py`
- `views/tabs/overview_widgets.py`
- `model/overview_aggregation.py`
- `tests/test_overview_charts.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`
- `README.md`
- `FEATURES.md`
- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`
- `docs/help/README.md`
- `docs/help/index.html`
- `views/help_content.py`
- `CHANGELOG.md`
- `VERSION_INFO.txt`

## Neue/angepasste Tests

- `test_aggregate_category_amounts_limits_and_groups_other`
- `test_overview_uses_bars_instead_of_misleading_pies_for_account_and_categories`

## Validierung

Ausgeführt:

```bash
python -m compileall -q .
python tools/sync_version.py --check
python tools/i18n_audit.py --lang de --lang en --lang fr
python -m pytest -q
```

Ergebnis:

```text
Alle Versionsdateien synchron: 2.1.7
i18n: de/en/fr vollständig, keine verdächtigen hardcoded UI-Strings
279 passed, 2 skipped
```

## Einschränkung

Ein echter PySide6-GUI-Start konnte in dieser Sandbox nicht durchgeführt werden, weil PySide6 hier nicht installiert ist. Die Änderungen sind statisch, per Compile, i18n-Audit und Regressionstests geprüft. Der reale GUI-Smoke sollte lokal nach `pip install -r requirements.txt` erfolgen.
