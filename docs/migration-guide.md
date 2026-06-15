# Migration Guide — BudgetManager v2.0.8

## Grundsatz

BudgetManager speichert Nutzdaten lokal in SQLite. Migrationen laufen beim Start automatisch über `model/migrations.py`.

## Vor einem Update

1. App schließen.
2. Ordner `data/` sichern oder Backup-Funktion der App nutzen.
3. Neue Programmdateien einspielen.
4. App starten und prüfen, ob Budget, Kategorien und Tracking geladen werden.

## Portable-Update

Bei einem Portable-Update bleibt der bestehende `data/`-Ordner erhalten. Ersetze nur Programmdateien, nicht die Nutzdaten.

## Installer-Update

Der Installer überschreibt bestehende `data/budgetmanager_settings.json` nicht. Sprache, Währung und bevorzugter Buchungstag werden nur beim Erst-Setup geschrieben.

## Settings-Migration

`settings.py` merged geladene Einstellungen über aktuelle Defaults. Dadurch bleiben ältere Teil-Settings kompatibel und neue Keys wie `budget_overview_drag_drop` erhalten sinnvolle Standardwerte.

## Versionsprüfung

```bash
python tools/sync_version.py --check
```
