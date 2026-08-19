# Release-Checkliste — BudgetManager v2.2.60

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


## Vor dem ersten Release einmalig konfigurieren

Siehe `docs/release-signing.md`. Update-Signierschlüssel und Windows-Code-Signing-Zertifikat müssen als GitHub Variable/Secrets hinterlegt sein. Ohne diese Vertrauensanker bricht der Release-Build absichtlich ab.

## Verpflichtende automatisierte Release-Gates

Der Tag-Build startet diese beiden wiederverwendbaren Workflows und wartet auf sie:

- `platform-release-gates.yml`: Fedora 42 und latest unter Wayland bei 100/125/150/200 %, Windows bei 100/125/150/200 %, Qt-Accessibility, GUI- und Updater-Selbsttest.
- `dependency-audit.yml`: Bandit-Gate mit Nulltoleranz für MEDIUM/HIGH, Online-`pip-audit` des Lockfiles, `pip check` und Audit-Artefakte.
- `enterprise-release-audit-10000`: reproduzierbare 10.000 Zustands-Loops mit 112.000 Datenintegritätsprüfungen und JSON-Nachweis.
- `killcritic-usability-audit-10000`: 10.000 dynamische Qt-Usability-Loops über Navigation, Dialoge, Tastatur, Accessibility, Skalierung, Meldungen und End-to-End-Abläufe.

Ohne grünen Status aller vier Gates werden keine Release-Binaries gebaut.

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
git commit -m "Release v2.2.60"
git push origin main
git tag -a v2.2.60 -m "BudgetManager v2.2.60"
git push origin v2.2.60
```

## Nach GitHub Actions

- Kontrollieren, dass `platform-release-gates`, `dependency-security-gate` und `enterprise-release-audit-10000` und `killcritic-usability-audit-10000` grün sind.
- Das hochgeladene 10.000-Loop-JSON als Release-Nachweis archivieren.
- Das KILLCRITIC-Usability-JSON und die Loop-Matrix als Release-Nachweis archivieren.
- Das hochgeladene Online-`pip-audit`-JSON als Release-Nachweis archivieren.
- Windows-EXE und Linux-Binary stichprobenartig starten.
- Von GitHub Actions erzeugte `latest.json` prüfen: Version, URLs und SHA256-Werte müssen zum Tag passen.
- Release-Beschreibung aus `CHANGELOG.md` übernehmen.
