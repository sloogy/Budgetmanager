# BudgetManager v2.2.20 – VOR-RELEASE-VOLLAUDIT (Funktion · Logik · Sicherheit · Stabilität)

## Rahmen
Basis: **v2.2.19 FULL_RELEASE_AUDITED**. Auftrag: alle Audits vor einem Release,
1000 Loops, Findings fixen. Ausgeführt wurden die komplette bestehende Batterie
**plus ein neues 1000-Loop-Stresswerkzeug**; die zwei gefundenen Fehler sind
behoben.

## Neues Werkzeug: `tools/mega_release_audit_1000.py`
10 Stress-/Stabilitätsthemen × 100 = **1000 Loops, 6812 Checks** (Datenschicht,
headless, deterministisch): Massen-Buchungen mit Summen-Gegenprobe per SQL,
Undo/Redo-Stürme mit exaktem Endzustands-Vergleich, Rename-Kaskaden unter Last
über alle acht namensgekeyten Tabellen, Unicode-/Emoji-/RTL-Namen inkl.
Kaskade, Extrembeträge (±10⁹) mit Drift-Toleranz, Jahreskopie-Roundtrips
(SALDO-Ausschluss, Idempotenz), **Backup-Bundle-Fuzzing** (1-Byte-Flips müssen
immer abgewiesen werden oder bitidentisch lesbar bleiben), Reset-Semantik gegen
die dokumentierte v2.2.1-Definition, Vorschlags-Engine-Stress (nie Exception,
nie Vorschlag für `is_fix`), Tag-Chaos (nie Duplikate/FK-Leichen).
**Ergebnis: 0 Findings** – die Datenschicht hält auch dem Stress stand.

## Gefundene und behobene Fehler

### 🔴 A (SICHERHEIT, HOCH) – „Notfall-Reset" umging die Sicherheitsabfrage
v2.2.18/19 hatte einen **Notfall-Reset-Button in den Backup-Dialog** eingebaut,
der alle Tabellen der aktiven DB löschte – laut eigenem Tooltip
*„funktioniert auch ohne Passwort"*. Drei Probleme auf einmal:
1. **Umgehung der Code-Abfrage** aus v2.2.10/16 (nur eine Yes/No-Box).
2. **Bruch der K4-Regel** „Reset an genau EINEM Ort" (v2.2.16).
3. **Unvollständige Tabellenliste:** `suggestion_accepted` und
   `tracking_learning_state` fehlten – nach dem Reset blieben verwaiste
   Lern-/Vorschlagszustände zurück (exakt das v2.2.6-Kaskadenthema).
**Fix:** Button, Methode (100 Zeilen) und 9 zugehörige bzw. verwaiste
i18n-Keys entfernt (de/en/fr, Parität 2301×3). Der reguläre Reset im
`DatabaseManagementDialog` ist conn-basiert, funktioniert auch im
verschlüsselten Modus und läuft **immer** hinter `require_reauth`.
Regressionstest sichert zusätzlich: kein View definiert je wieder eine eigene
`_RESET_TABLES`-Löschliste.

### 🟠 B (RELEASE-HYGIENE) – Laufzeit-Artefakte im ZIP, Lint blind
`data/budgetmanager_settings.json` (Nutzer-Settings) und ein
`data/theme_profiles/`-Ordner lagen im Release-Baum; der Lint kannte die Muster
nicht. **Fix:** entfernt; `lint_procedure_check` prüft beide Muster jetzt –
empirisch verifiziert (Probe-Datei wird gemeldet, sauberer Baum PASS).

### 🟡 Nebenbefund – hartkodierte Version im neuen Doku-Test
`test_release_2217_documentation_alignment.py` (aus 2.2.19) prüfte wörtlich
„2.2.19" und wäre bei jedem Release erneut gebrochen. Liest jetzt
`APP_VERSION` dynamisch.

## Geprüft und in Ordnung (nicht verändert)
- **Sicherheits-Zusicherungen intakt** (statischer Quickscan): 0600-Pfade an
  allen Schreibstellen, `verify_bundle` in beiden Restore-Pfaden,
  Apply-Verifikation per Tree-Hash, Backup-Pflicht (Abbruchcode in beiden
  Pfaden), PIN ≥ 6 / Passwort ≥ 10, Reset hinter Re-Auth, SQL durchgehend
  parametrisiert (f-Strings nur PRAGMA/Whitelist), keine Secrets im Log,
  Updater-Limits inkl. Kompressionsverhältnis.
- `reset_database(keep_user_data=True)`-Semantik entspricht der dokumentierten
  v2.2.1-Definition („nur Budgets zurücksetzen") – mein anfänglicher
  Audit-Check war strenger justiert als die bewusste Semantik und wurde an die
  Doku angeglichen, nicht umgekehrt.
- `migrations.py`-Änderung aus 2.2.19 (Timestamp mit Mikrosekunden) ist eine
  harmlose Kollisionsvermeidung für Pre-Migration-Backups.

## Audit-Bilanz (alle auf dieser Version, sauberer Baum)

| Prüfung | Umfang | Ergebnis |
|---|---|---|
| Versions-Sync / Compile / i18n (2301×3) / Lint / DAU | – | PASS |
| Release-Logik-Audit | 100 Loops | 0 |
| Deep-Logic-Audit | 500 Loops / 3500 Checks | 0 |
| Fresh-Logic-Audit | 100 Loops | 0 |
| Stability-Audit (aus 2.2.19) | 300 Loops / 2400 Checks | 0 |
| **Mega-Release-Audit (neu)** | **1000 Loops / 6812 Checks** | **0** |
| KILLCRITIC-Harness | 100 Loops | 0 |
| pytest headless | 457 Tests | **457 passed, 2 skipped** |

**Gesamt: 2100 Loops, über 12 700 Einzel-Checks, 0 offene Findings.**

## Noch manuell (unverändert)
GUI-Smokes auf Fedora/Windows (PySide6 fehlt im Container), Plattform-Updates
von einer älteren Version, Update-Abbruch bei vollem Datenträger,
`latest.json`-Werte. Punkt für den Smoke: Der Backup-Dialog hat **keinen**
Notfall-Reset-Knopf mehr; Reset nur noch über Datenbank-Verwaltung mit
Code-Abfrage (PIN/Passwort-Konto) bzw. ohne Abfrage bei Quick.

## Releasefähigkeit
**v2.2.20 RELEASE_AUDIT_1000** – aus meiner Sicht releasefertig nach den
manuellen Plattform-Smokes. M6 (Komplexität) bleibt bewusst nach dem Release.
