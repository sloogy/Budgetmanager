# Portable Updater (GitHub Releases)

Stand: BudgetManager v2.2.68

Der Updater ersetzt Programmdateien, aber keine Nutzerdaten:

- `data/` bleibt erhalten: DB, Settings, Backups.
- `updates/` bleibt erhalten: Staging, Cache und Rollback-Backups.
- Windows-Installer-Installationen bevorzugen das Asset `windows_installer` mit Typ `installer`.
- Portable Windows/Linux behalten die Plattform-Keys `windows` und `linux` als portable ZIPs.

## Manifest-URL (Default)

Der Updater erwartet ein `latest.json` im neuesten GitHub Release:

```text
https://github.com/sloogy/Budgetmanager/releases/latest/download/latest.json
```

## Updater-Vertrag

In `latest.json` müssen diese Plattform-Keys update-sicher bleiben:

```json
{
  "assets": {
    "windows": { "type": "portable-zip" },
    "linux": { "type": "portable-zip" },
    "windows_installer": { "type": "installer" }
  }
}
```

Wichtig: `windows_installer` muss exakt den Typ `installer` haben. Der Updater erkennt nur so, dass eine Setup-EXE gestaged und später im Installer-Update-Modus gestartet werden muss.

Die portablen ZIPs müssen stabile Binary-Namen enthalten:

- Windows: `BudgetManager.exe`
- Linux: `BudgetManager`

## Vollständige Release-Artefakte erzeugen

Bevorzugt über den GitHub-Workflow `.github/workflows/build.yml`.

Lokal kann das Paketieren so getestet werden:

```bash
python tools/build_release_assets.py   --version 2.2.22   --release-tag v2.2.22   --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.2.22   --windows-build-dir artifacts/windows   --linux-build-dir artifacts/linux   --out-dir release_assets
```

Das erzeugt:

- `BudgetManager-v2.2.22-portable-windows.zip`
- `BudgetManager-v2.2.22-portable-linux.zip`
- `BudgetManager-v2.2.22-windows.exe`
- `BudgetManager-v2.2.22-linux`
- `BudgetManager_Setup_2.2.22.exe`, falls der Installer vorhanden ist.
- `BudgetManager_Setup_2.2.22.zip`, falls der Installer vorhanden ist.
- `latest.json`
- `SHA256SUMS.txt`

Der direkte Installer bleibt für Nutzer verfügbar. Der Installer-ZIP ist der Windows-Download-Fallback, wenn Browser oder SmartScreen die direkte EXE blockieren.

## Nur latest.json erzeugen

Der kleine Manifest-Helfer bleibt für einfache ZIP-Releases erhalten:

```bash
python -m updater.generate_manifest   --version 2.2.22   --release-tag v2.2.22   --channel stable   --windows-zip dist/BudgetManager-v2.2.22-portable-windows.zip   --linux-zip dist/BudgetManager-v2.2.22-portable-linux.zip   --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.2.22   --out latest.json
```

Der Updater prüft die SHA256-Werte aus dem Manifest fail-closed. Fehlt ein Hash oder passt er nicht, wird das Update abgelehnt.

## Nutzung manuell

1. Prüfen, Download und Staging:

```bash
python -m updater.check_update
```

2. App schließen.

3. Update anwenden:

```bash
python -m updater.apply_update
```

Unter Windows startet die App dafür einen externen Helfer, damit `BudgetManager.exe` nicht während des laufenden Prozesses überschrieben werden muss.
