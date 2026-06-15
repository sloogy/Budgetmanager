# Release-Checkliste — BudgetManager v2.0.8

Dieser Quellstand ist **release-ready**. Alle im Container prüfbaren Schritte sind grün.
Es folgen nur noch die Schritte, die eine echte Build-/Windows-Umgebung brauchen.

## Status im Quellpaket (bereits erledigt)

- [x] Version zentral auf **2.0.8** (`app_info.py`) und synchron in `version.json`,
      `latest.json.template`, `docs/latest.json.template`,
      `installer/budgetmanager_setup.iss` (`tools/sync_version.py --check` = synchron).
- [x] Fixkosten-/Forecast-Korrektur in `model/budget_suggestion_engine.py`
      (0-Monate senken Fixkosten/wiederkehrende Kategorien nicht; ≥ 3 echte
      Buchungsmonate; `active_only`-Abweichungen; `is_recurring` geschützt).
- [x] Tests: 34 passed (22 core + 8 Fixkosten + 4 Release-Integrität);
      GUI-Smoke wird ohne PySide6 übersprungen.
- [x] i18n: de/en/fr je 1735 identische Schlüssel; `i18n_audit` ohne Hardcoding.
- [x] DAU-Erststart-Check bestanden.
- [x] Paket-Hygiene: kein `users.json`, keine `*.enc`, kein `__pycache__`/`.pyc`/`.pytest_cache`.

## Manuelle Schritte vor Veröffentlichung

1. **Windows-/Linux-Smoke-Test** des gebauten Pakets:
   App-Start → Erststart (Sprache/Währung/Zahlenformat/Tag) → Budgetwert →
   Buchung → Kategorie umbenennen/löschen (Reassign) → Fix/Wiederkehrend buchen →
   Update-Dialog öffnen.

2. **Qt-Übersetzungen im Build** prüfen:
   ```
   python tools/verify_qt_translations.py
   ```
   (`BudgetManager.spec` warnt, falls `qtbase_de.qm`/`qtbase_fr.qm` fehlen.)

3. **Builds erzeugen** (PyInstaller) und Installer bauen (Inno Setup,
   `installer/budgetmanager_setup.iss`). Versionsanzeige **2.0.8** gegenchecken.

4. **`latest.json` mit echten SHA256 erzeugen** (ersetzt die `PUT_SHA256_HERE`
   aus dem Template):
   ```
   python -m updater.generate_manifest \
     --version 2.0.8 \
     --release-tag v2.0.8 \
     --channel stable \
     --windows-zip dist/BudgetManager-v2.0.8-portable.zip \
     --linux-zip   dist/BudgetManager-v2.0.8-portable.zip \
     --base-url https://github.com/sloogy/Budgetmanager/releases/download/v2.0.8 \
     --out latest.json
   ```

5. **Git-Tag setzen und veröffentlichen:**
   ```
   git add -A
   git commit -m "Release v2.0.8 — Fixkosten-Forecast-Fix + Clean Merge"
   git tag -a v2.0.8 -m "BudgetManager v2.0.8"
   git push origin main --tags
   ```

6. **GitHub-Release** anlegen, Assets hochladen (Portable-ZIP/EXE + `latest.json`).
   Die `url`-Pfade im `latest.json` müssen exakt zu den hochgeladenen Asset-Namen passen.

## Nach dem Release verifizieren

- Updater einer 2.0.7-Installation findet 2.0.8 und installiert sauber.
- About-Dialog/Fenstertitel zeigt 2.0.8.
