# Unabhängiges Deep-Audit v2.2.29 und Fix-Report v2.2.30 (DEEP_AUDIT_FIXES)

Datum: 18. Juli 2026
Basis: BudgetManager v2.2.29 (RELEASE_GATE_RESYNC)

## 1. Auftrag

Erneutes Vollaudit (Fehleranalyse, Enterprise-, UI-, Usability-Audit) auf
der ausgelieferten v2.2.29. Da die interne Werkzeugbatterie bereits grün
war, lag der Schwerpunkt auf unabhängigen Prüfungen, die die vorhandenen
Audits (release_logic_100, deep_logic_500, enterprise_10000,
killcritic_x10think_10000, ui_adhs_1000 u. a.) NICHT abdecken.

## 2. Unabhängige Prüfungen und Ergebnisse

| Prüfung | Methode | Ergebnis |
| --- | --- | --- |
| i18n-Platzhalter-Parität | `str.Formatter`-Extraktion aller Format-Felder je Key über de/en/fr (i18n_audit prüft nur Key-Parität) | 1 Divergenz `tags.action_text_label` — kein Defekt: `render_action_text` akzeptiert deutsche UND englische Namen; Labels bewusst lokalisiert. Folge-Hinweis B (s. u.) |
| Migrations-Idempotenz | `migrate_all` zweifach auf frischer DB, Schema-/Versionsvergleich, `PRAGMA foreign_key_check` | Schema stabil, 17 Tabellen, 0 FK-Verletzungen |
| Datums-Fuzz Fälligkeit | `is_open_this_month` über Jahre 2024/2026/2100 × 12 Monate × Stichtage {1, 15, letzter} × Soll-Tage {None, 0, 1, 15, 28–31, 99, "x"}; Erwartung unabhängig nachgerechnet | 0 Fehler (inkl. Klemme 29–31, Nicht-Schaltjahr 2100, Vergangenheits-/Teilbuchungsregeln) |
| Datums-Fuzz Soll-Datum | `_calculate_booking_date` für day_of_month 1–31 × 36 Monate | 0 Fehler |
| Undo/Redo-Fuzz | 400 Zufallsschritte (Add/Update/Delete/Undo/Redo) gegen Schattenmodell mit Verlaufsschnitten | 0 Abweichungen; 0 verwaiste entry_tags; FK sauber |
| Money-Roundtrip | `format_money`→`parse_money` für 10 Beträge × alle `NUMBER_FORMAT_CODES`; Cross-Format- und Mülleingaben | 0 Fehler; Müll (`abc`, `12,3,4`) sauber via ValueError abgelehnt |
| Backup/Restore E2E | Bundle erzeugen (0600), Byte-Flip im DB-Member, Manifest ohne SHA-256, `_read_limited`-Limit | Manipulation → `BundleIntegrityError`; Legacy → abgelehnt, Upgrade-Pfad erzeugt verifizierbares Bundle; Limits fail-closed |
| Krypto-Domänentrennung | `hash_password` vs. `derive_key_from_secret` funktional | getrennt (PW_VERIFY_CONTEXT), Legacy-Erkennung greift; dabei Befund 2 entdeckt |
| Secret-Logging | Regex-Scan aller `logger.*`-Aufrufe auf password/pin/db_key/pw_hash/… | 0 Treffer |
| Excepthook/Ressourcen | Quellprüfung `main.py` | Globaler Handler mit Dialog+Log vorhanden; einziges `open()` ohne `with` ist der absichtlich prozesslebenslange faulthandler-Handle |
| Worker-Muster | `_ExcelParseWorker`/QThread-Verdrahtung | korrekt: Worker emittiert nur Signale, GUI/DB nur im GUI-Thread, Lifecycle sauber |
| Destruktive Dialog-Defaults | Regex-Scan aller `QMessageBox.question` in views/ | 3 bewusste Yes-Defaults im Backup-Dialog (durch automatisches `before_restore`-Vollbackup abgesichert; zwei davon nicht destruktiv); 2 fehlende explizite Defaults im Theme-Editor → Hinweis A |
| Suggestion-Engine | 5 Szenarien: 6 Monate Überschreitung, Fixkosten exakt, Fixkosten echt überschritten, Unterschreitung, Monat vor Datenstart | exakt nach Spezifikation (Erhöhung gedämpft, Fixschutz, Senkung, None vor Datenstart) |

## 3. Befunde und Fixes

### Befund 2 (Robustheit Login, niedrig): TypeError statt Ablehnung bei korruptem pw_hash

**Symptom:** Ein von Hand editierter oder korrupter `pw_hash` in
users.json (Nicht-ASCII oder falscher Typ) führt in
`hmac.compare_digest` zu `TypeError`. `UserModel.authenticate` fing nur
`ValueError` — der Login crashte statt abzulehnen. Erreichbar nur durch
externe Manipulation der 0600-geschützten Datei; dennoch verletzt es das
Fail-closed-Prinzip.

**Fix:** Neuer Guard `model.crypto._is_comparable_stored_hash` (beide
gültigen Hash-Formate sind ASCII-Hex; alles andere ist per Definition
ungültig). `verify_password` und `is_legacy_password_hash` lehnen nicht
vergleichbare Werte fail-closed mit `False` ab; der timing-sichere
Vergleichspfad für gültige Hashes bleibt unverändert.
`UserModel.authenticate` fängt zusätzlich `TypeError` (Gürtel und
Hosenträger). Verifiziert: gültige Hashes, Legacy-Hashes und
Falsch-Passwörter verhalten sich exakt wie zuvor.

### Hinweis A (UI-Konsistenz): Theme-Editor-Bestätigungen ohne expliziten Default

Löschen/Zurücksetzen eines Farbprofils nutzte `QMessageBox.question`
ohne Default-Button; Qt macht damit implizit „Ja" zum Enter-Default.
Fix: explizites `QMessageBox.No` bei beiden Bestätigungen — konsistent
zum Hausstandard aller übrigen destruktiven Abfragen.

### Hinweis B (UI-Doku): Monats-Platzhalter nicht dokumentiert

`tags.action_text_label` nannte `{month}`/`{monat}` nicht, obwohl
`render_action_text` sie unterstützt. Fix: in allen drei Locales
ergänzt; Diff = exakt eine Zeile je Datei, Key-Parität unverändert
(de=en=fr).

## 4. Regressionstests

`tests/test_release_2230_deep_audit_fixes.py` (10 Tests): Guard-Matrix
(gültig/leer/None/bytes/Nicht-ASCII/int), korrupte Hashes in beiden
Verifikationsfunktionen, Legacy-Erkennung nach Guard unverändert,
`authenticate` mit korruptem pw_hash liefert weiterhin den db_key
(intakter wrapped_db_key) statt zu crashen, synthetischer TypeError im
Legacy-Pfad wird abgefangen, No-Default-Quellprüfung Theme-Editor,
Monats-Platzhalter in allen Locales, Render-Funktionsprobe aller sieben
dokumentierten Platzhalter inkl. Rohtext-Fallback bei unbekannten.

## 5. Abschlussstand v2.2.30

Komplette Gate-Batterie grün (Container-Einschränkungen bandit/PySide6
wie dokumentiert, CI-gedeckt). Headless-Suite: 576 PASS. Versions-Sweep
vollständig (app_info, sync_version-Ziele, drei Lockfile-Stempel,
README-Trio, elf Doku-Dateien, Hilfe-HTML, Updater-Doku,
Versionspin-Tests); Historie unangetastet. ZIP auf entpackter Kopie
empirisch verifiziert.
