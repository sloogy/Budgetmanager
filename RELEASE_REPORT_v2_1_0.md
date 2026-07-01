# BudgetManager v2.1.0 – Konsolidierter Release- und Stabilitätsbericht

Stand: 22. Juni 2026
Basis: `BudgetManager_Source_2_0_42_STABILITY_PERFORMANCE.zip`
Zielversion: `2.1.0`

## Release-Urteil

**Ergebnis: Release-Candidate technisch stabilisiert.**

Die kritischen Punkte aus dem externen/zweiten Report wurden umgesetzt: doppelte Datumsbereichslogik wurde zentralisiert, `tracking_model.py` und `cockpit_tab.py` nutzen denselben Helfer, die inline-Datumsberechnung in `get_month_total()` ist entfernt, `busy_timeout` ist konsistent auf 10 Sekunden gesetzt, und veraltete interne DB-Typ-Kommentare wurden bereinigt.

Die Qt-freie Regressionssuite und die Headless-Audits sind grün. Nicht lokal validierbar bleiben echte PySide6-GUI-Smoke-Tests, Qt-Translation-Verify und der Windows-/Linux-/Installer-Build.

## Umgesetzte Fixes

### 1. Single Source of Truth für Datumsbereiche

Neu: `model/date_ranges.py`

Enthält:

- `month_bounds(year, month)` → halb-offener ISO-Monatsbereich `[YYYY-MM-01, nächster Monat)`
- `year_bounds(year)` → halb-offener ISO-Jahresbereich `[YYYY-01-01, Folgejahr-01-01)`
- Validierung ungültiger Monatswerte außerhalb `1..12`

Vorteil:

- keine doppelte Monatslogik mehr in Model und View
- weniger Off-by-one-Risiko
- SQLite kann vorhandene `date`-Indizes verwenden
- alle korrektheitskritischen Monatsfilter nutzen dieselbe Semantik

### 2. `tracking_model.py` bereinigt

Geändert:

- lokale `_month_bounds()` entfernt
- lokale `_year_bounds()` entfernt
- Import auf `model.date_ranges` umgestellt
- `exists_in_month()` nutzt gemeinsamen Helfer
- `list_filtered(year=...)` nutzt `year_bounds()`
- `sum_by_typ()` / `sum_by_category()` / `sum_by_month()` nutzen die zentrale Range-Logik
- `get_month_total()` nutzt jetzt `month_bounds()` statt eigener inline-Berechnung

Bewusst verbliebene `substr(date, ...)`-Nutzungen:

- Monatsvergleich über alle Jahre ohne konkretes Jahr
- Gruppierung nach Monat für Chart-/Auswertungsbuckets
- Distinct-Jahresliste

Diese Fälle sind semantisch keine einfachen `[start,end)`-Filter und wurden deshalb nicht blind ersetzt.

### 3. `cockpit_tab.py` bereinigt

Geändert:

- zweite lokale `_month_bounds()` entfernt
- Cockpit nutzt `model.date_ranges.month_bounds()`
- `_sum_budget_actual()`, Warnungen und offene Fix-/Wiederholungsbuchungen verwenden denselben Helfer

Die vorherige Batch-/CTE-Optimierung für Cockpit bleibt erhalten und vermeidet N+1-Abfragen.

### 4. Weitere Monatsbereich-Hotspots vereinheitlicht

Zusätzlich auf den gemeinsamen Helfer umgestellt:

- `model/budget_overview_model.py`
- `model/budget_warnings_model_extended.py`
- `model/budget_suggestion_engine.py`
- `views/tabs/overview_kpi_panel.py`

Dabei wurden alte inklusive Monatsende-Abfragen (`date <= letzter Tag`) auf die robustere halb-offene Form (`date < nächster Monat`) umgestellt.

### 5. SQLite Locking konsistent gemacht

Vorher:

- `sqlite3.connect(..., timeout=10.0)`
- danach `PRAGMA busy_timeout = 5000`
- effektives Warten damit nur 5 Sekunden

Jetzt:

- `connect(timeout=10.0)` bleibt
- alle relevanten `PRAGMA busy_timeout` stehen auf `10000`

Geändert in:

- `model/database.py`
- `model/crypto.py`
- `views/startup_wizard.py`
- `views/backup_restore_dialog.py`

### 6. Kanonische DB-Typ-Sprache bereinigt

Bereinigt:

- veralteter Kommentar in `model/recurring_transactions_model.py`
- weitere Model-Kommentare, die intern noch „Einnahmen” als DB-Typ beschrieben

Kanonisch bleibt:

- `Einkommen`
- `Ausgaben`
- `Ersparnisse`

Anzeige-Aliasse wie „Einnahmen” bleiben dort bestehen, wo sie bewusst nutzerfreundliche UI-/Theme-/Hilfetexte sind.

### 7. Versionierung auf 2.1.0 gesetzt

Synchronisiert:

- `app_info.py`
- `version.json`
- `VERSION_INFO.txt`
- `installer/budgetmanager_setup.iss`
- `latest.json.template`
- `docs/latest.json.template`
- `README.md`
- `README_INSTALLATION.md`
- Release-/Dokumentationsdateien

`python tools/sync_version.py --check` meldet: **2.1.0 synchron**.

### 8. Neue Regressionstests

Neu: `tests/test_release_210_hardening.py`

Sichert ab:

- Monatsgrenzen Januar, Februar, Dezember und Jahreswechsel
- Jahresgrenzen
- ungültige Monate werden abgelehnt
- keine lokalen `_month_bounds()`-Dubletten in `tracking_model.py` und `cockpit_tab.py`
- `busy_timeout = 10000` bleibt in den relevanten Dateien erhalten

## Kritische Tiefenanalyse

### Versionierung

Status: **PASS**

- zentrale Quelle: `app_info.py`
- Version: `2.1.0`
- Manifest-URLs zeigen auf `v2.1.0`
- Installer-Version ist `2.1.0`

### i18n / Hardcoded UI

Status: **PASS mit Hinweis**

- DE/EN/FR sind synchron
- keine verdächtigen hardcodierten UI-Strings im Audit
- Hinweis: viele ungenutzte Keys bleiben vorhanden. Das ist kein Release-Blocker, sollte aber später bereinigt werden.

### Datenbank / Migration / Locking

Status: **PASS**

- Schema v14 aus der vorherigen Performance-Runde bleibt erhalten
- neue Performance-Indizes bleiben aktiv
- `busy_timeout` ist konsistent auf 10 Sekunden gesetzt
- `temp_store = MEMORY` bleibt aktiv
- Migrationen laufen idempotent in den Headless-Audits

### Forecast / Budget-Logik

Status: **PASS**

- 0-Monats-Schutz bei Fixkosten bleibt unangetastet
- Pot-/inkrementelle Kategorien bleiben geschützt
- Zero-Balance-Regel bleibt optional
- Jahreswechsel-/13.-Monatslohn-Tests bleiben grün

### Updater / Release-Pfade

Status: **PASS in statischer/Headless-Prüfung**

- Manifest-Version synchron
- SHA256-Fail-Closed-Tests bleiben grün
- Staging-Pruning-/Race-Regressionen bleiben grün
- echter Frozen-Build/Installer muss in CI validiert werden

### Performance

Status: **verbessert und weiter stabilisiert**

Bereits in der vorherigen Runde:

- Tracking-/Cockpit-Abfragen von `substr(date, …)` auf Range-Filter umgestellt
- Cockpit N+1 reduziert
- zusätzliche Indizes via Schema v14

Neu in v2.1.0:

- Datumsrange-Logik zentralisiert
- weitere Monatsbereich-Hotspots vereinheitlicht
- `get_month_total()` von inline-Berechnung auf Helfer umgestellt
- inklusive Monatsende-Filter in Budgetübersicht auf halb-offene Bereiche umgestellt

## Validierung

Lokal ausgeführt:

```text
python tools/sync_version.py --check
→ PASS, Version 2.1.0 synchron

python -m compileall -q .
→ PASS

python -m pytest -q -ra
→ 258 passed

python tools/i18n_audit.py
→ PASS, keine verdächtigen hardcoded UI-Strings

python tools/dau_first_run_check.py
→ PASS

python tools/release_logic_audit_100.py
→ PASS, 100 Loops, 0 Findings

python tools/deep_logic_release_audit.py
→ PASS, 500 Loops, 3500 Checks, 0 Findings

python tools/lint_procedure_check.py
→ PASS nach Release-Cleanup
```

Skipped lokal:

```text
tests/test_gui_smoke.py
→ PySide6 nicht installiert

tests/test_startup_restore_regression.py
→ PySide6 nicht installiert
```

Nicht lokal ausführbar:

- `python -m black --check model/` → Modul `black` in dieser Umgebung nicht installiert
- `python -m mypy model/` → Modul `mypy` in dieser Umgebung nicht installiert
- PyInstaller-Build
- Inno-Setup-Build
- echter Windows-Smoke-Test
- echter Linux-Frozen-Smoke-Test

## Release-Risiko-Restliste

Nicht blockierend, aber vor öffentlicher Veröffentlichung in CI/Build prüfen:

1. GitHub Actions müssen vollständig grün laufen.
2. PySide6-GUI-Smoke darf in CI nicht nur skipped sein.
3. `tools/verify_qt_translations.py` muss mit echter PySide6-Umgebung laufen.
4. Windows-Installer `BudgetManager_Setup_2.1.0.exe` bauen und Update-Modus testen.
5. Portable Windows/Linux Artefakte starten und Datenordner-/Updater-Pfade smoke-testen.
6. Die vielen ungenutzten i18n-Keys später bereinigen, aber nicht mehr für diesen Release erzwingen.

## Fazit

**v2.1.0 ist als Release-Candidate deutlich sauberer als v2.0.42.**

Die vom zweiten Report genannten Punkte sind umgesetzt. Zusätzlich wurden mehrere Datumsbereich-Hotspots außerhalb von `tracking_model.py` und `cockpit_tab.py` vereinheitlicht. Die Headless-Qualitätsgates sind grün. Für einen finalen öffentlichen Release fehlt nur noch der echte CI-/Build-Nachweis mit PySide6, PyInstaller und Inno Setup.
