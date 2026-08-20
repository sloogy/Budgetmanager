# Offene Release-Aufgaben — BudgetManager v2.2.62

Stand: 20. August 2026

## Source-Code-Status

Alle im lokalen Quellcode-Audit gefundenen technischen Findings wurden behoben. Versionsabgleich, Hash-Lockfiles, Syntax, Architektur, Übersetzungen, Handbuch, DAU-E2E, Funktionsregressionen und interne Release-Audits werden für v2.2.62 neu geprüft. Vor einer regulären Binärfreigabe müssen zusätzlich Signierung sowie die externen GitHub-Gates unter Fedora/Wayland und Windows grün sein.

## Einmalige externe Vertrauensanker

Diese Werte können nicht sinnvoll im Quellcode erzeugt oder mitgeliefert werden. Sie müssen im GitHub-Repository hinterlegt werden; ohne sie bricht der Tag-Build absichtlich ab:

- Variable `UPDATE_SIGNING_PUBLIC_KEY_B64`
- Secret `UPDATE_SIGNING_PRIVATE_KEY_B64`
- Secret `WINDOWS_CODESIGN_PFX_B64`
- Secret `WINDOWS_CODESIGN_PASSWORD`

Anleitung: `docs/release-signing.md`.

## Vor der finalen öffentlichen Freigabe

- Tag `v2.2.62` erstellen und den einzigen GitHub-Actions-Releaseworkflow grün abschliessen lassen.
- Online-`pip-audit` im Dependency-Workflow prüfen.
- GitHub Build-Provenance/Attestation prüfen.
- Authenticode-Signatur von `BudgetManager.exe` und Installer prüfen.
- Windows-Installer installieren, starten, Update-Modus testen und deinstallieren.
- Portable Windows- und Linux-Pakete auf einem sauberen System starten.
- `latest.json` und `latest.json.sig` gemeinsam prüfen.
- SHA-256-Summen und CycloneDX-SBOM archivieren.

## Lokale Vollprüfung

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
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
```
