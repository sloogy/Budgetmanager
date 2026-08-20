# Migration Guide — BudgetManager v2.2.62

## Grundsatz

BudgetManager speichert Nutzdaten lokal in SQLite. Migrationen laufen beim Start automatisch über `model/migrations.py`. Beim Öffnen einer verschlüsselten Datenbank wird vor einer Migration ein Sicherheitsbackup angelegt.

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

`settings.py` merged geladene Einstellungen über aktuelle Defaults. Dadurch bleiben ältere Teil-Settings kompatibel und neue Keys erhalten sinnvolle Standardwerte.

## Wichtig für v2.2.13

- Unter Wayland nutzt die App standardmäßig `xcb`, um Qt-Textinput-Abstürze zu vermeiden.
- Budgetwarnungen und Cockpit-Aktionen sind Teil des aktuellen Release-Stands.
- Restore-Fehler durch falschen Wiederherstellungscode führen nicht mehr in eine Sackgasse; der Assistent setzt sauber zurück.
- Defekte oder nicht mehr öffnende Konten blockieren die App nicht mehr dauerhaft, sondern bieten eine Selbstheilung an.
- Alte Zwischenstandsberichte sind aus dem Release-Paket entfernt; die Historie steht im `CHANGELOG.md`.

## Versionsprüfung

```bash
python tools/sync_version.py --check
```
