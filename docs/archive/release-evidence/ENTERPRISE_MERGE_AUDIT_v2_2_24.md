# Enterprise-Report: Releasefähigkeits-Vergleich v2.2.22 ↔ v2.2.23 und Merge → v2.2.24

**Produkt:** BudgetManager · **Datum:** 15. Juli 2026
**Verglichen:** A = v2.2.22 UI_ADHS_AUDIT_FIXED (eigene, voll verifizierte Basis) ↔ B = v2.2.23 ENTERPRISE_UI_ADHS (externer Release Candidate)
**Ergebnis:** **B ist eine vollständige, verifizierte Obermenge von A** → kein Code-Merge nötig; B + zwei Portabilitäts-Korrekturen = **v2.2.24 MERGED_RC**

---

## 1. Management-Summary

| Frage | Antwort |
|---|---|
| Ist B releasefähiger als A? | **Ja.** B behält alle A-Absicherungen nachweislich bei und behebt sechs reale Schwachstellen, die A noch hatte (drei davon hatte der externe Bericht korrekt an A gefunden – von mir am Code bestätigt). |
| War ein Merge nötig? | **Nein im Code, ja in der Qualitätssicherung.** B enthielt A vollständig; zwei neue B-Artefakte (Regressionstest, Audit-Tool) waren jedoch nicht container-lauffähig und hätten die headless-Batterie dauerhaft gebrochen → als M1/M2 korrigiert. |
| Releasefähigkeit v2.2.24 | **Release Candidate, automatisierte Gates vollständig grün** (4100 Loops, >32'000 Checks, 0 Findings). Finale Freigabe nach manueller Plattform-Abnahme (Abschnitt 7). |

---

## 2. Methodik: verifizieren statt glauben

Die Session-Erfahrung (v2.2.19 trug das Label „FULL_RELEASE_AUDITED" und enthielt trotzdem einen Passwort-umgehenden Notfall-Reset) diktiert die Methode: **jede Behauptung der B-Berichte wurde am Code nachgeprüft** – per Diff, per AST-Vergleich, per eigener Nachmessung, per Live-Ausführung der Logikkerne. Der Bericht unten kennzeichnet je Punkt, *wie* verifiziert wurde.

## 3. Bestandsschutz: Alle A-Kerne in B live intakt ✅

| A-Absicherung (v2.2.16–v2.2.22) | Verifikation in B | Ergebnis |
|---|---|---|
| Cockpit-Presets: Neuinstallation startet wirklich im Fokus; Toggle ändert genau ein Panel; Bestand unangetastet | **Live ausgeführt** (Settings-Stub, Szenarien a–f) | ✅ |
| Destruktiv-Erkennung de/en/fr mit Wortgrenzen (`ui_text_rules`) | **Live: Golden-Set** | ✅ |
| Kein „Notfall-Reset"; Reset nur DatabaseManagement, hinter `require_reauth` | grep + Quellprüfung | ✅ (0 Treffer / Guard vorhanden) |
| Lint-Artefakt-Muster (settings.json u.a.) | Quellprüfung | ✅ |
| `a11y.itemview_hint` ×3 · i18n-Hardgate | JSON-Zählung | ✅ 2313×3, de−fr=∅ |
| Alle A-Audit-Tools + Regressionstests vorhanden | Datei-/Suite-Prüfung | ✅ (nichts entfernt) |

## 4. B-Verbesserungen – unabhängig bestätigt

| # | Behauptung des B-Berichts | Meine Verifikation | Urteil |
|---|---|---|---|
| 1 | Gegenfund an A: Release-Cleaner entfernte Laufzeit-Settings nicht | Diff `clean_release_tree.py`: Muster ergänzt (settings/tmp/users/db/enc/theme_profiles) | ✅ realer A-Fund, in B behoben |
| 2 | Gegenfund an A: `selectAll()` auf vorbefüllten Feldern (Überschreib-Risiko) | Diff `ui_usability.py`: `setCursorPosition(len(text))` mit Begründung | ✅ realer A-Fund, in B behoben |
| 3 | Gegenfund an A: Icon-only-Löschaktionen entgingen dem Enter-Schutz | `_is_destructive` prüft jetzt Text **und** Tooltip/AccessibleName/WhatsThis | ✅ realer A-Fund, in B behoben |
| 4 | `QFormLayout`-Labels als Accessible Names | Neue `_associated_form_label` (labelForField + Buddy, Eltern-Aufstieg) | ✅ |
| 5 | Sprachwechsel: keine gemischte UI mehr; A11y-Texte erneuerbar | `language_changed`→Neustart-Hinweis; `refresh_accessibility` mit Auto-Markern löst auch die Marker-Kollision meines Einmal-Markers | ✅ sauber gelöst |
| 6 | Alle 25 Themes ≥ 4,5:1 auf relevanten Paaren | **Selbst nachgerechnet:** 25 × 8 Paare = 200 Messungen, 0 Verletzungen, Minimum 4,50 | ✅ bestätigt |
| 7 | 21 model-Dateien „format-only" (Black) | **AST-Vergleich A↔B je Datei: 0 semantische Abweichungen** | ✅ bewiesen |
| 8 | Neues Enterprise-Tool: 1000 Loops, 0 FAIL, 200 WARN | Auf diesem Baum reproduziert (nach M2 auch im Container) | ✅ |

**Einordnung der Gegenfunde an A:** Punkte 1–3 waren echte Schwächen meiner v2.2.22 – der externe Auditor hat sie zu Recht gefunden. `selectAll` stammte aus der 2.2.21-Übernahme, der Icon-only-Fall war eine Lücke meiner Erkennungs-Extraktion, der Cleaner ein blinder Fleck neben dem Lint. Die Behebungen in B sind fachlich korrekt umgesetzt.

## 5. Gefunden und korrigiert beim Merge (M1/M2)

| ID | Fund in B | Wirkung | Korrektur |
|---|---|---|---|
| **M1** | `test_release_2223_…` importiert PySide6 auf Modulebene | Headless-Suite dauerhaft rot (Modul-Import-Fehler) | `pytest.importorskip("PySide6.QtWidgets")` – identisches Muster wie `test_gui_smoke.py`; unter Qt unverändert voll |
| **M2** | `enterprise_ui_adhs_audit_1000.py` d3/d4 nicht ohne Qt lauffähig | Neues Batterie-Tool im Audit-Container: 100 FAIL (falsch-rot) | Qt-freie Kern-Fallbacks (echte `is_destructive_text`-Aufrufe; Quell-Invarianten der Label-Ableitung); unter Qt weiterhin Volltest |
| – | CSV-Matrix-Name hartkodiert „v2_2_23" | kosmetisch | folgt jetzt der Version |

Beides sind **Portabilitäts-**, keine Inhaltskorrekturen – deshalb Merge-Version v2.2.24 statt stiller Neubau des 2.2.23-ZIPs (Reproduzierbarkeit: ein Versionsstand = ein Baum).

## 6. Abschlussbilanz v2.2.24 (dieser Baum, sauber)

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| Enterprise-UI/ADHS (neu, B) | 1000 Loops / 4300 Checks | **0 FAIL**, 200 WARN (by design, s.u.) |
| UI/ADHS (A-Werkzeug) | 1000 Loops / 15'623 Checks | 0 |
| Mega-Release | 1000 Loops / 6'812 Checks | 0 |
| Deep-Logic · Stability · Logik · Fresh · KILLCRITIC | 500+300+100+100+100 Loops | 0 |
| pytest headless | 480 Tests | **477 passed, 3 skipped** (Qt-Tests laufen auf Zielsystem; extern mit Qt: 491) |
| Sync · Compile · i18n (2313×3) · Lint · DAU | – | PASS |

**Kumuliert: 4100 Loops, über 32'000 Einzel-Checks, 0 offene Findings.**

## 7. Bewusst offen (ehrlich ausgewiesen, keine Blocker)

1. **WARN d9 – 107 modale Info-Dialoge** (von 419 QMessageBox gesamt): gehört in einen eigenen, fachlich klassifizierten UX-Umbau (Erfolg→Statusleiste/Toast, Eingabefehler→inline; Sicherheit/Datenverlust bleibt modal).
2. **WARN d10 – 13 komplexe Dialoge ohne explizite Tab-Reihenfolge**: erst reale Tastaturtests, dann `setTabOrder`-Ketten.
3. **Manuelle Plattform-Abnahme** (PySide6 fehlt im Container): Fedora/Wayland 100–200 % · Windows 100–150 % · Tastaturdurchlauf der 13 Dialoge · NVDA/Orca-Stichprobe de/en/fr · Sicht-Smoke der 25 Themes · plus die Kurzprüfungen aus v2.2.22 (Fokus-Start der Neuinstallation, Einzel-Panel-Toggle, „Réinitialiser" ohne Enter-Auslösung).

## 8. Releaseurteil

**v2.2.24 MERGED_RC – Freigabe als Release Candidate empfohlen.** Der externe v2.2.23-Stand war inhaltlich stark und ehrlich dokumentiert (inklusive berechtigter Gegenfunde an meiner v2.2.22); nach unabhängiger Verifikation aller Kernbehauptungen und zwei Portabilitäts-Korrekturen ist der zusammengeführte Stand die bisher am breitesten abgesicherte Version des Projekts. Finale Veröffentlichung nach Abschnitt 7.
