# BudgetManager v2.0.9 — Stabilitäts- & Release-Readiness-Report

Stand: 14.06.2026
Basis: 2.0.8 „SETUP BACKUP IMPORT FIXED" (aktueller Arbeitsstand, **nicht** der ältere 2.0.8-RELEASE-Schnitt)
Ergebnis: **Release Ready** im Container — offen bleibt nur der manuelle Windows-/Linux-Smoke-Test mit echter GUI.

---

## 1. Was in 2.0.9 gemacht wurde

### Version zentral gezogen
- `app_info.py`: `APP_VERSION = 2.0.9`, Release-Datum `14. Juni 2026`.
- Über `tools/sync_version.py` propagiert auf `version.json`, `installer/budgetmanager_setup.iss`, `latest.json.template`, `docs/latest.json.template`.
- User-sichtbare Doku/Header auf 2.0.9: `README.md`, `README_INSTALLATION.md`, `FEATURES.md`, `updater/README.md`, `updater/generate_manifest.py`, `views/budget_entry_dialog.py` (Header).
- **Bewusst NICHT geändert**: historische Regressions-Kommentare und Test-Docstrings, die „v2.0.8" als Fehlerzeitpunkt korrekt benennen.
- `VERSION_INFO.txt` neu geschrieben, `CHANGELOG.md` um einen 2.0.9-Eintrag ergänzt.

### Zurückgemergte Dateien (waren im FIXED-Stand verloren)
- `.github/workflows/build.yml` — CI-Build; zieht die Version aus dem Git-Tag (`${TAG#v}`), versionsagnostisch, kein Hardcoding nötig.
- `.gitignore`
- `data/.gitkeep`

---

## 2. Statische Verifikation (alles grün)

| Prüfung | Ergebnis |
|---|---|
| `compileall` gesamter Baum | 0 Syntaxfehler |
| JSON-Validität aller Locales | gültig |
| i18n: de = en = fr identisch | 1833 Keys, vollständig deckungsgleich |
| i18n: benutzte `tr()`/`trf()`-Keys im Code | 1452 benutzt, **0 fehlend** |
| `sync_version.py --check` | „synchron: 2.0.9" |
| Packaging-Hygiene | 0 verbotene Artefakte (keine `users.json`, `.enc`, `.db`, Caches, `.bmr`) |
| Import-Smoke (alle Qt-freien Module) | 25 OK, 0 Fehler |

---

## 3. Headless-Funktionstest der Datenschicht — 34/34 PASS

Das gesamte `model/`-Layer ist Qt-frei und wurde gegen echte temporäre SQLite-DBs durch den vollen Lebenszyklus gefahren.

| # | Bereich | Geprüft | Ergebnis |
|---|---|---|---|
| 1 | DB & Migrationen | Schema-Aufbau, **Idempotenz** (2. Migrationslauf), `tracking.source`-Spalte | PASS |
| 2 | Kategorien | `ensure_defaults` (44 Defaults), anlegen (fix/recurring/flex), Flags | PASS |
| 3 | Budget | set/get, `get_matrix`, Summen | PASS |
| 4 | Tracking & Quellen | manual/auto_fixcost/auto_recurring persistiert; **Fixkosten-bereits-gebucht** (`exists_in_month`); **Dropdown-Ranking zählt nur manuelle Buchungen** | PASS |
| 5 | Favoriten | pin/unpin, `is_favorite`, Reihenfolge (`move_up`) | PASS |
| 6 | Sparziele | create, `add_progress`, `progress_percent`, `release`, Undo kennt Sparziel-Ops | PASS |
| 7 | Wiederkehrend | `get_pending_bookings` (Fälligkeit), **bereits-gebucht reduziert Fälligkeit**, `toggle_active` | PASS |
| 8 | **Budget-Vorschläge** | **Fixkosten 250/0/0 → KEIN Senkungsvorschlag**; Gegenprobe: flexible Kategorie mit echter 3-Monats-Überschreitung → Vorschlag möglich | PASS |
| 9 | Undo/Redo | `rename_and_cascade` (Kategorie + Tracking), Undo stellt her, Redo reproduziert | PASS |
| 10 | Reassign-Merge | `delete_category_safely(reassign)` additiv (100+30=130), kein UNIQUE-Crash, Altkategorie gelöscht | PASS |
| 11 | Backup/Management | `create_backup`, `get_available_backups`, `get_database_statistics`, `source_db_name` im Bundle | PASS |
| 12 | typ_constants | `normalize_typ`-Aliase, `rest_sign`-Konvention | PASS |

### Zwei positive Nebenbefunde während des Tests
- Der **Rename-Kollisionsschutz** greift korrekt: Umbenennen auf einen bereits existierenden Kategorienamen wird mit `categories.category_exists` abgelehnt (kein stiller Datenkonflikt).
- Die **Vorschlags-Engine ist bewusst konservativ**: Der unvollständige aktuelle Monat wird übersprungen (`use_current_month=False`), und es braucht `months_back` *abgeschlossene* Monate. Das verhindert verfrühte Vorschläge aus laufenden Monaten — gewolltes, dokumentiertes Verhalten.

---

## 4. Grenzen dieses Tests

Im Container ist **kein PySide6** und **kein Netz** verfügbar. Daher **nicht** abgedeckt:
- GUI-Klickpfade (Cockpit, Dialoge, Drag & Drop, Theme-/Erscheinungsmanager-Rendering).
- `pytest`-Suite (braucht PySide6) — laut deinem Changelog zuletzt „50 passed, 2 skipped".
- Gebauter Windows-Installer / EXE-Start, Single-Instance-Verhalten am echten Prozess, Updater gegen echtes `latest.json`.

Diese Punkte bleiben als manuelle Schritte vor dem öffentlichen Release.

---

## 5. Offene Schritte vor dem GitHub-Release

1. `python -m pytest -q` auf einer Umgebung mit PySide6.
2. Windows-Smoke-Test (Installer bauen, EXE starten, Erststart-Assistent, Backup-Restore, Cockpit, Kategorie löschen/umbenennen, Update-Dialog).
3. Linux-Smoke-Test mit frischem Datenordner.
4. `latest.json` aus Template mit echten Release-URLs und SHA256 füllen.
5. Git-Tag `v2.0.9` setzen → löst den CI-Build aus.

---

## 6. Urteil

**v2.0.9 ist im Rahmen des hier Prüfbaren release-ready.** Datenschicht, Syntax, i18n, Versionssync und Packaging sind verifiziert grün; die zurückgemergten CI-/Hygiene-Dateien sind drin; die Kern-2.0.8-Logik (Fixkosten-0-Monate-Regel, Tracking-Quellen, Reassign-Merge, Undo/Redo-Cascade) ist headless bestätigt. Es verbleibt ausschließlich der manuelle GUI-/Build-Smoke-Test.
