# Budget-Warnungen Crashfix v2.0.8

## Problem
Beim Öffnen von `Budget prüfen` konnte der Dialog abstürzen:

```text
ValueError: max() iterable argument is empty
```

Auslöser war ein Sonderfall im Budgetanpassungsdialog:

- Es lagen Vorschläge aus der Verlaufsauswertung vor.
- Gleichzeitig gab es im aktuellen Monat keine echten aktuellen Überschreitungen.
- Dadurch war `exceedances` leer.
- Die Empfehlungserzeugung rief trotzdem `max(exceedances, ...)` auf.

## Fix
`views/budget_adjustment_dialog.py` wurde abgesichert:

- `max()` läuft jetzt nur noch auf vorhandenen aktuellen Überschreitungen.
- Bei reinen Verlaufsvorschlägen wird kein Crash mehr ausgelöst.
- Der Dialog bleibt geöffnet und zeigt die vorhandenen Vorschläge normal an.

## Regressionstest
Neu:

- `tests/test_budget_adjustment_dialog_regression.py`

Der Test stellt sicher, dass der alte ungeschützte `max(exceedances)`-Pfad nicht wieder eingebaut wird.

## Checks

```text
compileall                         OK
sync_version --check               OK, 2.0.8 synchron
i18n_audit                         OK
DAU first-run check                 OK
pytest                              40 passed, 1 skipped
```
