# BudgetManager v2.0.8 — Release-Ready Final Report

Stand: 14. Juni 2026

## Kurzentscheid

**Ja, der Satz macht fachlich Sinn:**

> 0 darf bei Fixkosten nie allein der Auslöser für einen Budgetvorschlag sein. Fixkosten können inkrementell/lumpy sein.

Gemeint ist: Eine Versicherung, Steuer, Jahresgebühr oder ein Abo kann monatelang 0 Buchungen haben und dann in einer oder mehreren Raten auftauchen. Diese 0-Monate sind kein Beweis dafür, dass das Budget zu hoch ist.

## Vergleich der Lösungsschritte

| Stand | Umsetzung | Bewertung |
|---|---|---|
| v2.0.7 release_ready | Releasefähige Basis: DAU-Check, Update-Dialog, Zahlenformat, i18n, Versionierung sauberer als Schwesterpaket | **Als Basis behalten** |
| v2.0.7 forecast_fix | Fixkosten/wiederkehrende Kategorien nutzen `active_only=True`; 0-Monate werden für Budgetänderung ignoriert | **Fachlich richtiger Kern** |
| v2.0.8 Upload | Version/Doku/Merge auf 2.0.8, zusätzlicher Fixkosten-Test, aber Engine schützt nur `active_months == 0` | **Teilweise gut, aber fachlich zu schwach** |
| Final v2.0.8 release_ready | v2.0.8-Basis + robuste v2.0.7-Forecast-Logik + erweiterte Tests + Doku/README auf 2.0.8 | **Release-ready im Container** |

## Wichtigster Fund

Die hochgeladene v2.0.8-Version hatte eine echte Lücke:

- Wenn eine Fixkosten-Kategorie **gar keine** Buchungen hatte, wurde sie geschützt.
- Sobald aber **ein einziger echter Buchungsmonat** vorhanden war, liefen die 0-Monate wieder in die normale Median-Analyse.
- Dadurch konnte der Fall `Versicherung Budget 200, Ist 250 / 0 / 0 / 0 ...` trotzdem wieder zu einem falschen Senkungsvorschlag führen.

## Final umgesetzte Regel

### Fixkosten / wiederkehrende Kategorien

Gilt für:

- `is_fix = 1`
- oder `is_recurring = 1`

Regel:

```text
0-Monate werden für Budgetänderungen ignoriert.
Es braucht mindestens 3 echte Buchungsmonate (> 0).
Der 0-Reduktionspfad wird übersprungen.
Wiederholte echte Überschreitung darf erhöhen.
Wiederholte echte niedrigere Buchung darf senken.
Aber nie nur wegen 0.
```

### Flexible Kategorien

Beispiel Hobby:

```text
Budget: 40 CHF
Ist:    20 / 30 / 0 / 20 / 30 / 0
```

Hier darf ein Senkungsvorschlag entstehen, weil 0 Teil des wiederholten Nutzungsmusters ist. Das bleibt bewusst flexibel.

### Ausreißer bleiben stabil

Beispiel Nahrungsmittel:

```text
Budget: 400 CHF
Ist:    450 / 350
```

Ergebnis: **kein Vorschlag**, weil sich Über- und Unterschreitung ausgleichen.

## Geänderte Kern-Dateien

- `model/budget_suggestion_engine.py`
  - `respect_fixed_costs=True`
  - fixed-like Erkennung über `is_fix` oder `is_recurring`
  - `active_only=True` für Fixkosten/wiederkehrende Kategorien
  - Mindestanforderung: mindestens 3 echte Buchungsmonate
  - Mindeständerung nach Rundung nochmals geprüft

- `tests/test_fixed_cost_suggestion.py`
  - erweitert von 4 auf 8 Regressionstests
  - deckt Versicherung 250/0/0, Hobby 20/30/0 und Nahrungsmittel 450/350 ab

- `updater/check_update.py` und `tests/test_release_integrity.py`
  - GUI-Erfolgsergebnis nach erfolgreichem Update-Staging ergänzt
  - Regressionstest verhindert, dass der Update-Dialog wieder ohne Freischaltung bleibt

- `README.md`, `README_INSTALLATION.md`, `FEATURES.md`, `docs/*`, `VERSION_INFO.txt`
  - auf v2.0.8 aktualisiert
  - Forecast-/Fixkosten-Regel dokumentiert
  - alte 2.0.7-Hinweise in aktiven Release-Dokumenten bereinigt

## Testergebnis

```text
python -m pytest -q
34 passed, 1 skipped
```

```text
python tools/sync_version.py --check
Alle Versionsdateien synchron: 2.0.8
```

```text
python tools/dau_first_run_check.py
ERGEBNIS: ALLE CHECKS BESTANDEN ✅
```

```text
python tools/i18n_audit.py
[OK] Keine verdächtigen hardcoded UI-Strings gefunden
```

```text
python -m compileall -q .
0 Syntaxfehler
```

## Release-Status

**Container-Status: release-ready nach Update-Dialog-Fix.**

Offen bleibt nur der manuelle echte Smoke-Test außerhalb des Containers:

1. Windows-EXE/Installer starten.
2. Frischer Erststart mit neuem Datenordner.
3. Kategorie löschen/umbenennen prüfen.
4. Fixkosten-Forecast in der GUI gegenprüfen.
5. `latest.json` mit echten Release-URLs und SHA256 füllen.

