# BudgetManager v2.2.1 – KILLCRITIC Release-Audit & Fixbericht

Datum: 3. Juli 2026  
Basis: `BudgetManager Source 2 2 1 RELEASE.zip`  
Ergebnis: **Release Candidate nach Fix releasefähig als Source-Paket**, mit zwei Einschränkungen: GUI-Smoke und echte Windows-/Linux-Build-Smokes müssen in GitHub Actions bzw. auf Zielsystemen laufen, weil in dieser Umgebung PySide6 nicht installiert ist.

## Gefundene Blocker / Risiken

### 1. GitHub-Actions-Workflow pinnte Black doppelt und widersprüchlich

**Problem:**  
`.github/workflows/build.yml` installierte zuerst `requirements-dev.txt`, darin `black==25.1.0`, danach aber zusätzlich:

```bash
python -m pip install --force-reinstall "black==26.5.1"
```

Das ist ein Release-Risiko, weil die lokale Dev-Tool-Quelle und der CI-Workflow auseinanderlaufen. Wenn die hart gesetzte Zusatzversion nicht verfügbar ist oder sich anders verhält, kann GitHub Actions scheitern, obwohl das Projekt lokal sauber ist.

**Fix:**  
Die zusätzliche `--force-reinstall`-Zeile wurde entfernt. `requirements-dev.txt` ist wieder die zentrale Quelle für Dev-Tools.

**Absicherung:**  
`tools/lint_procedure_check.py` blockiert künftig einen separaten Black-`--force-reinstall`-Pin im Workflow. `tests/test_lint_release_procedure_v2041.py` prüft, dass diese Schutzlogik vorhanden bleibt.

### 2. Release-Baum nach Testläufen muss konsequent bereinigt werden

**Befund:**  
Nach lokalen Testläufen entstehen erwartungsgemäß `__pycache__`, `.pytest_cache` und temporäre Backup-Artefakte. Der Cleaner entfernt diese korrekt.

**Fix/Abschluss:**  
`tools/clean_release_tree.py` wurde ausgeführt. Das finale Paket enthält keine generierten Python-Caches, Test-Caches oder `.bmr`-Backups.

## Durchgeführte Checks

| Check | Ergebnis |
|---|---:|
| `python -m compileall -q .` | PASS |
| `python -m pytest -q -ra` | 303 passed, 2 skipped |
| `python tools/sync_version.py --check` | PASS – 2.2.1 synchron |
| `python tools/i18n_audit.py` | PASS – keine fehlenden Keys, keine verdächtigen hardcoded UI-Strings |
| `python tools/lint_procedure_check.py` | PASS |
| `python tools/deep_logic_release_audit.py` | PASS – 500 Loops / 3500 Checks |
| `python tools/release_logic_audit_100.py` | PASS – 100 Loops |
| `python tools/dau_first_run_check.py` | PASS |

## Bewusst nicht vollständig lokal verifiziert

- `python tools/verify_qt_translations.py` konnte in dieser Umgebung nicht final geprüft werden, weil PySide6 nicht installiert ist. Der Workflow installiert PySide6 über `requirements-build.txt`/`requirements-dev.txt`; der echte Gate muss in GitHub Actions laufen.
- GUI-Smoke-Tests wurden deshalb übersprungen: `tests/test_gui_smoke.py` und `tests/test_startup_restore_regression.py`.
- Windows-Installer, Windows-Portable und Linux-Portable müssen nach GitHub-Actions-Build auf echten Zielsystemen gestartet werden.

## Release-Entscheid

**Source-Release: JA, nach Fix freigabefähig.**  
**Public Final Release: JA, wenn GitHub Actions grün ist und die manuellen Windows-/Linux-Smokes aus `docs/open-tasks.md` bestanden sind.**
