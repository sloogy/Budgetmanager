# Portable Updater (GitHub Releases)

Dieser Updater ist für die portable Version gedacht:

- `data/` bleibt erhalten (DB, Settings, Backups).
- Update ersetzt nur Programmdateien.
- Windows-Installer-Installationen bevorzugen das Installer-Asset `windows_installer`.
- Portable Windows/Linux bevorzugen das portable ZIP.

## Manifest-URL (Default)

Der Updater erwartet ein `latest.json` im GitHub Release:

```text
https://github.com/sloogy/Budgetmanager/releases/latest/download/latest.json
```

## latest.json erzeugen (inkl. SHA256)

Der GitHub-Workflow erzeugt `latest.json` automatisch. Für einen manuellen Build von v2.1.0 kann das Manifest so erzeugt werden:

```bash
python -m updater.generate_manifest \
  --version 2.1.0 \
  --release-tag v2.1.0 \
  --channel stable \
  --windows-zip dist/BudgetManager-v2.1.0-portable.zip \
  --linux-zip dist/BudgetManager-v2.1.0-portable.zip \
  --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.1.0 \
  --out latest.json
```

GitHub-Release-Assets für v2.1.0:

- `BudgetManager-v2.1.0-portable.zip`
- `BudgetManager-v2.1.0-windows.exe`
- `BudgetManager-v2.1.0-linux`
- `BudgetManager_Setup_2.1.0.exe`
- `latest.json`

Der Updater prüft die SHA256-Werte aus dem Manifest fail-closed. Fehlt ein Hash oder passt er nicht, wird das Update abgelehnt.

## Nutzung (manuell)

1. Prüfen, Download und Staging:

```bash
python -m updater.check_update
```

2. App schließen.

3. Update anwenden:

```bash
python -m updater.apply_update
```

Unter Windows muss die gestartete EXE geschlossen sein, sonst kann sie nicht ersetzt werden.
