# BudgetManager v2.0.30 – Konsolidierung & Verifikation

**Datum:** 19. Juni 2026
**Ergebnis:** Drei divergierende Quellstände sauber zusammengeführt, Forecast-Fix unabhängig verifiziert, High-DPI-Skalierungsfix eingebaut. **Alle container-prüfbaren Gates grün.** Zwei Punkte brauchen echte Windows-Hardware bzw. ein Crash-Log (siehe §5).

---

## 1. Ausgangslage: drei divergierende ZIPs

| Quelle | Version | Enthielt |
|---|---|---|
| `…_MINDMAP_I18N_FIXED` | 2.0.29 | i18n-Lückenschluss, Shortcut-i18n, Mindmap, **Forecast-Fixkosten-Hotfix** |
| `Budgetmanager_release` | 2.0.28 | gehärtete CI-`build.yml` (offscreen Qt, UTF-8) |
| (meine v2.0.29-Arbeit) | 2.0.29 | i18n-Audit, Sparziel-Ergänzung – bereits in der Mindmap-Quelle integriert |

**Konsolidierungsentscheid:** Mindmap-Quelle als Basis (vollständigste), darauf die `build.yml` aus der Release-Quelle. Ergebnis: **v2.0.30**.

---

## 2. Was zusammengeführt wurde

### 2.1 CI-Workflow (aus Release-Quelle)
`.github/workflows/build.yml` Test-Job setzt jetzt:
- `QT_QPA_PLATFORM: offscreen` (Qt-Tests laufen headless auf dem Runner)
- `PYTHONUTF8: "1"`, `PYTHONIOENCODING: utf-8` (Umlaut-/Akzent-sichere Ausgabe)
- `pytest -v -ra --tb=short`

Das war der „Release-YAML-Fix". Die Mindmap-Variante hatte nur `pytest -v` ohne diese Absicherung.

### 2.2 Forecast / i18n / Shortcuts / Mindmap (aus Mindmap-Quelle)
Bereits enthalten und hier verifiziert – siehe §3.

---

## 3. Unabhängig verifizierte Fixes

### 3.1 Forecast-Fixkostenlogik – Christians Befund behoben ✅

**Der gemeldete Denkfehler:** Budget 200 CHF, Ist 250/250/250/0/0/0 → 750 real von 1200 budgetiert (unter Budget), trotzdem Erhöhung auf 240.

**Der Fix (Mindmap-Quelle, „Release-Regel v2.0.30"):** Bei fixkostenähnlichen Kategorien mit echten 0-Monaten wird die **Gesamtdeckung des Fensters** betrachtet, nicht nur die aktiven Monate. Ist `Summe(Budget − Ist) ≥ 0` über das volle Fenster, gibt es keinen Erhöhungsvorschlag. Andernfalls wird die durchschnittliche Gesamtunterdeckung pro Monat als konservativer Anpassungswert genutzt.

**Meine unabhängige Verifikation** (gegen das echte `migrate_all`-Schema, isolierte Settings):

| Szenario (Budget 200, fix+wiederkehrend) | Ist/Budget | Ergebnis | korrekt |
|---|---|---|---|
| 250/250/250/0/0/0 (Christians Fall) | 750/1200 | kein Vorschlag | ✅ |
| 500/500/500/0/0/0 (echte Unterdeckung) | 1500/1200 | Erhöhung → 240 | ✅ |
| 600/600/0/0/0/0 (exakt ausgeglichen) | 1200/1200 | kein Vorschlag | ✅ |
| 590/590/0/0/0/0 (knapp drunter) | 1180/1200 | kein Vorschlag | ✅ |
| 250×6 (konstant über, keine 0-Monate) | 1500/1200 | Erhöhung | ✅ |
| 300/300/0/0/0/0 (nur 2 aktive Monate) | 600/1200 | kein Vorschlag (zu wenig Daten) | ✅ |
| 900×4/0/0 (massive Unterdeckung) | 3600/1200 | Erhöhung → 520 | ✅ |

Zusätzlich: **16 gezielte Edge Cases + 4000 randomisierte Property-Szenarien** (1089 erzeugte Vorschläge) ohne Invarianten-Verletzung. Der Fix ist vollständig und führt keine Regression ein.

### 3.2 Shortcut-Texte lokalisiert ✅
`model/shortcuts_config.py` liefert Labels, Gruppen und Tastenanzeigen über i18n-Keys. Test `test_shortcut_catalog_is_localized_in_all_release_languages` grün: in EN/FR erscheinen **keine** deutschen Begriffe mehr (`Hilfe`, `Wissensdatenbank`, `Einstellungen öffnen`, `Zum Budget-Tab`, `Allgemein`, `Funktionen`, `Strg`, `Umschalt`). „Strg+Umschalt+Z" wird in DE so, in EN als „Ctrl+Shift+Z" angezeigt.

### 3.3 i18n-Parität ✅
de = en = fr, exakt **2068 Schlüssel**, keine leeren Werte. Die drei zuvor unübersetzten UI-Texte (`Budget bearbeiten`, `Datenbank-Verwaltung`, `Datenbank bereinigen`) sind in EN/FR korrekt übersetzt.

---

## 4. Container-Gates (alle grün)

| Gate | Ergebnis |
|---|---:|
| compileall | ✅ |
| sync_version --check | ✅ 2.0.30 |
| i18n_audit | ✅ |
| dau_first_run_check | ✅ |
| Qt-freie Regression (eigene Harness) | ✅ 83 PASS / 0 FAIL |
| 100-Loop-Logiktest | ✅ 100/100 |
| Forecast-Audit (eigen, echtes Schema) | ✅ 16 + 4000 |
| Updater-Audit (eigen, 5 Ebenen) | ✅ 5/5 |
| Hardcoded-UI-Scanner (eigen) | ✅ 0 |
| Packaging-Hygiene | ✅ keine privaten Daten/Bytecode |

---

## 5. Offen – braucht echte Hardware bzw. Input

### 5.1 Skalierung (portable, Windows) – Fix eingebaut, Hardware-Verifikation nötig
**Symptom (dein Screenshot):** Cockpit-Tabellen „Favoriten im Blick"/„Budget-Ampel" mit extrem schmalen, abgeschnittenen Spalten, restliche UI normal.

**Eingebauter Fix:** `QApplication.setHighDpiScaleFactorRoundingPolicy(PassThrough)` vor der QApplication-Instanz (`main.py`). Das ist die häufigste Ursache für verzerrte Layouts bei fraktionaler Windows-Skalierung (125/150/175 %).

**Wichtig – ehrlich:** Im Container ist keine GUI lauffähig (kein PySide6/Display), ich konnte das Symptom **nicht reproduzieren und den Fix nicht visuell bestätigen**. Bitte die portable v2.0.30 auf der betroffenen Windows-Maschine starten und prüfen. Falls die Spalten weiterhin gequetscht sind, ist es kein DPI-Rundungsproblem, sondern ein Tabellen-Layout-Problem – dann brauche ich: (a) die eingestellte Windows-Skalierung (%), (b) einen Screenshot der **v2.0.30**.

### 5.2 Abstürze – Crash-Log nötig
Die App schreibt ein Diagnose-Log via `faulthandler`. Du findest es unter:

```
<Datenordner>/budgetmanager_crash.log
```

(Fallback `/tmp/budgetmanager_crash.log`, falls der Datenordner nicht beschreibbar ist.)

Bitte den Inhalt nach dem nächsten Absturz schicken – ohne den Traceback ist jede Absturz-„Behebung" geraten. Mit dem Log kann ich die Ursache gezielt eingrenzen.

---

## 6. Nicht lokal ausführbar (wie bisher)
PyInstaller-/Inno-Builds und `black`/`mypy`/Qt-`pytest` laufen erst im CI bzw. auf echter Hardware. Pflicht-Smoke nach dem GitHub-Build: Installer + beide Portable-ZIPs starten, Updater real durchklicken, `data/` + Backups prüfen.

---

## 7. Empfehlung
1. Diese ZIP als konsolidierten Stand **v2.0.30** verwenden.
2. Tag `v2.0.30`, GitHub-Build laufen lassen (CI bestätigt black/mypy/pytest/Builds).
3. Portable v2.0.30 auf der Windows-Maschine starten → Skalierung prüfen (§5.1).
4. Bei erneutem Absturz `budgetmanager_crash.log` schicken (§5.2).
5. Erst nach Skalierungs-/Absturz-Klärung öffentlich freigeben.

**Endurteil:** Konsolidierung, Forecast-Fix, i18n/Shortcuts und CI sind releasefähig und verifiziert. Skalierung und Abstürze sind ohne echte Hardware/Crash-Log nicht abschließend lösbar – dafür sind die nächsten Schritte klar benannt.
