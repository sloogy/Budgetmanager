# BudgetManager v2.2.7 – X10THINK KILLCRITIC RESTORE-CODE HARDENED

## Ausgangspunkt
Basis war **v2.2.6 KILLCRITIC – LEARNING-STATE CASCADE FIXED**. Die dort behobenen Punkte bleiben erhalten:
- `tracking_learning_state` folgt Kategorie-Rename/Reassign.
- `TrackingModel.delete` räumt `entry_tags` explizit auf.
- 100er Invarianten-Harness, Release-Logik-Audit und Deep-Logic-Audit waren in v2.2.6 grün.

## Akuter Nutzerbefund
Beim Einlesen bestimmter Backups war kein Code mehr nötig. Ursache: Normale `.bmr`-Backups konnten `users.json` enthalten. Bei Quick-Usern steht darin historisch der lokale `db_key_b64`. Damit lagen Datenbank **und** Schlüsselmaterial im selben Backup. Ein altes/komfortables `.bmr` konnte dadurch beim Erststart-Import ohne Restore-Key geöffnet werden.

## Gefundene und behobene Punkte

### 1. FIX SECURITY – Normale Backups enthalten keine `users.json` mehr
Geändert in:
- `views/backup_restore_dialog.py`
- `views/main_window.py`
- `settings_dialog.py`

Betroffene Pfade:
- Manuelles Backup im Backup/Restore-Dialog
- Safety-Backup vor Restore/Reset
- Auto-Backup beim Start
- Manuelles Backup aus den Einstellungen

Neu: Backups enthalten weiterhin Datenbank und sichere Settings, aber **keine lokale Kontoregistrierung / kein lokales Schlüsselmaterial** mehr.

### 2. FIX SECURITY – Erststart-Import nutzt `users.json` nie mehr als Ersatzschlüssel
Geändert in:
- `views/startup_wizard.py`

Vorher:
- Alte `.bmr`-Backups mit `users.json` wurden bei Quick-Usern automatisch über `db_key_b64` entschlüsselt.

Neu:
- `users.json` wird beim Import nicht mehr als Schlüsselquelle gelesen.
- Fremdes verschlüsseltes Backup verlangt den Restore-Key.
- Ohne Restore-Key wird sauber abgebrochen und der temporär angelegte Benutzer zurückgerollt.

### 3. FIX SECURITY/UX – Normaler Restore stellt Benutzerkonten nicht mehr wieder her
Geändert in:
- `views/backup_restore_dialog.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`

Neu:
- Alte `.bmr`-Backups mit `users.json` zeigen einen Sicherheitshinweis.
- Der Dialog setzt `restore_users = False` hart.
- Die normale UI kann nicht mehr unbemerkt von PIN/Passwort auf Quick/kein Code umstellen.

### 4. Regressionen
Geändert/neu:
- `tests/test_startup_restore_regression.py`
- `tests/test_release_227_restore_code_hardening.py`

Abgesichert:
- Normale Backup-Callsites setzen kein `users_json_path` mehr.
- Startup-Restore enthält keine `_candidate_db_keys_from_bundle_users`-Logik mehr.
- Restore-Dialog fragt nicht mehr nach `dlg.restore_users_question` und erzwingt `restore_users=False`.
- Alter Quick-Backup-Fall: ohne Restore-Key Abbruch, mit Restore-Key erfolgreicher Import.

## 100er Loop / Kombinationsprüfung
Zusätzlich zu den bestehenden Release-Audits wurde ein Restore-Code-Security-Audit mit **100 Kombinationen** gefahren:

Achsen:
- Backup-Quelle: manuell, Auto-Backup, Einstellungen, Safety-Backup, altes Legacy-Bundle
- Format: `.bmr`, `.enc`, `.db`
- Restore-Pfad: normaler Restore, Erststart-Import, Backup-Erstellung
- `users.json` vorhanden/nicht vorhanden
- aktiver Schlüssel passt/passt nicht

Ergebnis:
- **100 Loops / 0 Findings**
- Invariante: Normale Backups enthalten kein `users_json_path`.
- Invariante: Startup-Import nutzt nur Restore-Key, nie Bundle-User-Keys.
- Invariante: Restore-Dialog stellt `users.json` nicht wieder her.

## Tests / Gates

Bestanden:
- `python tools/sync_version.py --check` → PASS, 2.2.7 synchron
- `python -m compileall -q .` → PASS
- `python tools/i18n_audit.py` → PASS, de=en=fr je 2286 Keys, keine fehlenden referenzierten Keys, keine verdächtigen hardcoded UI-Strings
- `python tools/dau_first_run_check.py` → PASS
- `python tools/release_logic_audit_100.py` → PASS, 100 Loops, 0 Findings
- `python tools/deep_logic_release_audit.py` → PASS, 500 Loops / 3500 Checks, 0 Findings
- `python tools/lint_procedure_check.py` nach `clean_release_tree` → PASS
- Restore-Code-Security-Audit → PASS, 100 Loops, 0 Findings
- Pytest segmentiert:
  - Gruppe 1: 138 passed, 1 skipped
  - Gruppe 2: 130 passed
  - Gruppe 3: 97 passed, 1 skipped

Einschränkung:
- `python tools/verify_qt_translations.py` konnte in dieser Sandbox nicht grün laufen, weil kein Qt-Übersetzungsverzeichnis (`qtbase_*.qm`) vorhanden ist. Das ist ein Umgebungs-/Build-Asset-Thema, kein Codefehler. Auf deiner Fedora/Windows-Dev-Umgebung bitte zusätzlich prüfen.

## Geänderte Dateien
- `app_info.py`
- `version.json`
- `latest.json.template`
- `docs/latest.json.template`
- `VERSION_INFO.txt`
- `CHANGELOG.md`
- `FEATURES.md`
- `README.md`
- `README_INSTALLATION.md`
- `requirements.lock`
- `views/startup_wizard.py`
- `views/backup_restore_dialog.py`
- `views/main_window.py`
- `settings_dialog.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`
- `tests/test_startup_restore_regression.py`
- `tests/test_release_227_restore_code_hardening.py`
- diverse aktive `docs/*` und `updater/*` Versionsstempel auf 2.2.7

## Releasefähigkeit

**Source-Release: releasefähig als v2.2.7 RESTORE-CODE HARDENED.**

Wichtig für deinen konkreten Befund:
- Neue Backups enthalten keine `users.json` mehr.
- Alte Backups, die noch `users.json` enthalten, öffnen fremde verschlüsselte Datenbanken nicht mehr ohne Restore-Key.
- Ein Restore kann die lokale Anmeldung nicht mehr heimlich auf „kein Code / Quick” zurücksetzen.

Empfehlung vor GitHub-Release:
1. Auf Fedora einmal GUI-Smoke starten und altes `.bmr` importieren: Restore-Key muss abgefragt werden.
2. Neues Backup erstellen und per ZIP prüfen: `users.json` darf nicht enthalten sein.
3. Windows/Installer-Build laufen lassen, inklusive `verify_qt_translations.py` in der echten Qt-Buildumgebung.
