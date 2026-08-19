# BudgetManager v2.2.25 – KILLCRITIC X10THINK 10.000 (Usability-Vollaudit + Enterprise-Merge)

**Datum:** 17. Juli 2026
**Basis:** Merge aus `ENTERPRISE_10000_AUDITED` (Upload) und `FINAL_AUDITED` (Final-Release-Audit-Zweig)
**Ergebnis:** **10 000 Loops, 326 908 Checks, 10 000 PASS, 0 WARN, 0 FAIL** – Negativ-Gegenprobe 4/4 erkannt.
**Matrix:** `KILLCRITIC_X10THINK_10000_MATRIX_v2_2_25.csv`

## 1. Merge der beiden 2.2.25-Zweige

Beide Zweige entstanden parallel aus v2.2.24 und waren komplementär:

| Zweig | Kernbeiträge |
|---|---|
| ENTERPRISE_10000 (Basis) | 3 Datenintegritätsfixes (feste Tags bei Kategorienwechsel, Tag-Restore bei Undo/Redo, Buchungsquelle), 204 modale Infos → nicht-modales Toast-System (`utils/notifications.py`), Tab-Ketten (`utils/accessibility.py`, 20 Dialogklassen), `enterprise_release_audit_10000.py` (112 000 Checks), Bandit-Differenzsperre, CI-Ausbau (Plattform-Gates, pip-audit, Dependabot), Updater-Randfix `_update_marker.json` |
| FINAL_AUDITED (rückportiert) | Ultimo-Bugfix `fixed_cost_due` (Soll-Tag 29–31 in kurzen Monaten), 6 SQL-Härtungen (Whitelist-/Identifier-Guards inkl. `target_table` und JSON-Spaltenfilter im Undo-Modell), `final_release_audit_1000.py` (20 855 Checks, AST-Fixpunkt-SQL, Injektions-Gegenprobe) |

Der Statusleisten-Teilfix des FINAL-Zweigs wurde bewusst **nicht** übernommen – das flächendeckende Toast-System der Basis ersetzt ihn vollständig (0 modale Informationsdialoge); die zwei zugehörigen i18n-Titel-Keys sind wieder aktiv (Parität de/en/fr je 2313).

## 2. Im Audit gefundene und behobene Produktfehler

### 2.1 Verwaiste Tag-Zuordnungen nach Undo/Redo (Kernfix)

`UndoRedoModel._delete_by_id` löschte nur die Buchung, nicht deren `entry_tags`-Zeilen. Das Schema trägt zwar `ON DELETE CASCADE`, SQLite erzwingt Fremdschlüssel jedoch nur bei aktivem `PRAGMA foreign_keys` – das die App-Verbindung nicht setzt. Deterministische Reproduktion: anlegen → löschen → Undo → Redo hinterließ `tracking=[]`, aber `entry_tags=[(1,1)]`.

**Fix:** Der Undo-/Redo-Löschpfad entfernt `entry_tags` für `tracking`-Zeilen jetzt explizit (Symmetrie zu `_restore_tracking_tags`). **Migration 17** bereinigt Bestandswaisen aus älteren Datenbanken idempotent. Verifiziert: 0 Waisen nach Redo, erneutes Undo stellt die Tags vollständig wieder her.

### 2.2 Falscher Menü-Mnemonic (de/en/fr)

`menu.backup` enthielt ein unmaskiertes literales `&` („&Backup & Wiederherstellen..."), wodurch Qt einen zweiten, falschen Tastatur-Mnemonic erzeugte. In allen drei Sprachen als `&&` maskiert.

### 2.3 Theme-Editor ohne sichtbaren Schließen-Weg

`ThemeEditorDialog` war nur über Esc/Fenster-X schließbar. Ergänzt: `QDialogButtonBox` mit Schließen-Button (`btn.close`, RejectRole) in einem neuen äußeren Layout; die Tab-Ketten-Registrierung war bereits vorhanden.

### 2.4 Anleitungslücken (de/en/fr)

Die Benutzeranleitungen deckten Cockpit, Tags, Konten/Benutzer und Monatsabschluss nicht ab und hatten kein Erststart-Kapitel; die Lernmodus-Unterkapitel 5.1/5.2 standen hinter Kapitel 8. Ergänzt in allen drei Sprachen: „Erststart in vier Schritten" (direkt nach dem Titel, inkl. Hinweis auf nicht-blockierende Statusmeldungen) und die Kapitel 9–12 (Cockpit/Reiter/Favoriten, Tags inkl. Regeln für feste Kategorie-Tags und Undo-Erhalt, Konten und Benutzer, Monatsabschluss); 5.1/5.2 hinter Kapitel 5 verschoben.

## 3. Die zehn Domänen (X10THINK: ~10 Perspektiven je Loop)

| Domäne | Gegenstand | Art |
|---|---|---|
| k1 | Erststart-/Assistenten-Pfad, i18n der Schritte, Guide-/DAU-Doku | statisch |
| k2 | Kernbuchungs-Lebenszyklus: Kategorie → fester Tag → Buchung → Filter-Orakel → Undo/Redo mit Tag- und Quellenerhalt, Waisen-Zählung, `_cols`-Guard | **echte DB je Loop** |
| k3 | Backup-Bundle: create → verify → Byte-Flip im DB-Member → inhaltsverändertes Member → gefälschtes Manifest | **echte Bundles je Loop** |
| k4 | Guide-Abdeckung der Kernbegriffe in de/en/fr | statisch |
| k5 | Hilfe-Wiki (`HELP_TOPICS`): eindeutige IDs, drei Sprachen, keine Roh-Keys, Suchindex | funktional |
| k6 | UI-Textqualität über alle 3×2313 Werte (Ränder, Doppel-Leerzeichen, Platzhalter-Balance, Mnemonics, Platzhaltertexte) | statisch |
| k7 | Update-Pfad: `find_staged_root` inkl. Marker-Randfall, flaches Layout, `__MACOSX`; Guide-Erwähnung | **funktional** |
| k8 | Jede `tr()`/`trf()`-Referenz existiert dreisprachig; Toasts nie für destruktive Aktionen ohne vorherige modale Bestätigung | statisch |
| k9 | Dialog-Invarianten: Schließbarkeit, Tab-Ketten-Registrierung komplexer Dialoge, keine modalen Infos | AST |
| k10 | Regressionsschild: Ultimo-Klemmung (3 Stichdaten, echte Aufrufe), SQL-Guards (echte Aufrufe), Tag-Restore-Verdrahtung, Quellen-Fallback, 0 modale Infos, Parität 2313, Nachweis-Artefakte | funktional |

## 4. Kalibrierungsentscheide (als legitim eingestufte Muster)

Der Audit meldete zunächst Muster, die sich bei Einzelprüfung als bewusste Gestaltung erwiesen. Sie sind jetzt als Regeln kodiert, damit echte Fehler weiter auffallen:

- **Struktur-Einrückungen** wie `'  ↳ {value_0}'` (Unterkategorien) und `'✓  OK'` (Symbol-Padding).
- **Ausrichtungsblöcke** (mehrzeilige Summen-Tooltips mit `─`-Trennlinien und Label-Wert-Spalten).
- **Satzfragmente zur Konkatenation** mit dreisprachig identischem Rand-Leerzeichen (z. B. `' wirklich löschen?'`, `'…Budget-Einträge '`).
- **Dreisprachig konsistente Doppel-Leerzeichen** (Schritt-Trenner in `update.hint_one_click`, Beispiel-Abstände in `number_format.*`): Ein echter Tippfehler wäre sprachspezifisch; genau das prüft die Regel – die Gegenprobe mit einem nur-deutschen Doppel-Leerzeichen wird erkannt.
- **Erfolgs-Toast nach modaler Bestätigung** (z. B. „Benutzer gelöscht" nach `QMessageBox.question`) entspricht der Meldungsrichtlinie und ist kein Verstoß.
- **Deflate-Randbits:** Bit-Flips in Padding-/`BFINAL`-Bits eines komprimierten Members können das Dekompressat unverändert lassen – dann ist die Integrität faktisch intakt und `verify_bundle` schweigt korrekt. Das k3-Orakel wertet einen stillen Flip nur dann als Fehler, wenn sich der Inhalt tatsächlich geändert hat; zusätzlich MUSS ein real verändertes DB-Member und ein gefälschter Manifest-`sha256` jeweils `BundleIntegrityError` auslösen (beides in jedem Loop geprüft).
- **Ellipsen-Bestand** `...` vs. `…` (46:70) ist gemischt, aber kein Standardverstoß; eine Vereinheitlichung würde beim nächsten i18n-Sync der `auto.*`-Keys zurückdriften und bleibt bewusste Zukunftsaufgabe.

## 5. Negativ-Gegenprobe (Schärfenachweis)

Vier absichtliche Verstöße wurden injiziert und alle erkannt: sprachspezifischer Doppel-Leerzeichen-Tippfehler (k6), `tr()`-Aufruf auf nicht existenten Schlüssel (k8), modaler Informationsdialog in einer View (k9), entfernte `target_table`-Whitelist (k10). Alle Injektionen wurden rückstandsfrei zurückgebaut (Locales-Parität und Quelltexte verifiziert). k2 und k3 sind zusätzlich selbstschärfend: Sie führen die echten Produktpfade aus und schlugen vor den Fixes nachweislich an.

## 6. Grenzen der Prüfumgebung

GUI-Interaktionstests (echtes Klicken/Fokusreihenfolge zur Laufzeit), `pytest`-Volllauf mit PySide6, `bandit`/`pip-audit` und die Plattform-Gates (Wayland/Windows-Skalierung, Installer/Updater-E2E) laufen wie im Enterprise-Zweig verdrahtet auf dem Zielsystem bzw. in der CI. Die hier ausgeführten Prüfungen sind headless-vollständig; Qt-gebundene Tests wurden auf korrektes `importorskip`-Gating geprüft.
