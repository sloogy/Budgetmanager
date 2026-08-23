# Release-Checkliste — BudgetManager v2.4.1

## Lokal prüfen

```bash
python tools/sync_version.py --check
python tools/verify_hashed_lock.py
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/exception_audit.py
python -m ruff check . --select E9,F63,F7,F82
python tools/i18n_audit.py
python tools/dau_first_run_check.py
python tools/gepinnte_werkzeuge.py black --check --workers 1 main.py app_info.py settings.py settings_dialog.py theme_manager.py model updater utils views tools tests
python tools/gepinnte_werkzeuge.py mypy model/ updater/
python tools/bandit_release_gate.py --bandit-json audit_artifacts/BANDIT_CURRENT.json --summary-json audit_artifacts/BANDIT_RELEASE_GATE.json
python -m pytest tests/ -v -ra --tb=short --cov --cov-branch --cov-report=json:audit_artifacts/coverage_full.json --cov-fail-under=40
python tools/coverage_gate.py --json audit_artifacts/coverage_full.json --summary-json audit_artifacts/coverage_gate_summary.json --overall-min 40
python tools/architecture_quality_gate.py
python tools/enterprise_release_audit_10000.py --loops 10000 --seed 20260718 --json-out audit_artifacts/ENTERPRISE_RELEASE_AUDIT_10000.json
python tools/run_killcritic_usability_10000.py --loops 10000 --seed 20260718 --json audit_artifacts/KILLCRITIC_USABILITY_10000.json --csv audit_artifacts/KILLCRITIC_USABILITY_10000.csv
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
```
> **black und mypy immer ueber `tools/gepinnte_werkzeuge.py` aufrufen.** Beide
> formatieren beziehungsweise urteilen von Nebenversion zu Nebenversion
> unterschiedlich. Die CI nimmt die Version aus `requirements-dev.txt`, ein
> `python -m black` nimmt die des Rechners - und macht damit das Gate rot,
> ohne dass am Code etwas falsch waere.



## Die beiden Workflows

Im Repository existieren genau zwei Workflows; `tools/lint_procedure_check.py`
prüft diese Liste und meldet jeden weiteren.

- `.github/workflows/push-checks.yml` — der schnelle Lauf bei jedem Push auf
  `main`: Linux, ein Python, keine Builds, zwei bis drei Minuten. Er reagiert nie
  auf Tags und überspringt `[release]`-Commits, weil die ohnehin durch den vollen
  Lauf gehen.
- `.github/workflows/build.yml` — der Release-Weg. Ihn startet ausschliesslich
  ein Tag `v*`; ein Push auf `release/**` synchronisiert nur die
  Release-Metadaten. Der frühere zweite Auslöser, ein `[release]`-Commit auf
  `main`, ist entfallen: Beim Release werden Zweig und Tag zusammen gepusst,
  der Bau lief also zweimal für denselben Stand und lud beide Male unter
  denselben Tag hoch. Da `latest.json` die Hashes der ZIPs trägt, hätten
  Manifest und ZIP aus verschiedenen Läufen stammen können — der Updater
  lehnt so etwas fail-closed ab. Eine `concurrency`-Sperre sichert das
  zusätzlich.

Der Releaselauf erledigt die gesamte Veröffentlichung:

1. Windows- und Linux-onedir-Build mit PyInstaller.
2. Windows-Installer mit Inno Setup, inklusive Silent-Install-, Start- und
   Silent-Uninstall-Test.
3. Portable ZIPs für Windows und Linux.
4. Unsigned `.lpmodule`-Pakete für Windows und Linux samt SHA-256-Dateien.
5. `latest.json`, `latest.json.sig`, `SHA256SUMS.txt` und SBOM.
6. Upload aller Dateien in den GitHub-Release.

Die Manifest-Signierung ist seit v2.2.65 verpflichtend: Ohne die Repository-
Variable `UPDATE_SIGNING_PUBLIC_KEY_B64` bricht der Build vor PyInstaller ab,
und ein Release ohne `latest.json.sig` kommt nicht durch das Gate. Der
In-App-Updater nimmt ein unsigniertes Manifest nicht an. Die
Authenticode-Signierung der Windows-Binaries hängt am Code-Signing-Zertifikat;
Details in [release-signing.md](release-signing.md).

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
VERSION="$(python -c 'from app_info import APP_VERSION; print(APP_VERSION)')"
git status
git add .
git commit -m "Release v$VERSION"
git push origin main
git tag -a "v$VERSION" -m "BudgetManager v$VERSION"
git push origin "v$VERSION"
```

Die Version kommt immer aus `app_info.py`; so bleibt der Tag automatisch
richtig. Der Tag ist der einzige Auslöser des Release-Laufs — ein
`[release]`-Commit auf `main` baut nichts mehr.

## Nach GitHub Actions

- Kontrollieren, dass der Workflow `Build Executables` grün ist.
- Windows- und Linux-Portable-ZIP stichprobenartig starten.
- `BudgetManager_Setup_<Version>.exe` unter Windows testen.
- Von GitHub Actions erzeugte `latest.json` prüfen: Version, URLs und SHA256-Werte müssen zum Tag passen.
- `SHA256SUMS.txt` gegen die veröffentlichten Assets prüfen.
- Windows- und Linux-`.lpmodule` mit LifePlanner/LiveManager prüfen; Status muss „Nicht signiert“ lauten und die manuelle Vertrauensbestätigung funktionieren.
- Release-Beschreibung aus `CHANGELOG.md` übernehmen.
