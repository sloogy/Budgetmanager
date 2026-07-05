# BudgetManager v2.1.7 RC2 – Fixbericht Punkt 1 & 2

Geprüftes Ausgangspaket: `BudgetManager Source 2 1 7 RC2 TRACKING SHORT LABELS FIXED.zip`

## Umfang

Umgesetzt wurden nur die vom Nutzer freigegebenen Punkte:

1. Release-Paket von Runtime-/Backup-Artefakten bereinigen.
2. Nutzernahe Doku und Release-Hinweise von alten v2.1.0-Dateinamen auf v2.1.7 synchronisieren.

Punkt 3 aus dem Pre-Release-Bericht, also die Tracking-Tabellenanzeige mit Parent/Child-Kurzlabel, wurde bewusst nicht geändert.

## Änderungen

### 1. Runtime-Backups entfernt

Entfernt aus `data/backups/`:

- `budgetmanager_pre_migration_20260702_203548.bmr`
- `budgetmanager_pre_migration_20260702_203830.bmr`
- `budgetmanager_pre_migration_20260702_203928.bmr`
- `budgetmanager_pre_migration_20260702_203955.bmr`

Damit enthält das Release-Paket keine `.bmr`-Backupdaten mehr.

### 2. Doku-Versionen synchronisiert

Aktualisiert wurden die aktiven, nutzer- und release-nahen Dokumente:

- `README.md`
- `README_INSTALLATION.md`
- `FEATURES.md`
- `docs/features.md`
- `docs/open-tasks.md`
- `docs/release-checklist.md`
- `docs/package-overview.md`
- `docs/architecture.md`
- `docs/help/README.md`
- `docs/help/index.html`

Dabei wurden insbesondere diese alten Namen ersetzt:

- `BudgetManager_Setup_2.1.0.exe` → `BudgetManager_Setup_2.1.7.exe`
- `BudgetManager_Setup_2.1.0.zip` → `BudgetManager_Setup_2.1.7.zip`
- `BudgetManager-v2.1.0-portable-windows.zip` → `BudgetManager-v2.1.7-portable-windows.zip`
- `BudgetManager-v2.1.0-portable-linux.zip` → `BudgetManager-v2.1.7-portable-linux.zip`
- `v2.1.0` Release-Tag-Hinweise → `v2.1.7`

Alte v2.1.0-Releaseberichte im Root wurden aus dem Paket entfernt, damit das Source-Paket nicht mehr wie ein gemischter Zwischenstand wirkt.

Historische v2.1.0-Erwähnungen in `CHANGELOG.md`, Tests und Code-Kommentaren bleiben erhalten, weil sie Regressionen oder Versionshistorie beschreiben.

## Validierung

Ausgeführt im bereinigten Arbeitsbaum:

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py --lang de --lang en --lang fr
python tools/dau_first_run_check.py
python tools/lint_procedure_check.py
python -m pytest -q
python tools/release_logic_audit_100.py
python tools/deep_logic_release_audit.py
```

Ergebnis:

- Versionssync: PASS, 2.1.7 synchron
- Compile: PASS
- i18n-Audit: PASS
- DAU-Erststart: PASS
- Lint-/Release-Prozedur: PASS
- Tests: 282 passed, 2 skipped
- Release-Logik-Audit: PASS, 100 Loops, 0 Findings
- Deep-Logic-Audit: PASS, 500 Loops, 3500 Checks, 0 Findings

## Status

Punkt 1 und 2 sind behoben.

Das Paket ist dadurch als bereinigter v2.1.7-RC2-Fixstand deutlich sauberer. Offen bleibt nur der bewusst zurückgestellte Punkt 3 aus dem Pre-Release-Bericht.
