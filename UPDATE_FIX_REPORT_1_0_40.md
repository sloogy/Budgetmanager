# Update-Fix Report 1.0.40

## Problem

Der Windows-Updater konnte Updates nicht zuverlässig anwenden.

Hauptursachen:

1. `latest.json` zeigte bei `windows` auf eine direkte `.exe`.
2. `updater.check_update` behandelte dieses Asset trotzdem als ZIP und versuchte es zu entpacken.
3. Unter Windows kann eine laufende PyInstaller-EXE sich nicht selbst überschreiben.
4. Release-Dateien waren nicht versioniert benannt.

## Fixes

### Updater-Check

- `updater/check_update.py` prüft jetzt, ob das gewählte Asset wirklich eine ZIP-Datei ist.
- Wenn `windows` oder `linux` auf eine direkte EXE/Binary zeigen, nutzt der Updater automatisch `portable_zip`, sofern vorhanden.
- Wenn gar kein ZIP-Update vorhanden ist, erscheint eine klare Fehlermeldung statt eines Entpackungsfehlers.

### Windows-Apply

- `updater/apply_update.py` erkennt Windows + PyInstaller/Frozen.
- In diesem Fall wird nicht mehr direkt aus der laufenden EXE heraus kopiert.
- Stattdessen wird ein externes `updates/apply_update_<version>.cmd` erzeugt.
- Das CMD-Skript wartet auf laufende BudgetManager-Prozesse, ersetzt dann Programmdateien und lässt `data/` sowie `updates/` stehen.

### GUI

- `views/update_dialog.py` übergibt beim Anwenden die PID der laufenden App an den Updater, damit das externe Windows-Skript sauber warten kann.

### GitHub Actions / Release

- Release-Dateien werden versioniert benannt:
  - `BudgetManager-v1.0.40-windows.exe`
  - `BudgetManager-v1.0.40-linux`
  - `BudgetManager-v1.0.40-portable.zip`
- `latest.json` zeigt für `windows` und `linux` bewusst auf das portable ZIP.
- Direkte EXE/Binary-Assets bleiben zusätzlich als `direct_windows_exe` und `direct_linux_binary` im Manifest enthalten, sind aber nur für manuelle Downloads gedacht.

## Geprüft

- `python tools/sync_version.py --check`
- `python -m compileall -q . -x '_attic|__pycache__'`
- `python tools/i18n_audit.py --lang de --lang en --lang fr`
- Fallback-Auswahl im Updater mit einem alten Manifest simuliert.
