# BudgetManager v2.2.6 – X10THINK KILLCRITIC

## Vorgehen
Ausgangspunkt war der releasefähige Stand **v2.2.5 POT/TAG/FILTER FIXED**. Statt nur die
bestehenden Audits erneut laufen zu lassen (die alle grün waren), wurde tiefer geprüft:

1. **Vollständige Gate-Batterie als Baseline** (alle grün): compileall, sync --check,
   i18n-Parität (de=en=fr, 2285 Keys), DAU-Erststart, Release-Logik-Audit 100/0,
   Deep-Logic-Audit 500/3500/0, Lint.
2. **Tiefenlese der Kernlogik** entlang der Feature-Liste: Wiederkehrende/Fixkosten-
   Fälligkeit, POT/Rückstellung, Vorschlagsengine inkl. strikter Lernmodus-Trennung,
   Undo/Redo inkl. Sparziel-Kopplung, Sparziel-Grenzen, Tags, Backup/Reset, Warnungen.
3. **Neuer Prüfmechanismus – i18n-Vollständigkeit:** Alle 1787 literalen `tr()`/`trf()`-
   Keys im Code gegen `de.json` geprüft → 0 fehlende Keys (keine sichtbaren Roh-Keys in der UI).
4. **Cascade-Vollständigkeit:** Alle namensreferenzierenden Tabellen aus dem Schema
   ermittelt (8 Stück) und gegen die Rename-/Reassign-/Delete-Pfade abgeglichen.
5. **Randomisierte Invarianten-Harness – 100 Loops (10 Themen × 10):** Property-Tests
   gegen die echten Modelle (Fälligkeit, POT, Vorschlag, Undo/Redo, Sparziel-Grenzen,
   Tags, Rename-Cascade, Budget-Summen, Tracking-Summen, Reset).

## Gefundene und behobene Punkte

### 1. FIX (Datenkonsistenz) – Lernzustand verwaiste bei Rename/Reassign
`tracking_learning_state` ist die **achte** namensreferenzierende Tabelle (gekeyt auf
`typ`+`category`). Der **Delete-Pfad** räumte sie bereits korrekt auf, aber **Rename** und
**Reassign** führten sie nicht mit – sie nutzten handgeschriebene SQL-Listen, in denen
genau diese Tabelle fehlte.

Folge vor dem Fix: Nach einem Rename ging die **Nutzerentscheidung**
(beobachten/ignoriert/vertagt/beendet) verloren, die Kategorie tauchte unter dem **neuen
Namen wieder im Lernmodus** auf, und die alte Zeile blieb als Karteileiche stehen.

Behoben in drei Pfaden, konfliktfrei (`UPDATE OR IGNORE` + `DELETE`, PK ist `typ,category`):
- `model/category_model.py` → `rename_and_cascade`
- `model/category_model.py` → `_move_category_text_references` (Reassign)
- `model/undo_redo_model.py` → `_rename_cascade` (+ `tracking_learning_state` in Undo-Whitelist)

### 2. HÄRTUNG (Defense-in-Depth) – Tag-Verknüpfungen beim Buchungs-Löschen
`TrackingModel.delete` verließ sich für das Aufräumen von `entry_tags` allein auf die
FK-Regel `ON DELETE CASCADE`, die nur bei `PRAGMA foreign_keys=ON` greift. Produktiv war
das korrekt (crypto.py/database.py setzen das Pragma). Auf einer ohne das Pragma
geöffneten Verbindung wären jedoch verwaiste Tag-Links entstanden. Jetzt räumt der Delete
`entry_tags` **zusätzlich explizit** auf – analog zum Kategorie-Delete.
- `model/tracking_model.py` → `delete`

## Nachgewiesen unberührt (bewusst NICHT verändert)
- **Strikte Trennung Vorschlagsengine ↔ Lernmodus:** Die Engine referenziert Lernmodus
  nirgends; Lernvorschläge entstehen weiterhin ausschließlich für Kategorien **ohne
  positives Jahresbudget** und nur als `direction="initial"`.
- **POT-Topf-Cap = höchster Budgetwert** (nicht Summe der Monatsbudgets).
- **POT- vs. laufende-Monatsausgabe-Heuristik:** 3-Monatsfenster mit 2 aktiven Monaten
  bleibt Topf.
- **Sparziel-Vorzeichenlogik** bei Undo+Redo (kein doppelter Betrag).
- **Data-Start-Boundary** der Vorschlagsengine.

## Geänderte Dateien
- `model/category_model.py`
- `model/undo_redo_model.py`
- `model/tracking_model.py`
- `tests/test_release_226_learning_state_cascade.py` (neu, 5 Tests)
- Versions-/Doku-Stempel: `app_info.py` (2.2.6), `CHANGELOG.md`, `VERSION_INFO.txt`,
  `FEATURES.md`, `requirements.lock`, diverse `docs/*` und `updater/*`
  (jeweils nur der aktuelle Versionsstempel; Historien unangetastet).

## Tests / Gates
- Versions-Sync: **PASS** (2.2.6 synchron)
- Compile: **PASS**
- i18n-Audit: **PASS** (de=en=fr, je 2285 Keys, 0 Fehler)
- i18n-Vollständigkeit: **PASS** (1787/1787 verwendete Keys existieren)
- DAU-Erststart: **PASS**
- Release-Logik-Audit: **100 Loops, 0 Findings**
- Deep-Logic-Audit: **500 Loops / 3500 Checks, 0 Findings**
- Lint-/Release-Prozedur: **PASS**
- pytest headless: **362 passed, 2 skipped** (vorher 357 + 5 neue Regressionstests)
- KILLCRITIC-Invarianten-Harness: **100 Loops (10 Themen × 10), 0 Findings**

## Einschränkung
Die 2 übersprungenen Tests sind Qt/PySide-GUI-Smoke-Tests, die in der headless
Prüf-Umgebung nicht laufen können (Ausführung auf Fedora/Windows durch dich).

## Einschätzung
Source-Release ist releasefähig als:

**v2.2.6 KILLCRITIC – LEARNING-STATE CASCADE FIXED**
