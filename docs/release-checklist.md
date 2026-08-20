# Release-Checkliste — BudgetManager v2.2.63

## Lokal prüfen

```bash
python tools/sync_version.py --check
python tools/verify_hashed_lock.py
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
python tools/dau_first_run_check.py
python -m black --check --workers 1 main.py app_info.py settings.py settings_dialog.py theme_manager.py model updater utils views tools tests
python -m mypy model/ updater/manifest_signing.py utils/secure_excel.py utils/ui_experience_mode.py
python tools/bandit_release_gate.py --bandit-json audit_artifacts/BANDIT_CURRENT.json --summary-json audit_artifacts/BANDIT_RELEASE_GATE.json
python -m pytest tests/ -v -ra --tb=short --cov --cov-branch --cov-report=json:audit_artifacts/coverage_full.json --cov-fail-under=40
python tools/coverage_gate.py --json audit_artifacts/coverage_full.json --summary-json audit_artifacts/coverage_gate_summary.json --overall-min 40
python tools/architecture_quality_gate.py
python tools/enterprise_release_audit_10000.py --loops 10000 --seed 20260718 --json-out audit_artifacts/ENTERPRISE_RELEASE_AUDIT_10000.json
python tools/run_killcritic_usability_10000.py --loops 10000 --seed 20260718 --json audit_artifacts/KILLCRITIC_USABILITY_10000.json --csv audit_artifacts/KILLCRITIC_USABILITY_10000.csv
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
```


## Einziger automatisierter Release-Workflow

Im Repository existiert ausschließlich `.github/workflows/build.yml`. Er wird nur
durch einen Tag `v*` gestartet und erledigt die gesamte Veröffentlichung:

1. Windows- und Linux-onedir-Build mit PyInstaller.
2. Windows-Installer mit Inno Setup.
3. Portable ZIPs für Windows und Linux.
4. Unsigned `.lpmodule`-Pakete für Windows und Linux samt SHA-256-Dateien.
5. `latest.json`, `SHA256SUMS.txt` und SBOM.
6. Upload aller Dateien in den GitHub-Release.

Für nicht-kommerzielle Vorab-Releases darf `latest.json` ohne
`latest.json.sig` veröffentlicht werden. Der signaturpflichtige In-App-Updater
nimmt ein solches Manifest bewusst nicht an; Installer und portable Pakete
bleiben manuell nutzbar. Vor einer regulären Veröffentlichung werden Manifest-
und Authenticode-Signierung als verpflichtende Gates aktiviert.

Die umfangreichen Enterprise-, Security- und Usability-Audits bleiben als lokale
Werkzeuge erhalten, einschließlich des 10.000er Enterprise-Audits, starten aber
keine eigenen GitHub-Workflows mehr.

## Funktionale Freigabe prüfen

- Cockpit: Rechtsklick öffnet Cockpit-Aktionen.
- Cockpit: Budgetwarnungen sind sichtbar.
- Budgetwarnung: Doppelklick öffnet die Warnungsprüfung.
- Tracking: Buchung erfassen, bearbeiten, löschen.
- Backup: Backup erstellen und Import/Restore testen.
- Restore: falscher Wiederherstellungscode führt zurück zum Start, ohne defekten Benutzer zu behalten.
- Start: defektes Konto bietet Selbstheilung an statt die App zu blockieren.

## Release erstellen

```bash
git status
git add .
git commit -m "Release v2.2.63"
git push origin main
git tag -a v2.2.63 -m "BudgetManager v2.2.63"
git push origin v2.2.63
```

## Nach GitHub Actions

- Kontrollieren, dass der Workflow `Build Executables` grün ist.
- Windows- und Linux-Portable-ZIP stichprobenartig starten.
- `BudgetManager_Setup_<Version>.exe` unter Windows testen.
- Von GitHub Actions erzeugte `latest.json` prüfen: Version, URLs und SHA256-Werte müssen zum Tag passen.
- `SHA256SUMS.txt` gegen die veröffentlichten Assets prüfen.
- Windows- und Linux-`.lpmodule` mit LifePlanner/LiveManager prüfen; Status muss „Nicht signiert“ lauten und die manuelle Vertrauensbestätigung funktionieren.
- Release-Beschreibung aus `CHANGELOG.md` übernehmen.
