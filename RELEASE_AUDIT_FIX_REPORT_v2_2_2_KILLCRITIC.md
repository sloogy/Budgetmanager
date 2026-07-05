# RELEASE AUDIT FIX REPORT v2.2.2 – KILLCRITIC Nachhärtung

Datum: 4. Juli 2026  
Basis: `BudgetManager Source 2 2 2 RELEASE.zip`  
Ergebnis: **Releasefähig nach Nachhärtung**

## Gefundene und behobene Punkte

### 1. Übersicht: zentraler Tag-Filter war nicht vollständig verdrahtet

**Problem:**  
Die neue Tag-Filter-Combo in der Übersichts-Kopfzeile war zwar vorhanden, aber nicht mit `currentIndexChanged` an den Refresh angebunden. Zusätzlich konnten einzelne Listen/Tabellen ihre Buchungen erneut ohne den zentralen Tag-Filter laden. Dadurch war die Aussage „filtert KPIs, Diagramme und Listen“ nicht zuverlässig erfüllt.

**Fix:**

- `OverviewTab`: Tag-Combo triggert jetzt Refresh.
- `TrackingModel.get_entries_in_range(...)`: akzeptiert optional `tag_id` und nutzt die bestehende `entry_tags`-Filterlogik.
- `OverviewTab`: lädt Tracking-Zeilen einmal zentral mit `tag_id`.
- `OverviewBudgetPanel`: Budgetübersicht, Kategoriebaum und Budget-Tabelle erhalten den Tag-Filter für Ist-Werte.
- `OverviewRightPanel`: Transaktionsliste erhält denselben zentralen Tag-Filter.

**Wichtiges Verhalten:**  
Budgets selbst tragen weiterhin keine Tags. Bei aktivem Tag-Filter bleibt der Planwert sichtbar, aber die Ist-Werte zeigen nur Buchungen mit dem gewählten Tag.

### 2. Übersicht-Seitenleiste: Label „Tag“ war missverständlich

**Problem:**  
In der rechten Übersichts-Seitenleiste wurde der Tag-Filter mit `lbl.day` beschriftet. Auf Deutsch wirkt das wie „Kalendertag/Fälligkeitstag“ und nicht wie „Tag/Label“.

**Fix:**

- Label von `tr("lbl.day")` auf `tr("header.tags")` geändert.
- Dadurch steht dort sprachübergreifend klar „Tags“.

### 3. Hilfe: Unterschied Favorit / Tag / Fälligkeitstag geschärft

**Problem:**  
Die Begriffe konnten für Einsteiger verwechselt werden: Favorit, Tag/Label und Fälligkeitstag.

**Fix:**

- In-App-Hilfe (`views/help_content.py`) ergänzt.
- HTML-Wissensdatenbank (`docs/help/index.html`) ergänzt.
- Markdown-Wissensbasis (`docs/help/README.md`) ergänzt.

Kurzlogik:

- **Favorit** = angepinnte Kategorie für schnellen Zugriff und Cockpit.
- **Tag/Label** = Schlagwort an einzelnen Buchungen für Auswertungen.
- **Fälligkeitstag** = Tag im Monat 1–31 für Fixkosten/wiederkehrende Buchungen.

### 4. Release-Prozedur: generierte Backup-Artefakte entfernt

**Problem:**  
Der DAU-Erststartcheck erzeugt testweise `data/backups/*.bmr`. Diese Dateien dürfen nicht ins Release-Paket.

**Fix:**

- Erzeugte `.bmr`-Dateien nach dem Check entfernt.
- `lint_procedure_check.py` danach erneut grün.

## Erweiterte Regressionen

`tests/test_release_221_reset_and_ux.py` wurde erweitert:

- statischer Schutz, dass der Übersichts-Tag-Filter an Refresh hängt,
- statischer Schutz, dass Budget-/Listenpanels `tag_id` bekommen,
- funktionaler Test für `TrackingModel.get_entries_in_range(..., tag_id=...)`.

## Validierte Gates

- `python tools/sync_version.py --check` → PASS
- `python -m compileall -q .` → PASS
- `python tools/i18n_audit.py` → PASS
- `pytest -q -ra` → **307 passed, 2 skipped**
- `python tools/dau_first_run_check.py` → PASS
- `python tools/release_logic_audit_100.py` → PASS, 100 Loops, 0 Findings
- `python tools/deep_logic_release_audit.py` → PASS, 500 Loops / 3500 Checks, 0 Findings
- `python tools/lint_procedure_check.py` → PASS

## Einschränkung der Prüfung

Die lokale Umgebung hatte kein PySide6 installiert. Deshalb wurden die echten GUI-Smoke-Tests übersprungen. Die Qt-freien Tests, Compile-Gates, i18n-Prüfung, DAU-Erststartsimulation und Logik-Audits sind grün. Der finale GitHub/Windows-Build sollte die GUI-Smokes und Installer-/PyInstaller-Strecke noch einmal ausführen.

## Release-Einschätzung

**Freigabeempfehlung:** Ja, als v2.2.2 KILLCRITIC-FIXED / Release Candidate.  
**Risiko:** niedrig bis mittel, weil GUI-Smoke lokal wegen fehlendem PySide6 nicht ausgeführt wurde.  
**Nicht blockierend:** Der Quellstand ist statisch und logisch releasefähig; finale Build-Umgebung muss den GUI-/Installer-Teil bestätigen.
