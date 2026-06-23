# BudgetManager v2.1.0 – Windows-Diagnose-Hardening Report

## Kurzurteil

Die im externen Review genannten Release-Blocker wurden umgesetzt. Der kritische Windows-Pfad nutzt nun keinen destruktiven `os.kill(pid, 0)`-Check mehr. Die Diagnosefunktion ist robuster, datenschutzfreundlicher und besser testbar. Für einen finalen Windows-Release bleibt ein echter Windows-/Frozen-Smoke-Test Pflicht, weil diese Umgebung hier nicht zur Verfügung steht.

## Umgesetzte Fixes

### 1. Windows-sicherer PID-Check

Neu: `model/process_utils.py`

- `is_pid_alive()` ist jetzt die zentrale PID-Prüfung.
- Unter POSIX bleibt `os.kill(pid, 0)` erhalten.
- Unter Windows wird `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE)` plus `WaitForSingleObject(handle, 0)` genutzt.
- Unklare Windows-Fehler werden konservativ als „lebt vermutlich” behandelt, damit kein Live-Lock entfernt und keine zweite Datenbankinstanz zugelassen wird.

Geändert:

- `main.py` / `_SingleInstanceGuard._pid_alive()` nutzt `model.process_utils.is_pid_alive()`.
- `model/diagnostics.py` nutzt ebenfalls den zentralen Helfer.

### 2. PID-Reuse-False-Negative entfernt

`previous_state_was_unclean()` nutzt keine PID-Lebendigkeitsprüfung mehr.

Neue Logik:

```text
Single-Instance-Lock wurde erworben + alter runtime_state sagt app_running=true
= letzter Lauf war unsauber beendet
```

Damit wird ein Crash-Hinweis nicht mehr unterdrückt, nur weil dieselbe PID nach Reboot/Crash inzwischen einem anderen Prozess gehört.

### 3. Diagnose-ZIP gehärtet

`create_diagnostic_report_zip()` schreibt jetzt immer:

- `MANIFEST.txt`
- `version.json` aus Datei, `_MEIPASS` oder `app_info`-Fallback
- `system_info.json`
- `budgetmanager_settings.sanitized.json`
- `README.txt`

Wenn Pflichtdateien wie `budgetmanager.log` fehlen, wird zusätzlich geschrieben:

- `READ_ERRORS.txt`

Damit entsteht kein scheinbar erfolgreicher, aber still leerer Bericht mehr.

### 4. Datenschutz verbessert

Im Diagnose-ZIP werden benutzerspezifische Home-Pfade maskiert:

```text
C:\Users\<Name>\...  → <home>\...
/home/<name>/...      → <home>/...
```

Das betrifft unter anderem:

- `runtime_state.json`
- `installation.json`
- `system_info.json`
- bereinigte Settings

### 5. Sanitizer präzisiert

Der Secret-Sanitizer entfernt weiterhin echte sensible Felder wie:

- `password`
- `api_token`
- `db_key`
- `restore_key`
- `pin`
- `salt`

Er entfernt aber nicht mehr harmlose Felder nur wegen Teilstrings, z. B.:

- `spinbox_value`
- `column_mapping`

### 6. PyInstaller-Version-Fallback

`BudgetManager.spec` enthält jetzt:

```python
("version.json", ".")
```

Zusätzlich sucht die Diagnosefunktion im Frozen-Build auch in `sys._MEIPASS`. Falls `version.json` trotzdem fehlt, wird ein gültiges `version.json` aus `app_info` generiert.

### 7. Neue Regressionstests

Ergänzt:

- `tests/test_windows_safe_pid_check_v210.py`
- zusätzliche Tests in `tests/test_release_diagnostics_v210.py`

Abgedeckt:

- Windows-PID-Check ruft kein `os.kill` auf.
- POSIX-Pfad nutzt weiterhin Signal 0.
- PID-Reuse-/Crash-Hinweis-Pfad fragt keine PID-Lebendigkeit mehr ab.
- Diagnose-ZIP enthält Manifest und Read-Errors bei fehlendem Hauptlog.
- Diagnose-ZIP enthält `version.json` auch ohne physische Datei.
- Home-Pfade werden in Runtime-/Systeminfo maskiert.
- Secret-Sanitizer redigiert nicht mehr zu breit.

## Validierung

```text
python -m compileall -q .                  PASS
python -m pytest -q -ra                    PASS, 252 passed, 2 skipped
python tools/sync_version.py --check       PASS, 2.1.0 synchron
python tools/i18n_audit.py                 PASS
python tools/dau_first_run_check.py        PASS
python tools/release_logic_audit_100.py    PASS, 100 Loops / 0 Findings
python tools/deep_logic_release_audit.py   PASS, 500 Loops / 3500 Checks / 0 Findings
python tools/lint_procedure_check.py       PASS nach Release-Cleanup
```

## Nicht lokal validierbar

Diese Umgebung hat kein PySide6 und kein Windows. Deshalb bleiben vor finalem Release zwingend offen:

1. Windows-Doppelstart: zweite Instanz darf die erste nicht beenden.
2. Windows-Crashfluss: App im Task-Manager killen, neu starten, Crash-Hinweis muss erscheinen.
3. Windows-Frozen-Smoke: Diagnose-ZIP aus echter EXE erzeugen und Inhalt prüfen.
4. Linux-GUI-Smoke mit PySide6.
5. PyInstaller-/Inno-Setup-Build in CI.

## Release-Urteil

Der bekannte Windows-Blocker im Code ist behoben. Das Paket ist wieder ein plausibler Release Candidate. Final freigeben erst nach echtem Windows-Smoke-Test des Doppelstarts und des Crash-Neustart-Flows.
