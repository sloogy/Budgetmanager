# Enterprise-UI-, Usability- und ADHS-Audit v2.2.22 (eigenständige Verifikation)

**Produkt:** BudgetManager · **Basis:** v2.2.21 UI_ADHS_HARDENED (Upload) · **Ergebnis:** v2.2.22
**Auditumfang:** eigenes Werkzeug `tools/ui_adhs_audit_1000.py` – 10 Domänen × 100 = **1000 Loops**, echte Funktionsläufe statt Quelltext-Behauptungen
**Vorher-Lauf auf v2.2.21: 252 Findings → Nachher auf v2.2.22: 0** (15'593 Checks)
**Regression gesamt:** 477 passed, 2 skipped · Daten-/Stabilitätsbatterie: 3'100 Loops kumuliert, 0 Findings

## Warum ein eigener Lauf

Der mitgelieferte v2.2.21-Bericht meldete „1'000 PASS / 0 FAIL". Die Verifikation am
Code ergab ein anderes Bild – zwei seiner Kernaussagen waren **falsch**:

1. *„Neue Installationen starten im Fokusmodus."* Faktisch materialisierte die
   v2.2.14-Zwangsmigration im Konstruktor die ALL-TRUE-Panelliste; die
   Preset-Combo zeigte „Fokus", sichtbar waren **alle** Bereiche.
2. *„Eigene Panel-Auswahl bleibt möglich, Layouts werden nicht überschrieben."*
   Ein einziger Panel-Toggle im Fokus-Modus mischte über den
   `{**PANEL_DEFAULTS, **cfg}`-Merge die ALL-TRUE-Basis ein – Favoriten,
   Budget-Ampel und „Zuletzt gebucht" poppten ungefragt auf.

Deshalb prüft das neue Werkzeug die Preset-/Migrationslogik und die
Destruktiv-Erkennung als **echte Funktionsaufrufe** (Settings-Stub, Golden-Sets)
und nicht über Quelltext-Marker.

## Die 10 Domänen (je 100 Loops)

| # | Domäne | Prüfung | v2.2.21 | v2.2.22 |
|---|---|---|---:|---:|
| D1 | Enter-Sicherheit | Golden-Set de/en/fr gegen `is_destructive_text` (echte Aufrufe) | 100 ❌ | 0 |
| D2 | A11y-i18n | keine hartkodierten deutschen UI-Sätze ausserhalb `tr()` | 2 ❌ | 0 |
| D3 | Filter-Hygiene | Einmal-Marker, Popup-Skip, zerstörungssicherer Fokus-Timer | 50 ❌ | 0 |
| D4 | Fokus-Regeln | kein Erstfokus/Default auf destruktiven Buttons | 0 | 0 |
| D5 | Cockpit-Presets | **echte Läufe**: Neuinstallation, Bestand, Toggle, v2014 | 100 ❌ | 0 |
| D6 | i18n-Platzhalter | `{var}`-Parität je Key über drei Sprachen | 0 | 0 |
| D7 | i18n-Referenzen | jeder `tr()`-Key existiert in de/en/fr | 0 | 0 |
| D8 | Skalierung | kein `setFixedSize` auf Dialogen (100–200 %) | 0 | 0 |
| D9 | Icon-Buttons | Emoji-/Icon-only-Buttons haben Tooltip (A11y-Quelle) | 0 | 0 |
| D10 | Enter-Defaults | kein `setDefault(True)` auf destruktiven `btn_*` | 0 | 0 |

Matrix: `UI_USABILITY_ADHS_1000_LOOP_MATRIX_v2_2_22.csv` (1'000 Zeilen, alle PASS).

## Behobene Findings

### 🔴 F5 – Fokus-Modus wirkte bei Neuinstallation nie (ADHS-Kernziel verfehlt)
`_ensure_budget_warnings_panel_visible` lief bedingungslos im Konstruktor und
schrieb die ALL-TRUE-Defaults fest, bevor das Fokus-Preset je greifen konnte;
zusätzlich widersprachen sich die Default-Maps in `settings.py` und im
Cockpit-Tab. **Fix:** Neues Qt-freies Modul `utils/cockpit_presets.py` als EINE
Wahrheit (Preset-Maps, wirksamer Zustand, Start-Materialisierung, Migration).
Die Alt-Migration gilt nur noch für Custom-Bestand mit eigener Auswahl;
`settings.py` bezieht seinen Default aus dem Fokus-Preset. Neuinstallation
startet jetzt **wirklich** reduziert, und die Combo-Anzeige stimmt mit dem
Sichtbaren überein.

### 🔴 F6 – Ein Toggle liess alle Panels aufpoppen
Merge-Basis war die ALL-TRUE-Map statt des wirksamen Zustands. **Fix:** Alle
vier Stellen (Panel-Config, Toggle, Preset-Wechsel, Anpassen-Dialog) delegieren
an die zentrale Logik; ein Toggle ändert **genau ein** Panel und wechselt sauber
auf „Benutzerdefiniert". Alt-Bestand ohne Preset-Feature behält sein bisheriges
„alles sichtbar" ausdrücklich festgeschrieben.

### 🟠 F3 – Destruktiv-Erkennung lückenhaft und substring-basiert
`réinitialiser`, `retirer`, `vider`, `clear`, `verwerfen`, `discard`,
`purge(r)`, `leeren` fehlten – französische/englische Lösch-Buttons konnten
Enter-Default bleiben. Substring-Matching hätte zugleich „Preset" (enthält
„reset") fälschlich entschärft. **Fix:** Qt-freies `utils/ui_text_rules.py`
mit Wortgrenzen-Matching; das Audit füttert die Funktion in D1 mit einem
dreisprachigen Golden-Set.

### 🟠 F1 – Screenreader-Hinweis hartkodiert deutsch
Der Tabellen-/Listen-Hinweis brach die de=en=fr-Hardregel; EN/FR-Nutzern wurde
Deutsch vorgelesen. **Fix:** `a11y.itemview_hint` in drei Sprachen (Parität
2'308 × 3).

### 🟡 F2 – Show-Filter lief bei jedem Anzeigen über den ganzen Baum
Auch Combo-Dropdowns und Menüs lösten den O(n)-Scan aus – unnötige Latenz,
kontraproduktiv fürs Ziel „ruhige Oberfläche". **Fix:** Einmal-Marker
`_bm_ui_enhanced` pro Widget plus Skip für Popup-/Menü-/Tooltip-Fenster.

### 🟡 F4 – Fokus-Timer konnte auf zerstörten Dialog feuern
Show → sofortiges Schliessen → `singleShot(0)` traf ein gelöschtes Qt-Objekt.
**Fix:** RuntimeError-Guard + Sichtbarkeitsprüfung; `install_ui_usability` ist
idempotent (kein Doppel-Filter).

## Prüfbilanz v2.2.22 (sauberer Baum)

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| **UI-/ADHS-Audit (neu)** | **1000 Loops / 15'593 Checks** | **0** (vorher 252) |
| Mega-Release-Audit | 1000 Loops / 6'812 Checks | 0 |
| Deep-Logic-Audit | 500 Loops / 3'500 Checks | 0 |
| Stability-Audit | 300 Loops / 2'400 Checks | 0 |
| Logik- / Fresh-Audit | je 100 Loops | 0 |
| KILLCRITIC-Invarianten | 100 Loops | 0 |
| pytest headless | 479 Tests | **477 passed, 2 skipped** |
| Sync · Compile · i18n (2'308×3) · Lint · DAU | – | PASS |

**Kumuliert: 3'100 Loops, > 28'000 Einzel-Checks, 0 offene Findings.**

## Bewusst offen (unverändert aus v2.2.21, fachlich richtig so)

- **Modale Meldungsflut (P1):** Die Umstellung Erfolg→Statusleiste /
  Eingabefehler→Inline gehört in ein eigenes Release; Sicherheits- und
  Datenverlust-Dialoge bleiben modal.
- **Reale GUI-Matrix (P1):** PySide6 fehlt im Container. Auf Fedora/Windows
  prüfen: Skalierung 100–200 %, Tastaturdurchlauf, drei Sprachen.
- **Echte Screenreader-Prüfung (P2):** NVDA/Orca gegen Tabellen, Diagramme,
  Statuskarten.

## Manuelle Smoke-Punkte für diese Version

1. **Neuinstallation** (frisches Datenverzeichnis): Cockpit startet sichtbar
   reduziert (KPIs, Hauptaktionen, Sparziele, Warnungen, offene Fixkosten);
   Combo zeigt „Fokus".
2. Im Fokus-Modus **ein** Panel zuschalten → nur dieses erscheint, Modus
   springt auf „Benutzerdefiniert".
3. Combo-Boxen mehrfach öffnen → kein Ruckeln (Filter läuft nur noch einmal).
4. FR-Sprache: Ein „Réinitialiser"-Button reagiert nicht auf blindes Enter.
5. Screenreader (falls verfügbar): Tabellenhinweis kommt in der App-Sprache.

## Releaseurteil

**Grün.** Die v2.2.21-Härtungsidee war richtig, ihre zwei zentralen
Verkaufsargumente (Fokus-Start, unberührte Layouts) waren jedoch nicht erfüllt
und die Enter-Sicherheit war nur auf Deutsch verlässlich. v2.2.22 löst alle
sechs Findings ein, macht die UI-Regeln Qt-frei prüfbar und verankert das
1000-Loop-Werkzeug dauerhaft in der Release-Batterie.
