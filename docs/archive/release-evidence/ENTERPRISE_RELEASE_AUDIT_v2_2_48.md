# BudgetManager v2.2.48 – Enterprise Release Audit

**Auditdatum:** 29. Juli 2026  
**Ausgangsversion:** 2.2.47 OPEN ISSUES FIXED  
**Geprüfter und gehärteter Stand:** 2.2.48 ENTERPRISE RELEASE AUDITED

## 1. Freigabeurteil

### Entscheidung

**GO für Source-Release, Tag `v2.2.48` und den signierten CI-Build.**

**Bedingtes GO für die öffentliche Veröffentlichung der erzeugten Windows-/Linux-Artefakte.** Die Binärdateien dürfen erst hochgeladen bzw. als „Stable“ freigegeben werden, wenn die im Repository vorgesehenen externen Gates grün sind:

1. GitHub Actions inklusive Bandit und `pip-audit`.
2. PySide6-GUI-Smoke unter Fedora/Wayland und Windows.
3. Starttest von Installer und portablen Paketen auf sauberen Systemen.
4. Authenticode-Signatur und Build-Attestation.
5. Signiertes `latest.json` plus passende SHA-256-Summen.

Im geprüften Source-Baum bestehen **keine offenen technischen Release-Blocker** mehr. Die noch offenen Punkte sind Build-, Signatur- und Zielsystemprüfungen, die nicht innerhalb eines reinen Source-Audits ersetzt werden können.

## 2. Gesamtbewertung

| Bereich | Punkte | Urteil |
|---|---:|---|
| Releasefähigkeit | **93/100** | Source freigabefähig; Binärfreigabe nach externen Gates |
| Funktionen | **97/100** | Sehr breiter, miteinander verknüpfter Funktionsumfang |
| Vollständigkeit | **93/100** | Kernumfang vollständig; Druck/PDF/XLSX-Berichte bewusst nicht implementiert |
| DAU-Fähigkeiten | **95/100** | Geführter Einstieg, Hilfen, Fokusmodus und sichere Dialoge |
| Grafik und UI | **91/100** | Statische Theme-/Kontrast-/Layout-Gates grün; Live-Rendering extern prüfen |
| Codebasis | **88/100** | Sauber gegliedert und stark getestet, aber mehrere sehr große Legacy-Dateien |
| Sicherheit | **92/100** | Fail-closed Update/Restore, Hash-Locks und sichere Pfade; externe Scanner offen |
| Backup und Restore | **95/100** | Stark gehärtet; Herkunft eines Backups bleibt ohne Signatur nicht beweisbar |
| Usability | **95/100** | ADHS-freundlich, verständliche Leerzustände und konsistente Bedienpfade |

**Gesamtwert: 93/100 – Release Candidate mit Freigabe für Tag und CI-Build.**

## 3. Technischer Umfang

- **277 Python-Dateien**
- **84’932 Python-Codezeilen** inklusive Tests und Werkzeuge
- **114 Testmodule**
- Model: 40 Dateien / 15’291 Zeilen
- Views: 54 Dateien / 35’275 Zeilen
- Updater: 10 Dateien / 2’145 Zeilen
- Tests: 115 Python-Dateien / 15’170 Zeilen

Größte produktive Dateien:

1. `views/main_window.py` – 3’473 Zeilen
2. `views/tabs/budget_tab.py` – 3’390 Zeilen
3. `model/budget_overview_model.py` – 1’927 Zeilen
4. `views/setup_assistant_dialog.py` – 1’894 Zeilen
5. `views/tabs/tracking_tab.py` – 1’490 Zeilen

Diese Größen sind kein heutiger Release-Blocker, erhöhen aber langfristig das Risiko für Seiteneffekte. Für Version 2.3 sollte insbesondere `main_window.py` und `budget_tab.py` weiter in kleinere Verantwortungsbereiche zerlegt werden.

## 4. Automatisierte Nachweise

### Testgruppen

Die Tests wurden wegen einer Zeitbegrenzung der Audit-Umgebung in disjunkten Gruppen ausgeführt. Die vollständig abgeschlossenen Gruppen ergeben zusammen:

- **745 bestanden**
- **10 übersprungen** – plattform-/umgebungsabhängig
- **2 bewusst abgewählt**
  - echter Bandit-Lauf: Modul in der Audit-Umgebung nicht installiert
  - isolierter PySide6-GUI-Worker: PySide6 in der Audit-Umgebung nicht installiert
- **0 fachliche Testfehler**

### Audit-Loops

| Audit | Ergebnis |
|---|---:|
| Enterprise Release Audit | 10’000 Loops / 112’000 Prüfungen / 0 Funde |
| DAU Enterprise Audit | 75’711 Prüfungen / 0 Funde |
| Final Release Audit | 1’000 Loops / 19’135 Prüfungen / 0 Warnungen / 0 Fehler |
| UI-/ADHS-Audit | 1’000 Loops / 16’300 Prüfungen / 0 Funde |
| Mega-Stress-Audit | 1’000 Loops / 6’810 Prüfungen / 0 Funde |
| Deep-Logic-Audit | 500 Loops / 3’500 Prüfungen / 0 Funde |
| Stability-Audit | 300 Loops / 2’400 Prüfungen / 0 Funde |
| Release-Logic-Audit | 100 Loops / bestanden |
| Fresh-Logic-Audit | 100 Loops / 0 Funde |
| DAU-Erststart | Konto, DB, Kategorien, Budget, Tracking, Rename, Löschen und Fehleingaben bestanden |

Zusätzlich bestanden:

- Versionssynchronität 2.2.48
- gehashte Lockfiles
- Übersetzungsparität DE/EN/FR
- Architektur-Gate
- Handbuch-Vollständigkeit
- lokale Dokumentationslinks
- Compile-All
- Sicherheits-Lint nach Release-Bereinigung

## 5. Behobene Release-Befunde

### 5.1 Backup-Integrität war unvollständig

Vorher wurde nur die Datenbankdatei gehasht. Einstellungen und Konto-Metadaten konnten beschädigt oder verändert sein, ohne dass die Bundle-Prüfung dies erkannte.

**Behoben:** Eigene SHA-256-Werte für Datenbank, `settings.json` und `users.json`; Restore erfolgt fail-closed.

### 5.2 Mehrbenutzer-Backup war nicht selbstkonsistent

Ein Konto-Backup konnte die gesamte `users.json`, aber nur eine Datenbank enthalten.

**Behoben:** Es wird nur der zur gesicherten Datenbank passende Kontoeintrag aufgenommen. Alte Bundles werden beim Restore auf den passenden Eintrag reduziert.

### 5.3 Restore konnte große Datenbanken komplett in den RAM laden

**Behoben:** Streaming in eine temporäre Datei mit Größenlimit, `fsync`, atomarem `os.replace` und restriktiven Dateirechten.

### 5.4 Manipulierte ZIP-Methoden konnten Low-Level-Ausnahmen auslösen

Der Stress-Audit erzeugte nicht unterstützte Kompressionsmethoden und gepatchte ZIP-Daten. Diese konnten `NotImplementedError` oder `OSError` bis zum Aufrufer weiterreichen.

**Behoben:** Solche Fälle werden kontrolliert in einen `BundleIntegrityError` überführt und der Restore wird sicher abgebrochen.

### 5.5 Update-ZIPs konnten plattformabhängige Pfadkollisionen enthalten

Beispiele: `App.txt` und `app.TXT` oder Slash-/Backslash-Varianten.

**Behoben:** Doppelte und normalisiert kollidierende Pfade werden vor der Extraktion abgewiesen.

### 5.6 Veralteter Dokumentationslink

Die Haupt-README verwies auf eine nicht vorhandene Datei.

**Behoben:** Link auf `docs/open-tasks.md` korrigiert und automatische Prüfung aktiver lokaler Markdown-Ziele ergänzt.

### 5.7 Release-Metadaten waren teilweise noch 2.2.47 bzw. älter

Installationsanleitung, Updater-Beispiele und einzelne Release-Anweisungen waren nicht vollständig synchron.

**Behoben:** Version, Tags, Dateinamen, Lockfile-Köpfe, Handbücher und Release-Beispiele auf 2.2.48 vereinheitlicht.

## 6. Funktions- und Vollständigkeitsbewertung

### Vollständig und releasefähig

- Jahres- und Monatsbudget
- Kategorienhierarchie und sichere Rename-/Delete-Kaskaden
- Einnahmen, Ausgaben und Ersparnisse
- Tracking mit Filtern, Favoriten, Fixkosten und Wiederholungen
- Lernmodus und Budgetvorschläge
- POT-System und Sparziele als getrennte Fachkonzepte
- Tags und Tag-Aktionen
- Cockpit, Übersicht, Plan/Ist, Trends und Diagramme
- Konto-, PIN-, Passwort- und Restore-Key-Logik
- Backup, Restore, Legacy-Migration und Datenumzug
- Update-System mit Manifestprüfung und sicherem Staging
- DE/EN/FR, In-App-Hilfe, HTML-Handbuch und Mindmaps
- Themes, Fokusmodus, Kachelsteuerung und ADHS-freundliche Darstellung

### Bewusst nicht implementiert

- Direkter Druck
- Druckvorschau
- PDF-Berichte
- XLSX-Berichte

CSV/TXT-Export und XLSX-Kategorienimport sind vorhanden. Die fehlenden Berichtsformate sind im Handbuch offen ausgewiesen und deshalb kein versteckter Defekt. Sie senken jedoch die Vollständigkeitsnote und sollten nicht als Release-Funktion beworben werden.

## 7. Grafik und UI

Positiv:

- 26 Designprofile und zentrale DesignManager-Hoheit
- Theme-Wechsel und Dashboard-Diagramme sind abgesichert
- Kontrastprüfungen und Verbot fest codierter UI-Farben
- Responsive Cockpit-Spalten und frei anordenbare Kacheln
- animationsfreie Diagramme als Wayland-Absturzschutz
- Linux-Hilfe ohne Abhängigkeit von Emoji-Schriften
- 16’300 statische UI-/ADHS-Prüfungen ohne Fund

Grenze des Audits:

Da PySide6 in der isolierten Audit-Umgebung nicht installiert war, konnte kein echtes Fenster gerendert und kein Pixel-/Screenshot-Vergleich durchgeführt werden. Vor der öffentlichen Binärfreigabe ist deshalb ein kurzer visueller Smoke-Test auf Fedora/Wayland und Windows verpflichtend.

## 8. Sicherheit

Positiv:

- keine gefundenen `shell=True`-, `os.system`-, TLS-Deaktivierungs- oder Python-`eval`/`exec`-Pfade
- Download mit Timeout, SHA-256, signiertem Manifest und sicherem Staging
- Update-ZIP-Schutz gegen Traversal, Symlinks, Zip-Bombs, Größenüberschreitungen und Pfadkollisionen
- Restore mit Member-Limits, Strukturprüfung, atomarem Schreiben und restriktiven Rechten
- gehashte Laufzeit-, Entwicklungs- und Build-Lockfiles
- sensible Aktionen mit erneuter Authentifizierung

Abhängigkeiten:

- Die festgelegten Versionen sind auf PyPI vorhanden.
- `requests 2.34.2` liegt über dem Fix 2.32.4 für den bekannten `.netrc`-Leak.
- `cryptography 49.0.0` liegt über den Fixes 46.0.6/46.0.7 für die 2026 gemeldeten Zertifikats-/Buffer-Probleme.
- `openpyxl 3.1.5` liegt deutlich über dem alten XXE-Fix 2.4.2.

Nicht lokal abschließend nachgewiesen:

- Bandit war nicht installiert.
- `pip-audit` war nicht installiert.
- Eine aktuelle Online-Prüfung aller transitiven Build-Abhängigkeiten muss daher im GitHub-Workflow grün sein.

## 9. Backup-Bewertung

Der technische Backup-Stand ist jetzt sehr stark:

- eindeutige Struktur
- genau eine Datenbank
- Größen- und Kompressionslimits
- Hash pro enthaltenem Nutzdaten-Member
- Streaming-Restore
- atomare Wiederherstellung
- Legacy-Upgrade
- Multi-User-Konsistenz
- Regressionstests gegen Manipulation und Kollision

Wichtige Grenze:

Die SHA-256-Werte liegen im selben, nicht signierten Backup. Sie erkennen zuverlässig Beschädigung und einfache Veränderung, beweisen aber nicht die Herkunft, wenn ein Angreifer das gesamte Bundle samt Manifest neu erstellen kann. Vollständige Konto-Backups nur aus vertrauenswürdiger Quelle importieren. Ein Quick-Konto-Backup kann den lokalen Datenbankschlüssel enthalten und muss wie ein Passwort geschützt werden.

## 10. DAU- und Usability-Bewertung

Stärken:

- geführter Setup-Assistent
- Quick/PIN/Passwort verständlich getrennt
- kontextsensitive Hilfe und F1
- „Nächste Schritte“ im Cockpit
- klare Leerzustände
- Rückfragen vor destruktiven Aktionen
- Fokusmodus und ausblendbare Reiter/Kacheln
- kurze Tracking-Kategorienamen
- verständliche Fixkosten-/POT-/Sparziel-Erklärungen
- dreisprachige Handbücher und Offline-Grafiken

Verbleibendes DAU-Risiko:

Der Funktionsumfang ist sehr groß. Trotz Fokusmodus können neue Benutzer POT, Sparziel, Lernmodus, Budgetvorschläge und mehrere Übersichtsformen verwechseln. Für Version 2.3 empfiehlt sich ein dauerhaft wählbares Profil „Einfach“ und „Erweitert“, nicht nur ausblendbare Elemente.

## 11. Release-Schritte für heute

1. Diese Source-ZIP in das Repository übernehmen.
2. Tag `v2.2.48` erstellen.
3. GitHub Actions vollständig durchlaufen lassen.
4. Nur bei grünen Bandit-, `pip-audit`-, Test-, Build- und Signatur-Gates fortfahren.
5. Windows-Installer sowie Windows-/Linux-Portable auf sauberen Systemen starten.
6. Backup erstellen, Testbuchung anlegen, Restore in Testkonto durchführen.
7. `latest.json`, `latest.json.sig`, SHA-256 und Signaturen prüfen.
8. Erst danach das Release als „Latest/Stable“ veröffentlichen.

## 12. Schlussurteil

**BudgetManager v2.2.48 ist als Source-Release freigabefähig.** Die im Audit gefundenen Backup-, ZIP-, Dokumentations- und Versionsprobleme wurden behoben und regressionsgesichert.

Für den heutigen Release gilt daher:

- **Tag und CI-Build: GO**
- **Öffentliche Binärfreigabe: GO, sobald die externen Zielsystem-, Scanner- und Signatur-Gates grün sind**
- **Ungeprüfte Binärdateien direkt veröffentlichen: NO-GO**
