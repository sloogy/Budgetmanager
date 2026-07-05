# BudgetManager v2.1.7 – Vergleich, Integration und Erweiterung

Datum: 2. Juli 2026

## Verglichene Pakete

- `BudgetManager Source 2 1 5 RELEASE.zip`
- `BudgetManager_Source_2_1_6_LEARNING_FINAL.zip`

## Bewertung der beiden Versionen

### 2.1.6 – bessere Basis

2.1.6 ist die bessere technische Basis, weil die neue Lernlogik sauberer getrennt und zentralisiert ist:

- eigenes Modul `model/budget_learning.py`
- klare Budgetarten statt verstreuter Heuristik
- `direction="initial"` für reine Startbudget-Vorschläge
- bessere Rundung: Einkommen vorsichtig runter, Ausgaben/Ersparnisse hoch
- Jahreswechsel-Prüfliste bindet Tracking-only-Kategorien als Startbudgets ein
- Erststart und Einstellungen enthalten Lernmodus-Optionen

### 2.1.5 – wichtige fehlende Funktionen

2.1.5 hatte wichtige Bedien- und Persistenzteile, die in 2.1.6 fehlten oder nicht vollständig übernommen waren:

- Tabelle `tracking_learning_state`
- Migration v14 → v15
- Statusaktionen: weiter beobachten, ignorieren, unregelmäßig markieren, zurücksetzen
- Kategorie-Kaskaden bei Rename/Delete
- persistentes Ausblenden statt nur Sitzungseffekt
- Jahreswechsel-Hinweistext für Lernvorschläge

## In v2.1.7 integriert

### Lernmodus-Funktion

- 2.1.6 bleibt Basis für Klassifizierung und Budgetarten.
- 2.1.5-Statusverwaltung wurde wieder integriert.
- Neue Migration `CURRENT_VERSION = 15` legt `tracking_learning_state` an.
- `BudgetOverviewModel` unterstützt wieder:
  - `show_in_report`
  - `auto_end`
  - `set_learning_action()`
  - `get_year_end_learning_suggestions()`
- Kompatibilität: `BudgetSuggestion.learning_kind` bleibt als Alias auf `budget_kind` erhalten.

### Vorschlagsdialog

- Lernvorschläge können per Rechtsklick gesteuert werden:
  - Weiter beobachten
  - Als unregelmäßig / Rückstellung markieren
  - Ignorieren
  - Lernstatus zurücksetzen
- „Weiter beobachten“ und „Ignorieren“ im Übernahme-Dialog speichern den Status jetzt dauerhaft.
- Budgetart-Bestätigung aus 2.1.6 bleibt erhalten.

### Einstellungen

- Automatisches Ausblenden nach langer stabiler Lernphase ist jetzt wirklich eine optionale Einstellung.
- Standard: aus.
- Die Kernregel bleibt immer aktiv: Sobald im Jahr ein positives Budget existiert, endet der Lernmodus für diese Kategorie automatisch.

### Jahreswechsel

- Tracking-only-Kategorien erscheinen weiterhin als Startbudgets in der Kopier-Prüfliste.
- Zusätzlich erscheint ein erklärender Hinweis, welche Kategorien aus dem Lernmodus erkannt wurden.

### Anleitung / Wiki

Erweitert wurden:

- `README.md`
- `FEATURES.md`
- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`
- `docs/help/README.md`
- `docs/help/index.html`
- `VERSION_INFO.txt`

Neu dokumentiert:

- Entscheidungspfad Lernmodus
- Budgetarten und Beispiele
- Rechtsklick-Aktionen im Vorschlagsbericht
- Jahreswechsel mit Tracking-only-Kategorien
- Best Practice für schwankendes Einkommen, Franchise, Selbstbehalt und Rückstellungen

## Neue Regression

Neue Datei:

- `tests/test_tracking_learning_integrated_v217.py`

Abgedeckt:

- Migration und Tabellenstruktur
- Kategorie-Kaskaden
- Weiter beobachten / Snooze
- Ignorieren
- Als unregelmäßig markieren
- Zurücksetzen
- optionales Auto-Ende
- Berichtsschalter

## Prüfungen

Ausgeführt und bestanden:

```bash
python -m compileall -q .
python -m pytest -q
python tools/sync_version.py --check
python tools/i18n_audit.py
```

Ergebnis:

- `273 passed, 2 skipped`
- Versionsdateien synchron auf `2.1.7`
- i18n: referenzierte Keys vorhanden, keine verdächtigen hardcoded UI-Strings

## Release-Einschätzung

v2.1.7 ist die bessere zusammengeführte Version aus 2.1.5 und 2.1.6. Sie behält die saubere zentrale Lernlogik von 2.1.6 und ergänzt die fehlende Persistenz-/Bedienlogik aus 2.1.5. Die Anleitung und das Wiki sind auf die neue Nutzerführung erweitert.
