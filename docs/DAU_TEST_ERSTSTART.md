# DAU-Test — Usability & Durchführung nach dem ersten Start

Stand: v2.3.0 · 20. August 2026

„DAU" = der technisch völlig unbedarfte Nutzer. Getestet wurde der komplette
Weg vom allerersten Start bis zur ersten eigenen Buchung — einerseits als
**automatischer End-to-End-Logiktest** (headless, ohne GUI), andererseits als
**Klickpfad-/Wording-Durchgang** des echten Dialog-Codes.

---

## Teil A — Automatischer Durchführungs-Test (headless)

Skript: `tools/dau_first_run_check.py` (jederzeit erneut ausführbar:
`python tools/dau_first_run_check.py`). Simuliert die Logik hinter dem Erststart.

| # | Schritt | Ergebnis |
|---|---|---|
| 0 | Sprache/Währung/Format (DE+CHF+`ch`, DE+EUR+`eu`) | ✅ `1'234.50 CHF`, `1.234,50 €` |
| 1 | Konto anlegen (Quick) | ✅ User erstellt, `has_users()` |
| 2 | DB + Migrationen + Defaults | ✅ 44 Kategorien, 17 Wurzeln, Hierarchie ok |
| 3 | Budget-Wert eintragen | ✅ gespeichert |
| 4 | Testbuchung erfassen | ✅ gebucht |
| 5 | Kategorie umbenennen | ✅ Cascade über alle Tabellen, 0 Reste |
| 6 | Hauptkategorie mit Kindern löschen | ✅ 3 Kinder hochgestuft |
| 7 | Integrität | ✅ 0 verwaiste Referenzen, 0 hängende `parent_id` |

**Ergebnis: alle Checks bestanden.** Der technische Ablauf „erster Start → erste
Buchung → bearbeiten/löschen" ist konsistent und ohne Datenleichen.

---

## Teil B — Klickpfad-Durchgang (was der DAU sieht)

Reihenfolge der Dialoge beim allerersten Start:

1. **Sprache & Region** (`LanguageSelectDialog`)
   - Trilinguale Begrüßung „Welcome / Willkommen / Bienvenue".
   - Auswahl: Sprache · **Währung** · **Zahlenformat** · bevorzugter Buchungstag.
   - Button „✓ OK".
2. **Konto einrichten** (`StartupWizard`)
   - „🚀 Willkommen im Budgetmanager"
   - Schritt 1: Name/Spitzname.
   - Schritt 2: „👤 Neuen Benutzer erstellen" ODER „📦 Daten übernehmen".
   - Schritt 3: Schutz „⚡ Ohne Passwort (Quick)" / „🔢 PIN" / „🔒 Passwort".
3. **Erste Schritte** (`SetupAssistantDialog`, geführt, 11 Schritte)
   - Startmodus → Datenbank → **Zahlenformat** → Kategorien-Methode →
     Kategorien-Manager/Excel → Budget → Tracking → Fixkosten → Fertig.

### Befunde (mit Schweregrad)

| # | Befund | Schwere | Status |
|---|---|---|---|
| B1 | **Zahlenformat-Trap**: erster Dialog setzte Währung, aber NICHT das Zahlenformat. Wer das geführte Setup abwählt, sah den Format-Schritt nie → DE/EUR-Nutzer bekam Schweizer Stil `1'234.50 €`. | 🔴 hoch | ✅ behoben |
| B2 | **Doppelter Fenstertitel**: Konto-Wizard und Setup-Assistent hießen beide „Erste Schritte". | 🟡 mittel | ✅ behoben |
| B3 | **Quick-Modus ist Default** → null Schutz. | 🟡 niedrig | ✅ behoben (fette Warnfarbe + klarer Text) |
| B4 | **„Bevorzugter Tag (wiederkehrend)"** im allerersten Dialog — Begriff dem DAU dort unklar. | 🟡 niedrig | ✅ behoben (aus erstem Dialog entfernt) |
| B5 | **11-Schritte-Assistent** ist lang, aber abwählbar/überspringbar und jederzeit über „Hilfe → Erste Schritte" erneut startbar. | 🟢 ok | — |
| B6 | Format wird jetzt in Dialog 1 UND im Assistent-Schritt gewählt → der Assistent-Schritt ist nun „Bestätigung" (zeigt die Vorauswahl + Live-Vorschau). | 🟢 ok | konsistent |

### Behobene DAU-Punkte aus früheren Stabilitätsständen

**B1 — Zahlenformat in den ersten Dialog gezogen.**
`LanguageSelectDialog` hat jetzt zusätzlich eine **Zahlenformat-Auswahl**
(ch/eu/us) mit sinnvoller Vorauswahl je Sprache (`de→ch`, `en→us`, `fr→eu`),
die der DAU sofort ändern kann. Damit ist das Format **immer** gesetzt — auch
ohne geführtes Setup. Der spätere Assistent-Schritt bestätigt die Wahl nur noch.

**B2 — Eigener Fenstertitel** „Konto einrichten" / „Set up account" /
„Configurer le compte" für den Konto-Wizard (vorher identisch mit dem
Setup-Assistenten).

---

## Teil C — Aktueller Stand in v2.2.13

- **B3** Quick-Modus: Warnung jetzt **fett in Warnfarbe** mit klarem Text
  („Jede Person mit Dateizugriff kann deine Daten öffnen").
- **B4** Buchungstag aus dem allerersten Dialog **entfernt** (nur noch
  Sprache/Währung/Zahlenformat); der Tag bleibt per Default/Settings.
- **R1 Setup-Gating**: Budget-Schritt erst „erledigt" bei Budgetwert > 0;
  Tracking-Schritt blockierend, erst „erledigt" nach echter Buchung — jeweils
  mit klarem Hinweis, warum „Weiter" gesperrt ist.
- **R3 Eingabe-Konsistenz**: Qt-`QLocale` an das Zahlenformat gekoppelt
  (`ch→de_CH`, `eu→de_DE`, `us→en_US`) → Spin-Felder erwarten dasselbe
  Dezimalzeichen wie die Anzeige.
- **Kritischer Block-Bug**: durch das Einfügen des Zahlenformat-Schritts hatten
  sich `_step_done`-Indizes verschoben → Kategorien-/Budget-Schritt blieb
  fälschlich gesperrt. Behoben über symbolische Indizes + Laufzeit-Selbstprüfung
  (`_verify_step_indices`) + statische Verifikation.

### Verbleibend (kein Blocker)
- **GUI-Smoke** (echte Klicks) nach `docs/TIEFENANALYSE_RELEASE_v2_0_3.md`,
  Abschnitt 5 — insbesondere DE/EUR-Nutzer ohne geführtes Setup (B1) und das
  neue Budget/Tracking-Gating (R1) gegenprüfen.

---

## Teil D — Fehleingabe-Robustheit (v2.2.42)

Ergänzend zum Erststart-Pfad wurde geprüft, was der DAU im laufenden Betrieb an
Unsinn eintippen kann. Der `dau_first_run_check.py` deckt das in **Schritt 8**
mit ab (jederzeit erneut ausführbar).

| Eingabe | Feld | Verhalten |
|---|---|---|
| `inf`, `Infinity`, `nan`, `1e400`, sehr lange Ziffernfolge | jedes Betragsfeld | ✅ abgewiesen (fail-closed) |
| `1,50` · `1.234,56` · `-5` · leer | jedes Betragsfeld | ✅ weiterhin korrekt |
| inf/nan als Budget, Buchung, Sparziel-Ziel | DB-Schreibgrenze | ✅ abgewiesen — kein nicht-endlicher Wert erreicht die DB |
| `'); DROP TABLE …` | Kategorie-/Tag-Name | ✅ parametrisiert, keine Injection |
| leer / nur Leerzeichen | Kategorie-/Tag-Name | ✅ an der GUI abgefangen |

**Hintergrund:** `float("inf")`/`float("nan")` sind formal „numerisch" und
rutschten früher durch jedes Betragsfeld in die DB — ein einziger solcher Wert
hätte alle Summen, Budget-Reste, Sparziel-Grenzen und Diagramme vergiftet. Die
Abwehr sitzt jetzt dreischichtig: `parse_money` (GUI-Eingabe), der Helfer
`require_finite_amount` (DB-Schreibgrenze, auch für Excel-Import) und Guards in
den Modellen für Budget, Tracking und Sparziele.

---

## Fazit

Die **Durchführung** nach dem ersten Start funktioniert technisch
vollständig und konsistent (Teil A, alle Checks grün). Der größte
**Usability-Stolperstein** (Zahlenformat-Trap bei übersprungenem Setup) ist
behoben. Verbleibende Punkte sind kosmetisch und kein Release-Blocker.
