# Fix: Backup-Import im geführten Starter

Stand: v2.0.8 · 14. Juni 2026

## Problem

Im geführten Setup-Assistenten war der Button **Backup wiederherstellen** falsch verdrahtet.
Der Code versuchte, `BackupRestoreDialog` mit einem nicht vorhandenen Direktpfad-Parameter zu öffnen. Dadurch konnte der Restore aus dem Starter abbrechen, bevor der eigentliche Import lief.

Zusätzlich war der Erststart-Import von `.bmr`-Backups für Quick-Benutzer unnötig sperrig: Obwohl `.bmr`-Backups `users.json` enthalten können, wurde dieser vorhandene Quick-DB-Key nicht genutzt. Der Nutzer wurde dann nach einem Restore-Key gefragt, obwohl das Backup die nötigen Kontometadaten enthielt.

## Umsetzung

- `BackupRestoreDialog` hat jetzt eine öffentliche Methode `restore_external_path(path)`.
- Der Setup-Assistent ruft den Backup-Dialog mit vollständigem Kontext auf:
  - aktive SQLite-Verbindung,
  - Settings,
  - verschlüsselte Session,
  - aktiver Benutzer.
- Danach wird das ausgewählte Backup über `restore_external_path()` wiederhergestellt.
- Restore-Optionen für `settings.json` und `users.json` werden auch bei direkter Pfad-Wiederherstellung abgefragt.
- Der Erststart-Import von `.bmr` kann Quick-Backups automatisch über die enthaltene `users.json` entschlüsseln und in den neu angelegten Benutzer re-verschlüsseln.
- Neue `.bmr`-Manifeste speichern zusätzlich den ursprünglichen DB-Dateinamen (`source_db_name`), damit künftige Imports genauer zugeordnet werden können.

## Tests

```text
python -m compileall -q .
python tools/sync_version.py --check
pytest -q
```

Ergebnis:

```text
Alle Versionsdateien synchron: 2.0.8
50 passed, 2 skipped
```
