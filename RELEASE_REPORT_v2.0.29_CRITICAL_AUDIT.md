# BudgetManager v2.0.29 – Kritischer Release-Audit auf allen Ebenen

**Datum:** 19. Juni 2026
**Basis:** `BudgetManager_v2_0_28_RELEASE_READY_100_LOOP_AUDITED.zip` (v2.0.28)
**Ergebnis:** **GO als Source-Release-Candidate v2.0.29** – nach unabhängiger Prüfung aller sieben geforderten Bereiche und Schliessung von vier echten Befunden.

---

## 1. Kurzurteil

Diese Prüfung hat die mitgelieferten Reports der v2.0.28 **nicht nachgeplappert**, sondern jeden geforderten Bereich mit eigenen, unabhängigen Werkzeugen neu verifiziert – inklusive einer randomisierten Forecast-Prüfung gegen das *echte* Datenbankschema und einer End-to-End-Auflösung aller Updater-Ebenen.

Dabei wurden **vier echte Befunde** gefunden und behoben. Danach sind alle automatisiert prüfbaren Gates grün.

| Gate | Werkzeug | Ergebnis |
|---|---|---:|
| 1 Compileall | `python3 -m compileall` | ✅ |
| 2 Versions-Sync | `tools/sync_version.py --check` | ✅ 2.0.29 |
| 3 i18n-Audit | `tools/i18n_audit.py` | ✅ |
| 4 DAU-Erststart | `tools/dau_first_run_check.py` | ✅ |
| 5 Qt-freie Regression | **eigene Harness** (kein pytest/PySide6 nötig) | ✅ 81 PASS / 0 FAIL |
| 6 100-Loop-Logiktest | `tools/release_logic_audit_100.py` | ✅ 100/100 |
| 7 Forecast-Denkfehler | **eigenes Audit, echtes Schema** | ✅ 16 + 4000 Szenarien |
| 8 Updater alle Ebenen | **eigenes Audit** | ✅ 5/5 Ebenen |
| 9 Hardcoded-UI-Scanner | **eigener AST-Scanner** | ✅ 0 |
| 10 Packaging-Hygiene | Dateiscan | ✅ keine privaten Daten/Bytecode |

**Wichtige Einschränkung:** In dieser Linux-Sandbox sind weder echte PyInstaller-Binaries noch ein echter Inno-Setup-Installer baubar, und `black`/`mypy`/Qt-`pytest` sind nicht installiert (kein Netzwerk). Diese Punkte bleiben Pflicht-Smoke-Test nach dem GitHub-Build (siehe §6).

---

## 2. Behobene Befunde (diese Runde)

### 2.1 Drei aktiv verdrahtete UI-Texte erschienen in EN/FR auf Deutsch

Eigener Vergleich der drei Locale-Dateien fand drei Schlüssel, deren englische **und** französische Werte nur eine Kopie des deutschen Textes waren. Alle drei sind im UI **aktiv verdrahtet**:

| Schlüssel | Ort | vorher (EN/FR) | nachher EN | nachher FR |
|---|---|---|---|---|
| `auto.views_main_window.1089_budget_bearbeiten_45efb7d1` | Budget-Menüeintrag (`main_window.py:1452`) | „Budget &bearbeiten…“ | „Edit &budget…“ | „&Modifier le budget…“ |
| `auto.views_database_management_dialog.54_…` | Dialog-Titel (`database_management_dialog.py:54`) | „🗄️ Datenbank-Verwaltung“ | „🗄️ Database management“ | „🗄️ Gestion de la base de données“ |
| `auto.views_database_management_dialog.89_…` | Button (`database_management_dialog.py:88`) | „🧹 Datenbank bereinigen“ | „🧹 Clean up database“ | „🧹 Nettoyer la base de données“ |

i18n-Parität bleibt exakt: **2040 Schlüssel** in de/en/fr, keine leeren Werte.

### 2.2 DE-Anleitung um Sparziele ergänzt

`docs/USER_GUIDE.de.md` erwähnte Sparziele nicht, während EN/FR sie führten. Ergänzt um einen Absatz, der das Setzen/Verfolgen inkl. der 0-/Ziel-Grenzen erklärt.

### 2.3 Versions-Stempel `docs/help/index.html` war nicht gebumpt

Der projekteigene Test `test_active_release_docs_are_version_synced` deckte auf, dass `index.html` noch v2.0.28 trug. Auf 2.0.29 gebracht; alle acht aktiven Release-Docs sind nun synchron.

### 2.4 Versionsangaben auf v2.0.29 synchronisiert

`app_info.py` als einzige Quelle auf 2.0.29 gesetzt; `sync_version.py` hat version.json, VERSION_INFO.txt, Installer-`.iss` und beide `latest.json`-Vorlagen propagiert. Anwender-Docs und die beiden harten Versions-Assertions in den Tests nachgezogen.

---

## 3. Abdeckung der sieben geforderten Punkte

### 3.1 Anleitung in DE/EN/FR — ✅
Drei Anleitungen vorhanden (`docs/USER_GUIDE.{de,en,fr}.md`), im README verlinkt, mit v2.0.29-Stempel. Acht Sektionen je Sprache: Grundidee, Kategorien, Budget, Tracking, **Forecast**, **Übersicht/Diagramme**, **Updates**, Backup/Restore. Themenabdeckung (Forecast, Diagramm-Erklärung, Updates, Fixkosten, Backup, Datenordner, Sparziele) je Sprache geprüft.

### 3.2 Forecast-Logik auf Denkfehler geprüft — ✅ (unabhängig, echtes Schema)
Eigenes Audit (`forecast_audit.py`) gegen das **echte `migrate_all`-Schema** mit **isolierten Settings** (verhindert, dass globale `carryover_start`-Werte den Test verfälschen). Geprüft:

- **16 gezielte Edge Cases:** Einkommen rauf/runter (Richtung korrekt), Einzelmonat blockiert, instabiles Muster blockiert, Fixkosten-0-Schutz, Fixkosten echte Überschreitung, Floor-Untergrenze, kein Budget → kein Vorschlag, Rauschen unter Schwelle, Vor-Tracking-Monate kein 0-Signal, Langzeit-0-Reduktion, einmalige Savings-Überzahlung.
- **4000 randomisierte Property-Szenarien** (1456 erzeugte Vorschläge) mit **0 Invarianten-Verletzungen**: nie negatives Budget, nie unter Floor (Ausgaben/Sparen), Einkommens­budget nie negativ, Richtung konsistent, **kein Engine-Crash**.

**Befund: keine Denkfehler in der Forecast-Logik.**

### 3.3 Hardcoded Strings ersetzt — ✅
Eigener **AST-Scanner** (`hardcoded_scanner.py`) sucht deutsche String-Literale, die direkt an Qt-UI-Setter/-Widgets gehen und **nicht** durch `tr()/trf()` laufen. Logger-Aufrufe (auch verkettete `logging.getLogger(__name__).warning`) und interne Sammel-Listen (`migrations_applied.append`) werden korrekt ausgenommen. **Ergebnis: 0 echte hardcoded UI-Strings.** Zusätzlich: `i18n_audit.py` grün; die drei EN/FR-Lücken aus §2.1 geschlossen.

### 3.4 Git / Release-Plattform kann alles erstellen — ✅ (statisch vollständig)
`.github/workflows/build.yml` deckt ab: Matrix-Build Windows + Linux (PyInstaller), Windows-Installer (Inno Setup), Portable-ZIP mit stabilen Startnamen (`BudgetManager.exe`/`BudgetManager`/`start-windows.cmd`/`start-linux.sh`), `latest.json`, Upload via `softprops/action-gh-release@v2`. Vorgeschaltete harte Gates im Build: `sync_version --check`, `compileall`, `black --check model/`, `mypy model/`, komplette `pytest`-Suite.

> **Hinweis zu den CI-Gates:** `black`/`mypy`/`pytest` laufen erst auf dem GitHub-Runner. `black`-Konformität von `model/` wurde hier heuristisch geprüft (0 echte Quote-Verstösse nach korrektem f-string-Handling) – die endgültige Bestätigung liefert der CI-Lauf.

### 3.5 DAU-freundlich — ✅
`dau_first_run_check.py` grün: Regionseinstellungen, Quick-Konto, DB+Migration, 44 Default-Kategorien, Budget/Tracking, Rename-Cascade über alle Tabellen, Kinder-Hochstufung, Integrität ohne verwaiste Referenzen. Anleitungen erklären Datenort, Workflows, Forecast-Bedeutung, Diagramme, Updates, Backup.

### 3.6 Graphen logisch inklusive Erklärung — ✅
Overview-Charts-Tests grün (Range-Budget über Fenster statt Einzelmonat; Top-Buchungen aggregieren Gehalt einmalig). KPI-Panel führt Untertabs **und** Erklär-Tipps für Monatsverlauf, Saldoverlauf und Top-Buchungen. Anleitung erklärt Balken-, Verteilungs- und Verlaufsdiagramme sowie das Verhalten bei fehlenden Daten.

### 3.7 Updater auf allen Ebenen funktionsfähig — ✅ (5/5 End-to-End)
Eigenes Audit (`updater_audit.py`) löst für **jede** Installationsvariante das korrekte Asset aus `latest.json` auf:

| Variante | Erste Wahl | Aufgelöstes Asset |
|---|---|---|
| Windows Installer | `windows_installer` | `BudgetManager_Setup_2.0.29.exe` |
| Windows Direct-EXE | `direct_windows_exe` | `…-windows.exe` |
| Windows Portable-ZIP | `windows` | `…-portable.zip` |
| Linux Direct-Binary | `direct_linux_binary` | `…-linux` |
| Linux Portable-ZIP | `linux` | `…-portable.zip` |

Zusätzlich abgesichert (mitgelieferte Tests, grün): Apply nutzt die geprüfte/gestagte Version statt einer alten höheren Staging-Version; Update-Dialog startet im Frozen-Build `--check-update`/`--apply-update`; stabile Startnamen im Portable-ZIP.

---

## 4. Was diese Prüfung anders gemacht hat

- Das mitgelieferte `release_logic_audit_100.py` führt **100× denselben** deterministischen Test aus (substanziell, aber keine zusätzliche Abdeckung pro Loop) und nutzt ein **vereinfachtes** DB-Schema. Diese Prüfung ergänzt ein **randomisiertes** Forecast-Audit gegen das **echte** Schema.
- Da der Container **kein pytest und kein PySide6** hat, wurde eine **eigene Qt-freie Harness** gebaut (Fixtures, `raises`, `monkeypatch`, `tmp_path`), die 81 Modell-/Logiktests real ausführt statt sie zu überspringen.
- Der Updater wurde nicht nur statisch geprüft, sondern die Asset-Auflösung **pro Installationsart** real durchgespielt.

---

## 5. Ausgeführte Befehle

```bash
python3 -m compileall -q .
python3 tools/sync_version.py --check
python3 tools/i18n_audit.py
python3 tools/dau_first_run_check.py
python3 tools/release_logic_audit_100.py
# eigene Audits:
python3 harness/run_tests.py        <root>   # Qt-freie Regression
python3 harness/forecast_audit.py   <root>   # Forecast-Denkfehler (echtes Schema)
python3 harness/updater_audit.py    <root>   # Updater alle Ebenen
python3 harness/hardcoded_scanner.py <root>  # hardcoded UI-Strings
```

---

## 6. Nicht lokal ausführbar / Pflicht-Smoke nach GitHub-Build

Folgendes wurde hier **nicht** ausgeführt und darf nicht als erledigt gelten:

- PyInstaller-Frozen-Build (Windows + Linux)
- Inno-Setup-Installer-Build (Windows)
- `black --check model/`, `mypy model/`, Qt-`pytest` (laufen erst im CI)
- echter Updater-Live-Test gegen ein GitHub-Release

**Pflicht-Smoke nach dem GitHub-Build:**
1. Windows-Installer installieren und starten.
2. Windows-Portable-ZIP starten.
3. Linux-Portable-ZIP starten.
4. Update-Dialog: Check → Download/Staging → Jetzt aktualisieren & Neustart.
5. Prüfen, dass `data/` und Backups erhalten bleiben.

---

## 7. Release-Empfehlung

1. Diese ZIP als Source-Release-Candidate **v2.0.29** verwenden.
2. Tag `v2.0.29` setzen und pushen.
3. GitHub Actions durchlaufen lassen (CI bestätigt black/mypy/pytest/Builds).
4. Die drei echten Artefakte testen (Installer, Windows-Portable, Linux-Portable) und den Updater real durchklicken.
5. Öffentliches Release freigeben.

**Endurteil:** Für Source/Logik/i18n/Tests/Updater ist **v2.0.29 releasefähig**. Für die öffentliche Binärverteilung fehlt nur noch der echte GitHub-Build- und Smoke-Test.
