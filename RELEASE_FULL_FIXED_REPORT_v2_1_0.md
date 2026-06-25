# BudgetManager v2.1.0 – Full Fixed Source Package

## Enthaltene Fixes

- Windows-sicherer PID-Check aus v2.1.0-Diagnosefix bleibt enthalten.
- Diagnose-/Log-Menü und lokaler Fehlerbericht bleiben enthalten.
- Mypy-/Black-Fixes aus v2.1.0 bleiben enthalten.
- `tools/verify_qt_translations.py` gibt keine nicht-CP1252-fähigen Emojis mehr aus; Windows-GitHub-Actions bricht dadurch nicht mehr mit `UnicodeEncodeError` ab.
- `updater/common.py` liest `install_type` robuster aus `installation.json`; falls JSON wegen unescaped Windows-Backslashes nicht parsebar ist, wird `install_type` per engem Regex-Fallback gelesen.
- Windows-Installer-Installationen priorisieren dadurch wieder `windows_installer` vor `direct_windows_exe`.
- `installer/budgetmanager_setup.iss` nutzt in `InitializeWizard` nicht mehr `{app}` vor der Initialisierung. Stattdessen wird `WizardDirValue` bzw. der Standardpfad verwendet.
- `start-macos.sh` ergänzt für Source-Start auf macOS. Kein fertiges macOS-App-Bundle.

## Lokal in dieser Paketierung geprüft

```text
python -m pytest tests/test_installer_icon_workflow.py::test_updater_has_different_asset_paths_for_installer_direct_and_portable -q  PASS
python tools/sync_version.py --check                                                                         PASS, 2.1.0 synchron
python tools/i18n_audit.py                                                                                   PASS
python tools/lint_procedure_check.py                                                                         PASS nach Cleanup
```

## Noch extern zu prüfen

- Voller GitHub-Actions-Build auf Windows/Linux.
- Windows-Installer-Smoke: Installation starten, Seiten durchgehen, App starten.
- Windows-Updater-Smoke: Installer-Installation muss Installer-Asset nutzen.
- Windows-Doppelstart und Crash-Neustart-Diagnose.

