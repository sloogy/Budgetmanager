# Portable Updater (GitHub Releases)

Dieser Updater ist **für die portable Version** gedacht:
- **`data/` bleibt immer erhalten** (DB, Settings, Backups)
- Update ersetzt nur Programm-Dateien

## Manifest-URL (Default)

Der Updater erwartet ein `latest.json` im GitHub Release (Asset):
- `https://github.com/sloogy/Budgetmanager/releases/latest/download/latest.json`

## latest.json erzeugen (inkl. SHA256)

Wenn du ein neues Release gebaut hast (portable ZIP), generierst du das Manifest so:

```bash
python -m updater.generate_manifest \
  --version 0.2.0.4 \
  --release-tag v0.2.0.4 \
  --channel stable \
  --windows-zip dist/BudgetManager_PORTABLE_WINDOWS.zip \
  --linux-zip dist/BudgetManager_PORTABLE_LINUX.zip \
  --base-url https://github.com/<user>/<repo>/releases/download/v0.2.0.4 \
  --out latest.json
```

Danach lädst du folgende Assets ins GitHub Release hoch:
- `BudgetManager_PORTABLE_*.zip`
- `latest.json`

Der Updater prüft dann automatisch die **SHA256** aus dem Manifest.

## Nutzung (manuell, "still")

1) **Prüfen & Download + Staging** (App kann dabei laufen):

```bash
python -m updater.check_update
```

2) **App schließen**

3) **Update anwenden** (ersetzt Dateien, lässt `data/` in Ruhe):

```bash
python -m updater.apply_update
```

> Hinweis: Für Windows-Binary-Releases muss die EXE geschlossen sein, sonst kann sie nicht ersetzt werden.
