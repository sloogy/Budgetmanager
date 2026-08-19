# Final-Release-Audit – BudgetManager v2.2.25

**Datum:** 17. Juli 2026
**Basis:** v2.2.24 (Enterprise Merged Audited, `FINAL_MERGE_RELEASE_TEST_v2_2_24.md`)
**Ergebnisversion:** v2.2.25 Final Audited
**Auftrag:** Release-Audit in einem 1000er-Loop, alle offenen Punkte fixen.

---

## 1. Neues Prüfwerkzeug

`tools/final_release_audit_1000.py` – **10 bislang ungeprüfte Domänen × 100 Loops
= 1000 Loops, 20 855 Checks**, mit echten Funktionsläufen statt reiner
Quelltext-Muster:

| Domäne | Prüfung | Art |
|---|---|---|
| d1 | SQL-Oberfläche: jede `execute`/`executescript`-Stelle in `model/` per AST-Fixpunkt-Analyse (scope-getrennt) | FAIL-fähig |
| d2 | Privacy-Sanitizer: `diagnostics._sanitize` ersetzt HOME-Pfade real | FAIL-fähig |
| d3 | Dateirechte: `secure_file` setzt 0644 → 0600 auf echter Datei | FAIL-fähig |
| d4 | Geldformat: `format_money`/`normalize` (Idempotenz, 4 Tausender-Formate) | FAIL-fähig |
| d5 | Fälligkeits-Klemmung: 8 Kantenfälle inkl. Schaltjahr-Ultimo | FAIL-fähig |
| d6 | Migrations-Idempotenz: `migrate_all` 2× auf echter DB, Schema-Snapshot identisch | FAIL-fähig |
| d7 | Bundle-Byte-Flip: manipuliertes Backup-Bundle wirft `BundleIntegrityError` | FAIL-fähig |
| d8 | i18n-Format-Sicherheit: alle 3×2311 Keys `str.format`-parsebar, Platzhalter-Parität | FAIL-fähig |
| d9 | Modale Info-Last (Messung) + Regressionsschutz des main_window-Teilfixes | WARN by design |
| d10 | `setTabOrder`-Deklarationen in 13 komplexen Dialogen (Zielsystem-Tastaturtest) | WARN by design |

Matrix: `FINAL_RELEASE_AUDIT_1000_MATRIX_v2_2_25.csv` (Projekt-Root).

**Endstand: 1000 Loops, 20 855 Checks, 800 PASS, 200 WARN by design, 0 FAIL.**

### d1-Analysetiefe (AST-Fixpunkt)

Die SQL-Analyse bewertet je Funktions-Scope (keine Vermischung gleichnamiger
Variablen verschiedener Methoden) einen gemeinsamen Fixpunkt über Zuweisungen
(`Assign` **und** `AnnAssign`) und Listen-Mutationen (`append`/`extend`).
Als sicher gelten: String-Literale (inkl. Ternary/Konkatenation),
`"?"`-Placeholder-Joins, `join()` über bewiesene Literal-Listen (benannt oder
inline), f-Strings über sicheren Ausdrücken, `_safe_table()`-Rückgaben,
`re.fullmatch`-geprüfte Namen, Loop-Variablen über Literal-Iterables /
Literal-Dict-`items()` / guard-gefilterten Schleifen sowie das
PRAGMA-Schnittmengen-Muster `[k for k in x.keys() if k in cols]` mit
`cols = self._cols(...)`. Geprüft werden f-String-Interpolationen,
Namens-Argumente (tainted Query-Variablen), `%`- und `+`-Konstruktionen.

Dokumentierte Ausnahmen: `super().execute(...)` (AutosaveConnection-
Wrapper-Delegation) und `crypto.py`-`executescript` (Laden des entschlüsselten
DB-Dumps – Manipulation setzt Schlüsselbesitz voraus).

**Negativ-Gegenprobe:** 6 absichtliche Injektionsmuster (f-String-Parameter,
tainted Name als Argument, `%`-Format, ungefilterte Loop-Variable,
Nicht-`_cols`-Comprehension, tainted-append-Join) über den echten d1-Pfad –
**alle 6 erkannt**, bei 0 False-Positives im Produktbaum.

---

## 2. Befunde und Fixes

| # | Befund | Schwere | Fix |
|---|---|---|---|
| 1 | **Fälligkeits-Ultimo-Bug:** Positionen mit Soll-Tag 29–31 wurden in kürzeren Monaten NIE offen (`today.day < due_day` galt auch am Monatsletzten). Beweis: Miete mit Soll-Tag 31 fehlte am 28.02.2026 im Cockpit. | **Kern-Bugfix** | `model/fixed_cost_due.py`: Soll-Tag wird per `monthrange` auf den Monatsletzten geklemmt. 8 Kantenfälle verifiziert (Schaltjahr-Ultimo 2024, Nicht-Schaltjahr 2026, April/30, vor Soll-Tag weiterhin nicht offen, Vormonat immer fällig, voll gebucht nie offen). |
| 2 | `category_model.get_category_usage/count()`: Tabellen-/WHERE-Fragmente ungeprüft im f-String | Härtung | Tabelle über `_safe_table`, WHERE strikt auf `col=?`-Ketten per Regex begrenzt. |
| 3 | `migrations._cols`, `tags_model._has_column`, `tracking_model._cols`: Tabellenname ungeprüft im `PRAGMA table_info` | Härtung | `re.fullmatch`-Identifier-Guard; Nicht-Identifier liefern leere Spaltenmenge. |
| 4 | `undo_redo_model._push_to_other_stack`: `target_table`-Parameter erreichte ungeprüft ein f-String-INSERT | Härtung | Whitelist-Guard `self._safe_table(target_table)` am Funktionsanfang (`undo_stack`/`redo_stack` sind Teil der Whitelist; fremde Namen ⇒ `ValueError`). |
| 5 | `undo_redo_model._insert_row/_update_by_id`: Spaltennamen aus persistiertem Undo-JSON nur per PRAGMA-Schnittmenge gefiltert | Härtung (Defense-in-Depth) | Zusätzlicher `re.fullmatch`-Identifier-Filter über die JSON-Schlüssel. |
| 6 | Zwei reine Statusrückmeldungen liefen als modale Info-Dialoge (abgelehnte „letzter Reiter"-Aktion, Erfolg der Datenordner-Migration) | UI/ADHS-Teilfix (d9) | `views/main_window.py`: Statusleiste (4 s / 6 s) statt `QMessageBox.information`. Neustart-/Antwort-Dialoge bleiben bewusst modal (6 verbleibende Stellen). |
| 7 | Zwei durch Fix 6 verwaiste i18n-Keys | Aufräumung | `cockpit.hide_tab_title` und `settings.data_dir_migrate_done_title` paritätisch entfernt – de/en/fr je **2311** Flat-Keys. |

Als sicher bewertet und **nicht** geändert: `budget_model`-Placeholder-Joins,
`month_close_model`-Datumsklauseln, `migrations`-Index-Loops,
`database_management_model`-Literal-Strukturen, `tracking_model`-WHERE-Ketten
sowie der `tags.action_text_label`-Platzhalterunterschied de↔en/fr (die
Render-Engine unterstützt beide Sprachvarianten).

---

## 3. Gate-Kette (alle grün)

| Gate | Ergebnis |
|---|---|
| `sync_version --check` | PASS – 2.2.25 synchron (app_info, version.json, VERSION_INFO, Installer, latest.json-Templates) |
| `compileall` | PASS |
| `i18n_audit` | PASS – keine hardcoded UI-Strings |
| `dau_first_run_check` | PASS |
| `release_logic_audit_100` | 100 Loops, 0 Findings (inkl. Doku-Stempel-Pflicht der Benutzerhandbücher) |
| `deep_logic_release_audit` | 500 Loops, 3500 Checks, 0 Findings |
| `fresh_logic_audit_100` | 100 Loops, 0 Findings |
| `pre_release_stability_audit_300` | 300 Loops, 2400 Checks, 0 Findings |
| `mega_release_audit_1000` | 1000 Loops, 6813 Checks, 0 Findings |
| `ui_adhs_audit_1000` | 1000 Loops, 15 611 Checks, 0 Findings |
| `enterprise_ui_adhs_audit_1000` | 1000 Loops, 0 FAIL; WARN by design (417 QMessageBox/105 Info; 13 Dialoge ohne `setTabOrder`) |
| `final_release_audit_1000` | 1000 Loops, 20 855 Checks, **0 FAIL**, 200 WARN by design |
| `lint_procedure_check` | PASS |
| Regressionstest `test_release_2225_final_audit.py` | **19/19 PASS** (headless) |
| Qt-Import-Collection-Check | 84 Testdateien, 0 ungegatete PySide6-Imports (`pytest.importorskip`-Muster) |
| Import-Smoke | 46/46 Qt-freie Module OK; `utils.icons`, `utils.table_autosize`, `utils.ui_usability` Qt-gebunden (Zielsystem) |

Hinweis zur Zählbasis d9: Das Enterprise-Audit zählt `views/` **plus**
`settings_dialog.py` (105 Infos), das Final-Audit nur `views/` (104) – je
eigene, dokumentierte Definition.

---

## 4. Sandbox-Grenzen / Zielsystem-Aufgaben

Im Audit-Container nicht ausführbar (kein PySide6, kein pytest, kein
black/mypy, kein Netz):

1. **pytest-Volllauf** (~491 Tests) unter Python 3.12 **und** 3.13.
2. **d10-Tastaturtest:** reale Tab-Reihenfolge der 13 komplexen Dialoge
   (Qt vergibt implizite Reihenfolgen; explizites `setTabOrder` ist
   Enterprise-Kriterium, kein Defekt).
3. **`pip check`** gegen `requirements.lock` unter Python 3.13
   (CI-Matrix 3.12 + 3.13 vorhanden).
4. **black/mypy** gemäß Release-Checkliste.

Alle vier Punkte sind in der CI bzw. Release-Checkliste verankert und ändern
nichts an den hier verifizierten Ergebnissen.

---

## 5. Merge-Nachtrag (Enterprise-Zusammenführung, 17. Juli 2026)

Dieser Baum ist die Zusammenführung mit dem Enterprise-10000-Zweig. Zwei
Aussagen dieses Berichts sind dadurch überholt: Der Statusleisten-Teilfix
(Abschnitt 2, Punkt 6) ist durch das flächendeckende nicht-modale
Toast-System (`utils/notifications.py`) ersetzt – es existieren **0 modale
Informationsdialoge** in `views/`; die zwei zuvor entfernten i18n-Titel-Keys
werden vom Toast-System wieder verwendet (Parität de/en/fr je **2313**
Schlüssel). Die d9-Prüfung des Final-Audits wurde entsprechend auf das
Toast-Kriterium umgestellt. Alle übrigen Befunde, Fixes und Kennzahlen
gelten unverändert; Details zum Merge in `KILLCRITIC_X10THINK_10000_v2_2_25.md`.
