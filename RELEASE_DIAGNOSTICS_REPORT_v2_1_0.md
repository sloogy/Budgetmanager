# BudgetManager v2.1.0 — Log-/Crash-Diagnose Release-Fix

## Ziel

Umgesetzt wurde die gewünschte DAU-freundliche Windows-/Portable-Diagnose:

- jederzeit unter **Hilfe/Info → Log anzeigen** erreichbar,
- nach einem vermuteten Crash oder erzwungenen Beenden beim nächsten Start sichtbar,
- lokaler Fehlerbericht als ZIP ohne Datenbank und ohne Backups.

## Umgesetzte Änderungen

### 1. Neuer Qt-freier Diagnosekern

Neue Datei:

- `model/diagnostics.py`

Funktionen:

- `log_file_path()` → `budgetmanager.log`
- `crash_log_file_path()` → `budgetmanager_crash.log`
- `runtime_state_path()` → `runtime_state.json`
- `mark_app_started()` / `mark_app_exited()` für Crash-/Kill-Erkennung beim Neustart
- `read_text_tail()` für schnelles Anzeigen großer Logs
- `create_diagnostic_report_zip()` für lokalen Fehlerbericht
- `remove_old_diagnostic_reports()` zur Begrenzung alter Diagnose-ZIPs

Der Diagnosebericht enthält bewusst **keine** Datenbank, keine Backups und keine Exporte.

Enthalten sind:

- `budgetmanager.log` plus Logrotationen,
- `budgetmanager_crash.log`,
- `runtime_state.json`,
- `installation.json`, falls vorhanden,
- `version.json`,
- `system_info.json`,
- bereinigte `budgetmanager_settings.sanitized.json`.

### 2. Menü unter Hilfe/Info erweitert

Datei:

- `views/main_window.py`

Neue Einträge:

- **Log anzeigen…**
- **Crash-Log anzeigen…**
- **Diagnoseordner öffnen**
- **Fehlerbericht erstellen…**

Die Loganzeige nutzt einen eigenen `LogViewerDialog`, liest nur das Dateiende und bleibt dadurch auch bei größeren Logdateien reaktionsfähig.

### 3. Crash-/Kill-Erkennung beim Neustart

Datei:

- `main.py`

Beim Start nach erfolgreichem Single-Instance-Lock wird geschrieben:

```json
{
  "app_running": true,
  "last_exit_clean": false,
  "pid": 1234,
  "version": "2.1.0"
}
```

Beim sauberen Beenden wird gesetzt:

```json
{
  "app_running": false,
  "last_exit_clean": true,
  "exit_reason": "qt_exit_0"
}
```

Wenn beim nächsten Start noch ein nicht sauberer Zustand gefunden wird, erscheint nach dem Öffnen des Hauptfensters ein Hinweis mit:

- **Log anzeigen**
- **Fehlerbericht erstellen**
- **Ignorieren**

Kontrollierte frühe Exits wie Login-Abbruch werden sauber markiert und lösen keinen falschen Crash-Hinweis aus.

### 4. i18n vollständig ergänzt

Dateien:

- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`

Alle neuen UI-Texte wurden in Deutsch, Englisch und Französisch ergänzt.

### 5. Tests ergänzt

Neue Datei:

- `tests/test_release_diagnostics_v210.py`

Abgedeckt:

- unclean Runtime-State wird erkannt,
- clean Exit löscht den Crash-Hinweis-Zustand,
- Diagnose-ZIP enthält Logs/Systeminfos/bereinigte Settings,
- Diagnose-ZIP enthält keine DB und keine Backups,
- neue Menü-/i18n-Keys sind vorhanden.

## Validierung

Ausgeführt im Source-Paket:

```text
python -m compileall -q .                         PASS
python -m pytest -q -ra                           PASS, 258 passed
python tools/sync_version.py --check              PASS, 2.1.0 synchron
python tools/i18n_audit.py --lang de --lang en --lang fr  PASS
python tools/dau_first_run_check.py               PASS
python tools/release_logic_audit_100.py           PASS, 100 Loops / 0 Findings
python tools/deep_logic_release_audit.py          PASS, 500 Loops / 3500 Checks / 0 Findings
python tools/lint_procedure_check.py              PASS nach Cleanup
```

Nicht lokal validierbar:

- PySide6-GUI-Smoke,
- echte Qt-Translation-Verify-Ausführung,
- PyInstaller-/Inno-Setup-Build.

Diese Punkte müssen weiterhin in GitHub Actions beziehungsweise auf Windows/Linux grün laufen.

## Release-Urteil

Die gewünschte Log-/Crashreport-Funktion ist umgesetzt und statisch/regressiv validiert.

Status: **Releasefähig als v2.1.0 mit Diagnose-Hardening**, sofern der echte GUI-/Build-CI-Lauf grün ist.
