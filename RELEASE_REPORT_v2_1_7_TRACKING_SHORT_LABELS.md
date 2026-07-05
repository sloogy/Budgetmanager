# Release-Bericht v2.1.7 – Tracking-Kategorieauswahl kurz

## Anlass

Für den Release 2.1.7 soll die tägliche Tracking-Erfassung schneller und weniger überladen sein. Parent-Kategorien sollen im Tracking nicht als eigene Buchungszeile vor Unterkategorien erscheinen. Unterkategorien sollen kurz angezeigt werden.

## Umsetzung

- `CategoryModel.list_for_tracking_dropdown_grouped()` blendet Parent-Kategorien mit mindestens einer Unterkategorie im Tracking-Picker aus.
- Unterkategorien werden im Tracking kurz angezeigt:
  - vorher: `Wohnen › Miete` oder `Wohnen - Miete`
  - jetzt: `Miete`
- Gespeichert wird weiterhin der echte Kategoriename aus der Datenbank, z. B. `Miete`.
- Root-Kategorien ohne Unterkategorien bleiben weiterhin buchbar, z. B. `Lebensmittel`.
- Favoriten, manuelle Nutzungshäufigkeit und Fix-/Wiederkehrend-Gruppen bleiben erhalten.

## Betroffene Bereiche

- Tracking-Dialog `views/tracker_dialog.py` über den gruppierten Picker
- Schnelleingabe `views/quick_add_dialog.py` über denselben Picker
- Fallback-Liste `list_for_tracking_dropdown()`
- Gemeinsamer Resolver `views/category_picker.py` bleibt rückwärtskompatibel mit alten Pfadlabels
- README, FEATURES, User-Guides und Wiki/Hilfe wurden angepasst

## Nicht geändert

- Kategorien-Manager zeigt Parent-Kategorien weiterhin.
- Budget-Tab zeigt Parent-Kategorien weiterhin als Struktur-/Summenzeilen.
- Import/Export darf weiterhin Pfadlabels wie `Wohnen › Miete` verwenden.
- Bestehende alte Buchungen auf Parent-Kategorien werden nicht gelöscht oder automatisch umgehängt.

## Neue Regression

`tests/test_picker_and_budget_reached.py::test_tracking_picker_shows_child_names_without_parent_prefix`

Geprüft wird:

- Parent `Wohnen` erscheint im Tracking nicht als buchbare Auswahl.
- Children `Miete` und `Internet` erscheinen weiterhin.
- Labels enthalten keine Parent-Pfade wie `Wohnen › Miete` oder `Wohnen - Miete`.
- Root-Kategorie `Lebensmittel` bleibt buchbar.

## Validierung

```bash
python -m compileall -q .
python tools/sync_version.py --check
python tools/i18n_audit.py --lang de --lang en --lang fr
python -m pytest -q
```

Ergebnis:

```text
Alle Versionsdateien synchron: 2.1.7
Keine verdächtigen hardcoded UI-Strings
280 passed, 2 skipped
```

## Bewertung

Release-tauglich für 2.1.7. Die Änderung ist klein, zielgenau und verbessert die tägliche Erfassung, ohne die größere Usability-Schiene für 2.2.0 vorwegzunehmen.
