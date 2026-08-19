# Release Audit Fix Report – v2.2.2 Recurring-Day Default Fix

## Ergebnis

Status: **releasefähig nach Fix**

Die Version wurde auf Releasefähigkeit geprüft. Der gemeldete Fehler mit dem bevorzugten Fälligkeitstag wurde bestätigt und behoben.

## Kritischer gefundener Fehler

### Fälligkeitstag bei neuer/wiederkehrender Kategorie fiel auf 1 zurück

**Problem:**
Wenn in den Einstellungen ein bevorzugter Buchungstag/Fälligkeitstag gesetzt war, z. B. 25, wurde dieser Wert nicht auf allen Kategorie-Pfaden übernommen.

Betroffene Pfade:

- neue Kategorie im Budget-Erfassungsdialog
- neue Kategorie im erweiterten Budget-Erfassungsdialog
- Kategorie-Eigenschaften: Kategorie auf wiederkehrend setzen
- Kategorien-Tab: Massenbearbeitung/Fälligkeitstag
- Budget-Tab: Wiederkehrend direkt umschalten
- Datenmodell-Pfad `CategoryModel.create(...)` ohne expliziten Tag
- Datenmodell-Pfad `CategoryModel.update_flags(..., is_recurring=True)` beim Umschalten von nicht-wiederkehrend auf wiederkehrend

**Ursache:**
Mehrere UI- und Model-Pfade hatten den technischen Datenbank-Default `1` als Fälligkeitstag. Dadurch wurde die Einstellung `recurring_preferred_day` nicht zuverlässig respektiert.

## Umsetzung

### Zentraler Fix im Datenmodell

In `model/category_model.py` ergänzt:

- `CategoryModel.preferred_recurring_day()`
- zentrale Normalisierung für Fälligkeitstage
- `create(...)` nutzt den bevorzugten Tag, wenn eine Kategorie wiederkehrend erstellt wird und kein expliziter Tag gesetzt wurde
- `upsert(...)` nutzt denselben Standard
- `update_flags(...)` setzt beim Wechsel von nicht-wiederkehrend auf wiederkehrend automatisch den bevorzugten Tag
- bereits wiederkehrende Kategorien behalten ihren explizit gesetzten Tag

### UI-Fixes

Geändert:

- `views/budget_entry_dialog.py`
- `views/budget_entry_dialog_extended.py`
- `views/category_properties_dialog.py`
- `views/tabs/budget_tab.py`
- `views/tabs/categories_tab.py`

Neue Kategorie-Dialoge und Umschaltpfade zeigen/verwenden jetzt den bevorzugten Tag aus den Einstellungen statt hart `1`.

## Regressionsschutz

Neue Tests:

- `tests/test_recurring_preferred_day_defaults.py`

Abgedeckt:

1. Neue wiederkehrende Kategorie ohne expliziten Tag bekommt den eingestellten Standardtag.
2. Bestehende Kategorie, die auf wiederkehrend gesetzt wird, bekommt den eingestellten Standardtag.
3. Bereits wiederkehrende Kategorie mit explizitem Tag 1 behält diesen Tag beim erneuten Speichern.
4. Relevante UI-Pfade verwenden den zentralen Standardtag statt hartem `1`.

## Prüfläufe

- Versions-Sync: **PASS**
- Python Compile: **PASS**
- Pytest: **311 passed, 2 skipped**
- i18n Audit: **PASS**
- Release-Logik-Audit: **100 Loops, 0 Findings**
- Deep-Logic-Audit: **500 Loops / 3500 Checks, 0 Findings**
- Lint-/Release-Prozedur: **PASS**
- DAU-Erststartcheck: **PASS**

Hinweis: Die zwei übersprungenen Tests sind GUI/Startup-Smoke-Tests, weil in der Prüf-Umgebung kein PySide6 installiert ist. Die Logik- und Release-Gates sind grün.

## Release-Einschätzung

Die Version ist nach dem Fix als **v2.2.2 Recurring-Day Default Fix** releasefähig.

