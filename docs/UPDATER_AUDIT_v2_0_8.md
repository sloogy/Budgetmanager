# Updater-Audit & Verifikation — BudgetManager v2.0.8 RELEASE

Stand: 14. Juni 2026
Paket: `BudgetManager_Source_2_0_8_RELEASE.zip` (Basis: `…RELEASE_FIXED` + ein zusätzlicher Updater-Fix)

## 1. Gemeldeter Blocker — verifiziert behoben

**Update-Dialog-Freischaltung** (`updater/check_update.py`): Nach erfolgreichem
Download/Staging wird wieder ein strukturiertes Ergebnis nach
`updates/last_check.json` geschrieben (`available:true`, `staged:true`, `remote`,
`release_tag`, `asset_type`, `asset_url`).

Gegengeprüft gegen die GUI: `views/update_dialog.py` schaltet den Installations-
button bei `res.get("available") and res.get("staged")` frei (Zeile 163) — exakt
die Keys, die der Fix schreibt. Der „bereits gestaged"-Pfad schreibt das
Erfolgsergebnis ebenfalls. Der Regressionstest
`test_update_check_writes_success_result_for_gui` läuft echt durch (mockt
Manifest/Download/Staging und prüft das geschriebene Ergebnis).

## 2. Vollständiges Updater-Audit (end-to-end)

Geprüft: `check_update.py`, `common.py`, `apply_update.py`, `update_dialog.py`,
`main.py`-Dispatch. Solide befunden:

- **Versionsvergleich** (`is_newer`, `latest_staged_version`) nutzt
  `packaging.version` → `2.0.10 > 2.0.9` korrekt (kein Lexikografie-Bug).
- **CLI-Dispatch**: `main()` ruft `_run_updater_mode(sys.argv)` und returnt bei
  `--check-update`/`--apply-update` **vor** `QApplication(...)` → keine zweite GUI,
  kein zusätzlicher Datei-Lock.
- **Windows-Apply**: externer Batch-Helfer wartet per `tasklist`-Schleife, bis die
  EXE beendet ist, kopiert dann per `robocopy` (schließt `data`/`updates` aus,
  Retries überbrücken kurze Sperren), startet neu, löscht sich selbst.
  `CREATE_NEW_CONSOLE` ohne `DETACHED_PROCESS` (bewusst, sichtbares Fenster).
- **ZIP-Extraktion** (`safe_extract_zip`) mit ZipSlip-Schutz.
- **Rollback-Backup** vor Apply; `data/` bleibt unangetastet.
- **last_check.json**: schreiben/lesen/löschen konsistent; Lesefehler → `{}`.

## 3. Zusätzlich gefundener Fehler — behoben

**`apply_update` wendete die falsche Version an.** Bisher wählte
`latest_staged_version()` blind die **höchste** vorhandene Staging-Version. Da alte
Staging-Ordner **nie aufgeräumt** werden, ist folgender Fall erreichbar:

> Ein Beta-Rest `staging/2.1.0` liegt herum, während der Stable-Kanal gerade
> `2.0.9` heruntergeladen und vorbereitet hat. `apply_update` hätte **2.1.0**
> angewendet statt der gestageten 2.0.9.

Empirisch reproduziert (Beleg im Container-Lauf).

**Fix:**
- `check_update.py` schreibt zusätzlich `staged_version` in `last_check.json`.
- `apply_update.py` bevorzugt diese Version (neue Funktion
  `target_staged_version()`) und prüft, dass deren Staging-Ordner Inhalt hat.
- **Sicherer Fallback** auf die höchste vorhandene Version, falls kein/kein
  gültiges Prüfergebnis vorliegt (mit Warn-Log).
- Regressionstest `test_apply_uses_checked_version_not_highest_stale_staging`
  (geprüfte Version gewinnt; Fallback ohne `last_check`; Fallback bei leerer
  bevorzugter Version).

> Hinweis (kein Blocker): Staging-Ordner werden weiterhin nicht automatisch
> bereinigt. Optional könnte `apply_update` nach Erfolg alte `staging/*` löschen.
> Bewusst nicht gemacht, um die Apply-Logik minimal/risikoarm zu halten.

## 4. Finale Verifikation (Container)

```text
compileall .                         → 0 Syntaxfehler · alle JSON gültig
i18n-Parität de/en/fr                → 3 × 1735 identisch
tools/i18n_audit.py                  → [OK] keine hardcoded UI-Strings
tools/dau_first_run_check.py         → ALLE CHECKS BESTANDEN
tools/sync_version.py --check        → synchron: 2.0.8
Tests (real-pytest-Äquivalent)       → 35 passed, 1 skipped
  • test_core.py                       22
  • test_fixed_cost_suggestion.py       8
  • test_release_integrity.py           5  (inkl. 2 Updater-Tests)
  • test_gui_smoke.py                   übersprungen (kein PySide6)
Paket-Hygiene                        → kein users.json/.enc/__pycache__/.pyc/updates/
```

## 5. Verdikt

`BudgetManager_Source_2_0_8_RELEASE.zip` ist aus Source-/Container-Sicht der
**finale Release-Kandidat**. Der gemeldete Updater-Blocker ist behoben, ein
weiterer latenter Updater-Fehler gefunden und behoben, der gesamte Update-Pfad
auditiert.

**Offen (nur außerhalb des Containers):** realer Windows-/Linux-Smoke-Test inkl.
echtem Update-Durchlauf (Check → Freischalten → Apply → Neustart),
`verify_qt_translations.py` im Build, Installer-Bau, `latest.json` mit echten
SHA256, Git-Tag `v2.0.8`. Schritte stehen in `docs/RELEASE_CHECKLIST_v2_0_8.md`.
