# Fix: Kategorien-Dropdown & Typ-Balken – v2.0.8

## Ausgangslage

Im Schnelleingabe-/Buchungsdialog war die Kategorieauswahl nicht praxisnah genug:

- Kategorien wurden primär strukturell/alphabetisch angezeigt.
- Häufig genutzte manuelle Kategorien waren nicht automatisch oben.
- Automatisch erzeugte Fixkosten-/Wiederkehrend-Buchungen konnten das Ranking verfälschen.
- Favoriten standen nicht konsequent an erster Stelle.

Zusätzlich waren die Budget-vs.-Ist-Balken für Einkommen/Ausgaben/Ersparnisse weiterhin als Ampel gefärbt. Für diese Typ-Balken ist das verwirrend, weil hier die Kontofarbe/Typfarbe erwartet wird.

## Umsetzung

### 1. Tracking-Quelle eingeführt

Die Datenbankmigration wurde auf Schema-Version 12 erweitert.

Neue Spalte:

```sql
tracking.source TEXT NOT NULL DEFAULT 'manual'
```

Genutzte Werte:

- `manual` – vom Nutzer erfasst oder normal bearbeitet
- `auto_fixcost` – über Fixkosten buchen erzeugt
- `auto_recurring` – über wiederkehrende Buchungsliste erzeugt

Alte Datenbanken bleiben kompatibel, weil die Spalte einen Default-Wert hat.

### 2. Automatische Buchungen werden beim Kategorie-Ranking ausgeschlossen

`TrackingModel.category_usage_counts(..., manual_only=True)` zählt nur manuelle Buchungen.

Zusätzlich gibt es eine Altbestand-Heuristik:

- `source LIKE 'auto%'` wird ausgeschlossen.
- Details mit `Wiederkehrend (ID:...)` werden ausgeschlossen.
- Bei Kategorien mit Fixkosten-/Wiederkehrend-Flag werden alte Einträge im Muster `Monat - Kategorie` nicht für das Ranking gezählt.

### 3. Dropdown-Reihenfolge für Buchungsdialoge

Neue zentrale Methode:

```python
CategoryModel.list_for_tracking_dropdown(typ)
```

Reihenfolge:

1. Favoriten des gewählten Typs ganz oben, mit `★` markiert.
2. Danach Kategorien nach manueller Nutzungshäufigkeit.
3. Danach übrige Kategorien in gepflegter Kategorien-Reihenfolge.

Angewendet in:

- `views/quick_add_dialog.py`
- `views/tracker_dialog.py`

### 4. Typ-Balken nutzen Kontofarbe statt Ampel

`CompactProgressBar` unterstützt neu `typ_key`.

In der Finanzübersicht werden die drei Budget-vs.-Ist-Balken jetzt mit Typfarbe dargestellt:

- Einkommen → Farbe aus Theme für Einkommen
- Ausgaben → Farbe aus Theme für Ausgaben
- Ersparnisse → Farbe aus Theme für Ersparnisse

Die generische Ampellogik bleibt für andere Fortschrittsbalken erhalten.

## Regressionstests

Neue Tests:

- `test_tracking_source_marks_auto_bookings_and_manual_usage_counts`
- `test_tracking_dropdown_favorites_then_manual_frequency`

## Prüfung im Container

Ausgeführt:

```bash
python -m compileall -q .
python tools/sync_version.py --check
pytest -q
```

Ergebnis:

```text
49 passed, 1 skipped
Alle Versionsdateien synchron: 2.0.8
```
