# BudgetManager v2.0.8 — Merge- & Release-Bericht

Stand: 2026-06-13
Ergebnis: **`BudgetManager_Source_2_0_8.zip`** — releasefähig bis auf den manuellen
Windows-/Linux-Smoke-Test.

---

## 1. Ausgangslage: zwei 2.0.7-Pakete verglichen

| Aspekt | `…2_0_7` (A) | `…2_0_7_release_ready` (B) |
|---|---|---|
| Zahlenformat-Schema | `ch / eu / us` (FR fällt mit DE zusammen) | **`swiss / german / french / anglo`** (FR eigenständig, schmales Leerz.) |
| Geld-Helfer | — | **`set_money_locale`, `preferred_number_format_for_currency`** |
| QLocale FR | de_DE | **fr_FR** |
| Erststart-Dialog | Tag-Frage entfernt | **bevorzugter Buchungstag wird abgefragt** |
| Update-Dialog | Basis | **GUI-Modus, Auto-Apply, mehr Fehlerausgaben** |
| Test-Override | — | **`BUDGETMANAGER_APP_DIR`** (für Tests/Tools) |
| Release-Integritätstest | — | **`tests/test_release_integrity.py`** |
| `dau_first_run_check.py` | ruft `delete_category(strategy=…)` → **API existiert nicht → defekt** | ruft `delete_category_safely(...)` → **korrekt** |
| Locale-Schlüssel | 1735 | 1733 (2 fehlten) |

**Befund:** `category_model.py` ist in beiden Paketen **identisch** und bietet nur
`delete_category_safely()` / `delete_categories_safely()`. Damit ist der DAU-Check in
Paket A nachweislich defekt. Paket B ist die sauberere, funktionsreichere Basis.

## 2. Merge-Entscheidung

- **Basis = B (`release_ready`).**
- Aus A übernommen: `docs/DAU_TEST_ERSTSTART.md` (einziges sinnvolles Unikat).
- In B ergänzt: die 2 fehlenden Locale-Schlüssel `catdel.opt_cascade_all` und
  `dlg.create_account` (de/en/fr) → wieder **1735 identische Schlüssel** je Sprache.
- Die beiden `locales/*.json` der Pakete unterschieden sich praktisch nur in der
  **Sortierung** (gleiche Inhalte) — kein inhaltlicher Konflikt.

## 3. Fachliche Änderung: Fixkosten-Vorschlagsregel

> „0 darf nie allein der Auslöser für einen Budgetvorschlag mit Fixkosten sein.
>  Fixkosten können inkrementell sein.“ — **Ja, das ist korrekt und war eine echte Lücke.**

Die zentrale Engine `model/budget_suggestion_engine.py` kannte das `is_fix`-Flag bisher
nicht. Ihr 0-Reduktionspfad senkt das Budget einer Kategorie, wenn ≥ 6 Monate in Folge
keine Buchung vorlag. Für **Fixkosten** (z. B. jährliche Versicherung, quartalsweise
Steuer) ist genau das falsch: monatelang 0, dann eine große Buchung — eine Senkung kurz
vor der Fälligkeit wäre ein Fehlvorschlag.

**Umgesetzt nach Gegenvergleich:**
- Die erste v2.0.8-Lösung war zu schwach: sobald **ein** echter Buchungsmonat
  vorhanden war, konnten 0-Monate wieder in die Median-Analyse fallen.
- Deshalb wurde die robustere v2.0.7-Forecast-Fix-Logik zurückgeführt und erweitert.
- Neuer Parameter `respect_fixed_costs: bool = True`.
- Fixed-like Erkennung: `is_fix=1` **oder** `is_recurring=1`.
- Für fixed-like Kategorien:
  - 0-Monate werden für Budgetänderungen ignoriert (`active_only=True`).
  - Es braucht mindestens 3 echte Buchungsmonate (> 0).
  - Der 0-Reduktionspfad wird übersprungen.
  - Wiederholte echte Überschreitungen dürfen weiterhin erhöhen.
  - Wiederholte echte niedrigere Buchungen dürfen senken, aber nicht bloß wegen 0.
- Flexible Kategorien bleiben unverändert flexibel: 0 kann Teil eines wiederholten
  Musters sein, z. B. Hobby 40 mit 20/30/0.
- Nach Rundung wird die Mindeständerung nochmals geprüft, damit Rundungsrauschen
  keinen Vorschlag erzeugt.

**Bewusst nicht angefasst:** Die Buchungs-Deduplizierung im Tracking
(`exists_in_month` → `skipped_existing`) blockt eine Kategorie, sobald sie im Monat
einmal gebucht ist. „Inkrementelle“ Mehrfachbuchungen pro Monat (z. B. Miete in zwei
Raten) wären eine separate Erweiterung mit Doppelbuchungs-Risiko — hier nicht geändert,
weil die Aussage sich klar auf den **Vorschlag** bezog. Hinweis bewusst dokumentiert.

## 4. Verifikation (Container)

```text
compileall .                         → 0 Syntaxfehler
JSON-Gültigkeit                      → alle gültig
i18n-Parität de/en/fr                → 3 × 1735 Schlüssel, identisch
tools/i18n_audit.py                  → [OK] keine hardcoded UI-Strings
tools/dau_first_run_check.py         → ALLE CHECKS BESTANDEN ✅
tools/sync_version.py --check        → synchron: 2.0.8
pytest -q                           → 34 passed, 1 skipped
  • tests/test_core.py                 22/22
  • tests/test_release_integrity.py     3/3
  • tests/test_fixed_cost_suggestion.py 8/8
Paket-Hygiene                        → kein users.json/.enc/__pycache__/.pyc/.pytest_cache
```

### Regressionstest-Details (`tests/test_fixed_cost_suggestion.py`)

- **T1** Fixkosten, Budget > 0, 0 Buchungen → **kein Vorschlag**.
- **T2** Gleiche Kategorie als **Nicht-Fixkosten** → 0-Reduktion liefert Vorschlag
  (zeigt: nur Fixkosten sind geschützt).
- **T3** Fixkosten mit dauerhaft über Budget liegenden Buchungen → **Erhöhungsvorschlag**.
- **T4** `respect_fixed_costs=False` hebt den Schutz auf (Steuerbarkeit).
- **T5** Versicherung 200 Budget, einmal 250 gebucht und danach 0 → **kein Senken**.
- **T6** `is_recurring=1` ohne `is_fix` wird ebenfalls geschützt.
- **T7** Hobby 40, Ist 20/30/0/20/30/0 → **flexibler Senkungsvorschlag erlaubt**.
- **T8** Nahrungsmittel 400, Ist 450/350 → **kein Vorschlag**.

## 5. Version

Zentral via `tools/sync_version.py` auf **2.0.8** gesetzt: `app_info.py`,
`version.json`, `latest.json.template`, `docs/latest.json.template`,
`installer/budgetmanager_setup.iss`. Projektordner: `BudgetManager_Source_2_0_8`.

## 6. Offen (nur außerhalb des Containers möglich)

1. Realer Windows-/Linux-Smoke-Test (App-Start, Erststart, Kategorie löschen/umbenennen,
   Fix/Wiederkehrend buchen, Update-Dialog).
2. Qt-Übersetzungskataloge im Build prüfen (`tools/verify_qt_translations.py`;
   `BudgetManager.spec` warnt bei fehlenden `qtbase_*.qm`).
3. Installer bauen (Inno Setup), Versionsanzeige `2.0.8` gegenchecken.
4. Git-Tag `v2.0.8` setzen, `latest.json` aus Template mit echten SHA256 füllen.

## 7. Status der Wunschfunktionen (alle bereits vorhanden, verifiziert)

Wiederkehrende Transaktionen (Soll-Datum) · Fixkosten-Check „schon gebucht?“ ·
optionale Auswahlliste fehlender Buchungen · Budgetwarnungen · Tags/Labels ·
Undo/Redo · Favoriten · Sparziele · Backup/Restore · DB-Reset auf Standard ·
Erscheinungsmanager (Theme-Editor/Farbprofile) · Windows-Installer (Inno Setup) ·
Update-Tool. Implementiert in den entsprechenden Modulen/Dialogen — kein Neubau nötig,
nur die obige Fixkosten-Korrektheit ergänzt.
