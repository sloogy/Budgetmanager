# BudgetManager v2.0.28 FINAL – Kritischer Fix- und 100-Loop-Bericht

Datum: 19. Juni 2026

## Urteil

**GO als Source-Final-Release v2.0.28 mit Einschränkung: echte Windows-/Linux-Frozen-Binaries müssen nach GitHub-Actions-Build noch manuell gesmoke-testet werden.**

Diese Version behebt die im v2.0.27-Recheck gefundenen Release-Blocker:

1. Budget-Modus war sprachabhängig (`Alle` vs. `All` vs. `Tous`).
2. Ungültige Beträge konnten still zu `0.0` werden.
3. Hardcoded-/i18n-Audit erkannte wichtige UI-Muster wie `addRow()` / `addItem()` nicht.

## Umgesetzte Fixes

### 1. Sprachneutrale Budget-Modi

Neu: `model/budget_modes.py`

Interne Werte:

- `month`
- `all`
- `range`

Die Dialoge zeigen weiterhin lokalisierte Texte, speichern und liefern aber stabile itemData-Werte. Legacy-/Anzeigewerte werden robust normalisiert:

- `Monat`, `Month`, `Mois` → `month`
- `Alle`, `All`, `Tous` → `all`
- `Bereich`, `Range`, `Période` → `range`

Betroffene Dateien:

- `model/budget_modes.py`
- `views/budget_entry_dialog.py`
- `views/budget_entry_dialog_extended.py`
- `views/tabs/budget_tab.py`

### 2. Copy-Year-Bereich sprachneutral gemacht

`CopyYearDialog` nutzt jetzt itemData:

- leerer String = alle Typen
- `Ausgaben`
- `Einkommen`
- `Ersparnisse`

Dadurch wird nicht mehr gegen sichtbaren Text wie `Alle` geprüft.

Betroffene Dateien:

- `views/copy_year_dialog.py`
- `views/tabs/budget_tab.py`

### 3. Strikte Betragsvalidierung

`utils.money.parse_money()` wirft jetzt `ValueError` bei nicht-numerischen Eingaben, statt still `0.0` zu liefern.

Beispiele, die jetzt abgelehnt werden:

- `abc`
- `CHF`
- `12abc`
- `--12`
- `€€`

Leere Tabellenzellen können über `empty_is_zero=True` weiter als `0.0` gelesen werden. Budget- und Tracking-Dialoge nutzen `empty_is_zero=False`, damit fehlende/ungültige Eingaben sichtbar gewarnt werden.

Betroffene Dateien:

- `utils/money.py`
- `views/budget_entry_dialog.py`
- `views/budget_entry_dialog_extended.py`
- `views/tracker_dialog.py`
- `views/tabs/budget_tab.py`

### 4. i18n- und Hardcoded-Härtung

`tools/i18n_audit.py` erkennt zusätzlich UI-Call-Muster:

- `addRow`
- `addItem`
- `addItems`
- `insertItem`
- `setItemText`

Zusätzlich wurden bekannte deutsche Resttexte in EN/FR übersetzt, u. a.:

- Budget-Modus: Monat/Bereich
- Bearbeiten
- Sparziel freigeben/abschliessen
- Fixkosten buchen
- Alles auf-/zuklappen
- Bis Ebene anzeigen
- Speichern fehlgeschlagen
- SQLite-Dateifilter

Betroffene Dateien:

- `tools/i18n_audit.py`
- `locales/de.json`
- `locales/en.json`
- `locales/fr.json`
- `views/account_management_dialog.py`
- `views/tags_manager_dialog.py`
- `settings_dialog.py`

### 5. Regressionstests ergänzt

Neu:

- `tests/test_release_hardening_v2028.py`

Abgedeckt:

- Money-Parser lehnt nicht-numerische Eingaben ab.
- Budget-Modi werden sprachneutral normalisiert.
- Bekannte deutsche UI-Restwerte tauchen nicht erneut in EN/FR auf.

## Prüfergebnis

| Prüfung | Ergebnis |
|---|---:|
| Versions-Sync | ✅ 2.0.28 synchron |
| Compileall | ✅ PASS |
| Pytest | ✅ 148 passed, 2 skipped |
| DAU-Erststart headless | ✅ PASS |
| i18n-Key-Parität de/en/fr | ✅ PASS |
| i18n-Hardcoded-Heuristik | ✅ keine Findings |
| 100-Loop-Hardcoded-Audit | ✅ 100/100 PASS |
| Private Daten im Paket | ✅ keine Runtime-DBs/Keys im Release |

## 100-Loop-Hardcoded-Audit

Zusatzbericht:

- `HARDCODED_AUDIT_100_LOOPS_v2.0.28.md`

Jeder Loop prüfte:

- i18n-Hardcoded-Scanner
- Key-Parität de/en/fr
- fehlende referenzierte Keys
- bekannte deutsche UI-Reste in EN/FR
- sprachabhängige Geschäftslogik gegen `Alle`/`All`/`Tous`

Ergebnis: **0 Findings in 100 Loops**.

## Kritische Einschränkung

Ein echter PyInstaller/Frozen-Smoke unter Windows und Linux wurde in dieser Umgebung nicht ausgeführt. Vor Veröffentlichung der Binärartefakte muss noch geprüft werden:

1. Windows `.exe` startet.
2. Linux-Binary startet.
3. Portable-ZIP nutzt stabile Startnamen.
4. In-App-Update: Check → Download/Staging → Apply → Neustart.
5. EN/FR: Budget „All/Tous“ setzt wirklich alle 12 Monate.
6. Ungültiger Betrag im Budget-/Tracking-Dialog zeigt Warnung und speichert nichts.

## Empfehlung

- Source-ZIP als `v2.0.28` taggen.
- GitHub Actions Build starten.
- Binärartefakte kurz manuell smoke-testen.
- Danach öffentliches Release mit Hinweis „v2.0.28 – Budget mode and validation hardening“ veröffentlichen.
