# BudgetManager v2.1.0 – Windows-Download & Updater-Safe Fix

## Ziel

Der Windows-Installer soll auch dann aus GitHub nutzbar sein, wenn Browser oder Windows SmartScreen den direkten `.exe`-Download blockieren. Gleichzeitig darf die vorhandene Updater-Logik für Installer, Standalone-EXE und portable ZIPs nicht beschädigt werden.

## Umgesetzt

- Neuer Release-Paketierer: `tools/build_release_assets.py`.
- GitHub Actions nutzt den Paketierer statt einer langen Inline-ZIP-Logik.
- Release erzeugt getrennte Plattform-ZIPs:
  - `BudgetManager-v2.1.0-portable-windows.zip`
  - `BudgetManager-v2.1.0-portable-linux.zip`
- Windows-Installer wird zusätzlich als ZIP bereitgestellt:
  - `BudgetManager_Setup_2.1.0.exe`
  - `BudgetManager_Setup_2.1.0.zip`
- `SHA256SUMS.txt` wird automatisch erzeugt.
- `latest.json.template` und `docs/latest.json.template` wurden auf die neuen Artefakte synchronisiert.
- Installations-/Updater-Dokumentation wurde aktualisiert.

## Updater-Sicherheit

Die Plattform-Keys bleiben update-sicher:

```json
"windows": { "type": "portable-zip" }
"linux":   { "type": "portable-zip" }
```

Zusätzlich bleibt der Installer-Pfad korrekt:

```json
"windows_installer": { "type": "installer" }
```

Wichtig: Der Typ darf nicht `installer-exe` heißen, weil `updater.check_update` nur bei exakt `installer` die Setup-EXE als Installer staged. Diese Stelle wurde bewusst so umgesetzt, dass der Installer nicht fälschlich als normale `BudgetManager.exe` behandelt wird.

## Release-Artefakte

Bei Tag `v2.1.0` lädt GitHub Actions hoch:

- `BudgetManager-v2.1.0-windows.exe`
- `BudgetManager-v2.1.0-linux`
- `BudgetManager-v2.1.0-portable-windows.zip`
- `BudgetManager-v2.1.0-portable-linux.zip`
- `BudgetManager_Setup_2.1.0.exe`
- `BudgetManager_Setup_2.1.0.zip`
- `latest.json`
- `SHA256SUMS.txt`

## Lokale Validierung

- `python tools/sync_version.py --check`
- `python -m compileall -q . -x '_attic|__pycache__|build|dist|release_assets'`
- `python tools/build_release_assets.py` mit Dummy-Artefakten
- Manifest-/ZIP-Inhalte geprüft
- Updater-Asset-Typen geprüft
