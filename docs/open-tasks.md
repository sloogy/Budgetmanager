# Offene Release-Aufgaben — BudgetManager v3.0.7

Stand: 25. August 2026

## Source-Code-Status

Alle im lokalen Quellcode-Audit gefundenen technischen Findings wurden behoben. Versionsabgleich, Hash-Lockfiles, Syntax, Architektur, Übersetzungen, Handbuch, DAU-E2E, Funktionsregressionen und interne Release-Audits werden für v3.0.6 neu geprüft. Vor einer regulären Binärfreigabe müssen zusätzlich Signierung sowie die externen GitHub-Gates unter Fedora/Wayland und Windows grün sein.

## Einmalige externe Vertrauensanker

Diese Werte können nicht sinnvoll im Quellcode erzeugt oder mitgeliefert werden. Sie müssen im GitHub-Repository hinterlegt werden; ohne sie bricht der Tag-Build absichtlich ab:

- Variable `UPDATE_SIGNING_PUBLIC_KEY_B64`
- Secret `UPDATE_SIGNING_PRIVATE_KEY_B64`
- Secret `WINDOWS_CODESIGN_PFX_B64`
- Secret `WINDOWS_CODESIGN_PASSWORD`

Anleitung: `docs/release-signing.md`.

## Vor der finalen öffentlichen Freigabe

- Tag `v3.0.6` erstellen und den einzigen GitHub-Actions-Releaseworkflow grün abschliessen lassen.
- GitHub Build-Provenance/Attestation prüfen.
- Authenticode-Signatur von `BudgetManager.exe` und Installer prüfen.
- Windows-Installer installieren, starten, Update-Modus testen und deinstallieren.
- Portable Windows- und Linux-Pakete auf einem sauberen System starten.
- `latest.json` und `latest.json.sig` gemeinsam prüfen.
- SHA-256-Summen und CycloneDX-SBOM archivieren.

## Abhängigkeitsprüfung

`pip-audit` läuft in keinem Workflow und soll das auch nicht: `ERLAUBTE_WORKFLOWS`
in `tools/lint_procedure_check.py` lässt genau drei Workflows zu, ein vierter
wäre sofort rot. Gefahren wird die Prüfung von Hand, vor jedem Release:

```bash
uvx --python 3.12 pip-audit@2.10.1 -r requirements-build.lock --progress-spinner off
uvx --python 3.12 pip-audit@2.10.1 -r requirements-dev.lock --progress-spinner off
```

`--python 3.12` ist Pflicht. Ohne die Angabe zieht `uv` cp314-Wheels, und
`pip-audit` bricht mit einem Hash-Mismatch ab, der wie ein defektes Lockfile
aussieht, aber nur ein Artefakt der Python-Version ist.

**Stand 26. August 2026**

- `requirements-build.lock` — das, was ausgeliefert wird — ist sauber.
- `requirements-dev.lock` meldet drei Einträge, alle für `black 25.1.0`
  (PYSEC-2026-2120, PYSEC-2026-2121; behoben ab 26.3.0 beziehungsweise 26.3.1).
  `pip` ist am 26. August 2026 von 26.1.2 auf 26.2.1 gehoben worden
  (PYSEC-2026-3721) und damit erledigt.

**black bleibt bewusst auf 25.1.0.** Ein Testlauf mit `black 26.3.1` gegen die
CI-Pfadliste formatiert **49 Dateien** um. black ist an vier Stellen gepinnt
(`requirements-dev.txt`, `requirements-dev.lock`, `push-checks.yml`,
`build.yml`, dazu `release-prepare.yml` über `tools/gepinnte_werkzeuge.py`); ein
Versionswechsel zieht also einen projektweiten Reformat-Commit nach sich. Dem
steht kein Nutzerrisiko gegenüber: black ist ein Formatierer, läuft nie beim
Anwender und verarbeitet ausschliesslich Quelltext aus diesem Repository. Die
Stabilität der Pins wiegt hier schwerer. Neu bewerten, sobald ohnehin ein
black-Sprung ansteht oder ein Fund den ausgelieferten Lock trifft.

## Lokale Vollprüfung

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
python tools/clean_release_tree.py
python tools/lint_procedure_check.py
```
> **black und mypy immer ueber `tools/gepinnte_werkzeuge.py` aufrufen.** Beide
> formatieren beziehungsweise urteilen von Nebenversion zu Nebenversion
> unterschiedlich. Die CI nimmt die Version aus `requirements-dev.txt`, ein
> `python -m black` nimmt die des Rechners - und macht damit das Gate rot,
> ohne dass am Code etwas falsch waere.

