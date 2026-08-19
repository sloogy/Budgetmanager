# BudgetManager v2.2.17 – LOGIC FIXES (Logikanalyse)

## Rahmen
Basis: **v2.2.16 UNIFY TOOLS**. Auftrag: das Programm auf Logikfehler
analysieren und diese beheben. Da die bestehenden Audits (Logik 100, Deep
500/3500, KILLCRITIC 100) grün sind, wurde mit **frischem Blick** geprüft:
die Nahtstellen der jüngsten Konsolidierung (Edit-Modus, Fixkosten-Dialog,
Reset-Pfad) und bislang ungeprüfte Randfälle der Datenschicht.

## Methodik
1. **Neues Invarianten-Werkzeug** `tools/fresh_logic_audit_100.py`
   (10 Themen × 10 Loops, reine Datenschicht, headless):
   source-Erhalt bei `tracking.update`, Tags nach Kategorie-Wechsel im Edit,
   Sparziel-Synchronisation bei Typwechsel savings↔expenses, Grenzen-Guard
   VOR jeder Änderung, Undo/Redo eines Updates inkl. `source`,
   Fälligkeitstag-Klemmung 29–31 (Februar!), leere Details bleiben leer,
   Edit ohne Typ/Kategorie-Wechsel lässt Sparziel-Stände unangetastet,
   `set_entry_tags`-Idempotenz.
2. Gezielte Code-Inspektion der v2.2.16-Nahtstellen.
3. Verdachtsprüfung in unabhängigen Bereichen (`copy_year`/`is_pot`,
   `requires_code(None)`).

## Ergebnis der Datenschicht-Prüfung
**0 Findings in 100 Loops** – die Kernlogik (Buchen, Bearbeiten, Sparziele,
Undo/Redo, Tags, Kalender) ist konsistent. Insbesondere bestätigt:
`update` erhält die Buchungsquelle, Sparziel-Überbuchung beim Typwechsel wird
geblockt **bevor** irgendetwas geändert wird, und Undo stellt alle Spalten
inkl. `source` wieder her.

## Gefundene und behobene Fehler (Oberflächen-Logik)

### 🔴 F1 – Komplett gebuchter Monat sperrte den Fälligkeiten-Dialog aus
**Funktionsregression aus K3 (v2.2.16).** War der aktuelle Monat bereits
vollständig gebucht, brach `add_fixcosts` mit „bereits gebucht" ab, **bevor**
der Dialog öffnete – der neu integrierte Monatswechsel war damit genau dann
unerreichbar, wenn man ihn brauchte (vorher kam die Monatsauswahl zuerst).
**Fix:** Der Dialog öffnet immer; abgebrochen wird nur noch, wenn überhaupt
keine relevanten Kategorien existieren. Eine leere Liste zeigt den Hinweis
„bereits gebucht", der Buchen-Button ist deaktiviert, der Monat bleibt oben
wechselbar (`views/tabs/tracking_tab.py`, `views/recurring_bookings_dialog.py`).

### 🟠 F2 – Bearbeiten verfälschte „zuletzt gebuchte Kategorie"
`tracking_last_category` (je Typ) wurde auch beim **Bearbeiten** gesetzt. Wer
eine alte Buchung korrigierte, bekam danach in der Schnellerfassung die
korrigierte statt der zuletzt wirklich gebuchten Kategorie vorgeschlagen.
**Fix:** Nebenwirkung nur noch im Anlege-Modus (`views/quick_add_dialog.py`).

### 🟡 F3 – Statuszeile meldete „gebucht – Undo" beim Bearbeiten
Der Hinweis gehört zum Anlegen; im Edit-Modus entfällt er. Gleicher Guard wie F2.

### 🟡 F4 – Ergebnis-Statistik bezog sich auf den Startmonat
Nach einem Monatswechsel im Dialog meldete die Zusammenfassung
(übersprungen/bereits gebucht) die Zähler des **falschen** Monats. **Fix:**
Der Dialog exponiert `current_month()`; die Statistik wird für den tatsächlich
gewählten Monat erhoben.

## Geprüft und für korrekt befunden (nicht verändert)
- `is_pot` wird aus Kategorie-Flags abgeleitet – `copy_year` kann den
  Pot-Modus nicht verlieren (kein Budget-Spalten-Flag).
- `requires_code(None)` im Legacy-Modus ohne Konto: läuft korrekt ohne Abfrage.
- Edit-Pfad ruft `update` + `set_entry_tags` in derselben Reihenfolge wie der
  frühere TrackerDialog-Pfad; Fixed-Tags der Zielkategorie bleiben konsistent.

## Tests / Gates (final, sauberer Baum)
- Versions-Sync: **PASS** (2.2.17 synchron)
- Compile: **PASS** · i18n: **PASS** (de=en=fr, 2309) · Lint: **PASS** · DAU: **PASS**
- Release-Logik-Audit: **100/0** · Deep-Logic: **500/3500/0**
- **Fresh-Logic-Audit (neu): 100 Loops, 0 Findings**
- KILLCRITIC-Invarianten-Harness: **100/0**
- pytest headless: **442 passed, 2 skipped** (436 + 6 neue)

## Noch manuell auf dem echten System
1. Monat komplett buchen → Fixkosten-Button: Dialog öffnet mit Hinweis,
   Monatswechsel lädt neue Kandidaten, Buchen-Button (de)aktiviert korrekt.
2. Buchung bearbeiten → Statuszeile bleibt still, Schnellerfassung schlägt
   weiterhin die zuletzt WIRKLICH gebuchte Kategorie vor.
3. Im Dialog Monat wechseln, buchen → Zusammenfassung nennt plausible Zähler.

## Releasefähigkeit
**v2.2.17 LOGIC FIXES** – vier Logikfehler behoben, Datenschicht mit neuem
100-Loop-Werkzeug abgesichert. Offen bleiben unverändert M6 und die
Plattform-Smokes.
