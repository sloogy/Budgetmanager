# Enterprise-/UI-/Usability-Audit v2.2.28 und Fix-Report v2.2.29 (RELEASE_GATE_RESYNC)

Datum: 18. Juli 2026
Basis: BudgetManager_Source_2_2_28_ENTERPRISE_HARDENED_RELEASE_CANDIDATE

## 1. Auftrag

Vollaudit der Version 2.2.28: Fehleranalyse, Enterprise-Audit, UI-Audit,
Usability-Audit. Zusätzlich Verifikation des Funktions-Backlogs
(13 Punkte: wiederkehrende Transaktionen mit Soll-Buchungsdatum,
Fixkosten-Monatscheck mit optionaler Offen-Liste, Budgetwarnungen,
Tags/Labels, Undo/Redo, Favoriten, Sparziele, Backup/Restore,
Datenbank-Reset, Erscheinungsmanager, Windows-Installer, Update-Tool).

## 2. Gate-Batterie (Container, headless)

| Gate | Ergebnis |
| --- | --- |
| python3 -m compileall | PASS |
| tools/sync_version.py --check | PASS (2.2.28 synchron) |
| tools/i18n_audit.py + manuelle fr-Parität | PASS, de=en=fr = 1935 Keys |
| tools/dau_first_run_check.py | PASS |
| tools/release_logic_audit_100.py | **FAIL (Befund 1)** |
| tools/deep_logic_release_audit.py | PASS, 500 Loops / 3500 Checks / 0 |
| tools/enterprise_release_audit_10000.py | PASS, 10000 / 112000 / 0 |
| tools/final_release_audit_1000.py | PASS, 1000 / 18975 / 0 |
| tools/killcritic_x10think_10000.py | PASS, 10000 / 326811 / 0 |
| tools/mega_release_audit_1000.py | PASS, 1000 / 6811 / 0 |
| tools/pre_release_stability_audit_300.py | PASS, 300 / 2400 / 0 |
| tools/fresh_logic_audit_100.py | PASS, 100 / 0 |
| tools/ui_adhs_audit_1000.py | PASS, 1000 / 12560 / 0 |
| tools/enterprise_ui_adhs_audit_1000.py | 800 PASS / 200 WARN (erwarteter Qt-freier Container-Fallback d3/d4, kein Defekt) |
| tools/lint_procedure_check.py | PASS |
| tools/architecture_quality_gate.py | PASS |
| tools/verify_hashed_lock.py | PASS (3 Lockfiles) |
| Headless-Pytest (Shim) | 547 PASS; 2 FAIL nur containerbedingt (bandit bzw. PySide6 im Subprozess nicht verfügbar) |
| tools/bandit_release_gate.py | im Container nicht ausführbar (kein Netz/kein bandit); läuft als CI-Gate |

GUI-Verifikation (Wayland/Windows, Skalierung 100–200 %) verbleibt wie
üblich bei der manuellen Ausführung auf Fedora/Windows.

## 3. Befund 1 (einziger Befund): Release-Gate-Desynchronisation

**Symptom:** `tools/release_logic_audit_100.py` bricht in Loop 1 ab:
`workflow missing "Verify updater manifest stays updater-safe"`.

**Ursache:** Beim Merge wurde der historische Workflow-Step in den
Sammel-Step „Build signed release assets, updater manifest and SBOM"
überführt. Das Audit wurde nicht nachgezogen. Damit fiel zugleich die
explizite Nach-Build-Verifikation des GENERIERTEN `latest.json` weg;
die Manifest-Sicherheit bestand nur noch by-construction
(`build_release_assets._write_latest_json` schreibt ausschliesslich
updater-sichere Asset-Typen) plus Template-Gates.

**Fix (Defense-in-Depth statt blossem Needle-Rename):**

1. Neues Qt-freies Gate `tools/verify_release_manifest.py`:
   fail-closed-Prüfung des generierten Manifests — Pflichtfelder,
   Plattform-Assets `windows`/`linux` als `portable-zip` mit korrekten
   URL-Suffixen, Fallback-Assets, exakte Installer-Typen (`installer`
   bzw. `installer-zip`, da `updater.check_update` nur diese korrekt
   staget), Verbot von `direct_windows_exe`/`direct_linux_binary`,
   https-Pflicht, 64-Hex-SHA-256 je Asset, Ablehnung unbekannter
   Asset-Keys. Mit `--signature` zusätzlich: Signaturdatei muss
   existieren und nicht leer sein; ist ein Public Key verfügbar
   (Env `UPDATE_SIGNING_PUBLIC_KEY_B64` oder eingebetteter Trusted
   Key), wird die Ed25519-Signatur kryptografisch verifiziert.
2. `.github/workflows/build.yml`: Step „Verify updater manifest stays
   updater-safe" direkt nach der Asset-Erzeugung reaktiviert; ruft das
   Gate mit `release_assets/latest.json --signature
   release_assets/latest.json.sig` und dem Public-Key-Env auf.
3. `tools/release_logic_audit_100.py`: pinnt jetzt BEIDE Step-Namen
   sowie den Werkzeug-Aufruf `tools/verify_release_manifest.py`.
4. Regressionstests `tests/test_release_2229_manifest_verify_gate.py`
   (19 Tests): Verdrahtung und Step-Reihenfolge im Workflow,
   Audit-Pins, PASS für vertragskonforme Manifeste (mit und ohne
   optionale Installer-Assets), FAIL für jede bekannte Verletzung
   (Direkt-Binär-Keys, falsche Typen, falsche URL-Suffixe, http,
   ungültiges SHA-256, fehlende Pflicht-Assets, unbekannte Keys,
   leere Pflichtfelder), CLI-Exit-Codes, Signaturpfad inkl. gültiger
   und manipulierter Ed25519-Signatur sowie ungültigem Env-Key.
   Zusätzlich End-to-End gegen echten `_write_latest_json`-Output.

**Verifikation nach Fix:** `release_logic_audit_100.py` = 100 Loops /
0 Findings; neue Tests 19/19 PASS; Headless-Suite 566 PASS.

## 4. Funktions-Backlog: alle 13 Punkte umgesetzt (funktional geprüft)

1. **Wiederkehrende Transaktionen mit Soll-Buchungsdatum je Eintrag** —
   aktiver Pfad über `categories.is_fix/is_recurring/recurring_day`
   (sprachunabhängige `tracking.source`-Marker); Legacy-CRUD in
   `model/recurring_transactions_model.py`. Datumsklemme geprüft:
   Soll-Tag 31 ⇒ 28.02. bzw. 30.04.
2. **Fixkosten-Check „im Monat schon gebucht"** —
   `model/fixed_cost_due.is_open_this_month`; Proben: Vormonat
   ungebucht = offen, laufender Monat gebucht = zu, vor Fälligkeitstag
   = noch nicht offen; v2.2.25-Klemme für Soll-Tage 29–31 aktiv.
3. **Offen-Liste zum Auswählen (optional)** — Cockpit-Panel
   „fehlende Fixkosten" (Doppelklick bucht; Gesamtzahl über
   `cockpit.next_missing_fix`) plus `views/recurring_bookings_dialog.py`.
4. **Budgetwarnungen bei Überschreitung** — Probe: Budget 100, gebucht
   150 ⇒ `BudgetExceedance(percent_used=150.0)`.
5. **Tags/Labels** — `model/tags_model.py` (Regex-gehärtete
   Identifier), Manager-Dialog, Kategorie- und Eintrags-Zuordnung.
6. **Undo/Redo** — Roundtrip-Proben über die Produktions-API:
   Insert→Delete→2×Undo→2×Redo stellt Zwischenzustände korrekt her,
   inklusive `entry_tags`-Wiederherstellung und
   Sparziel-`current_amount`-Rückrechnung (200 → 0 → 200).
7. **Favoriten** — `model/favorites_model.py` inkl. Sortierung,
   Dashboard-Dialog.
8. **Sparziele** — `model/savings_goals_model.py` mit Grenzen-
   Validierung, Release-Logik und Tracking-Synchronisation.
9. **Backup/Restore** — `model/restore_bundle.py`: SHA-256-Manifest,
   `hmac.compare_digest`, grössenlimitierte ZIP-Reads, Legacy-Upgrade
   nur als verifizierte Kopie; Re-Auth nur für PIN/Passwort,
   Quick-Konten laufen bestätigt ohne Abfrage durch.
10. **Datenbank-Reset auf Standard** — `database_management_model` mit
    fester Tabellen-Whitelist, Backup vor Reset, K4-Re-Auth aktiv.
11. **Erscheinungsmanager (Farbprofile)** — `theme_manager.py` +
    `views/theme_editor_dialog.py`: Slug-Härtung, atomare Writes,
    Bundled-Schutz, Override/Reset.
12. **Windows-Installer** — `installer/budgetmanager_setup.iss`,
    signierter CI-Build inkl. Silent-Install-Prüfgate.
13. **Update-Tool** — `updater/`-Paket: Ed25519-Signaturpflicht,
    Zip-Slip-/Symlink-/Zip-Bomben-Schutz, Kompressionsraten-Limit,
    Rollback-Backup als harte Vorbedingung, transaktionaler Austausch.

## 5. Unabhängige Sicherheits-/Codequalitäts-Stichproben (ohne Befund)

- SQL: f-String-`execute` ausschliesslich mit Whitelist
  (`undo_redo._safe_table`, DB-Reset-Tabellenliste) oder Regex-
  Identifier-Validierung (`tags`, `tracking`, `migrations`).
- Keine Bare-Excepts in model/views/utils/updater/tools.
- Dateirechte zentral 0600/0700 (`model/file_permissions.py`).
- Excel-Import: Archiv-/Member-/Entpack-Limits, Kompressionsrate,
  DTD/ENTITY-Verbot (`utils/secure_excel.py`).
- Geld-Formatierung zentral (`utils/money.py`), EPS-Vergleiche in der
  Fälligkeits-/Warnlogik.
- `latest.json.template` strukturgleich zum Builder-Output.

## 6. Abschlussstand v2.2.29

Alle Gates grün (Container-Einschränkungen bandit/PySide6
gekennzeichnet, CI deckt sie ab). Headless-Suite: 566 PASS.
Versionssynchronisation, Lockfile-Stempel, CHANGELOG, VERSION_INFO
und alle elf versionierten Doku-Dateien auf v2.2.29; Historie
unangetastet (per Diff gegen Original verifiziert).
