# BudgetManager v2.2.45 – Vergleich, Anleitung und Enterprise-DAU-Audit

Datum: 28. Juli 2026

## 1. Verglichene Versionen

1. `BudgetManager Source 2 2 44 CONSOLIDATED ENTERPRISE AUDITED`
2. `BudgetManager Source 2 2 44 MERGED AUDIT GUIDE`

## 2. Bewertungsentscheidung

Die Enterprise-auditierte Variante bleibt die technische Basis. Sie besitzt die robustere Cockpit-Persistenz, hält altes und neues Settings-Schema in einem Speichervorgang synchron und verhindert unnötige Layout-Signale.

Aus der Guide-Variante wurden gezielt die besseren Inhalte übernommen:

- ausführliches Cockpit-Kapitel in Deutsch, Englisch und Französisch;
- eigenes In-App-Hilfethema „Cockpit einrichten“;
- Erklärung der KPI-Trendfarben nach Bedeutung statt Vorzeichen;
- Erklärung von Ringdiagramm und kumuliertem Monatsverlauf;
- klare Abgrenzung von Automatikmodus und fixiertem Drag-and-drop;
- Beschreibung des 1180-Pixel-Spaltenumbruchs und der erhaltenen Spaltenzuordnung;
- Erklärung der Designprofile und des Profils „Mitternacht – Violett“;
- strengere Theme-Prüfung für drei- und sechsstellige Hexfarben.

## 3. Nicht übernommene Rückschritte

Folgende Ansätze der Guide-Variante wurden bewusst nicht übernommen:

- mehrere einzelne `settings.set()`-Schreibvorgänge statt `Settings.set_many()`;
- erneutes Senden des Layoutsignals auch ohne Zustandsänderung;
- reduzierte Cockpit-Kurzhilfe;
- schwächere beziehungsweise uneinheitliche Menübezeichnungen;
- Entfernen der v2.2.44-Konsolidierungs- und Versionsreferenz-Gates.

Damit bleiben DesignManager-Hoheit, Diagramm-Persistenz, Theme-Neuaufbau, Layoutmigration und atomare Speicherung erhalten.

## 4. Ergänzte Anleitung

Aktualisiert wurden:

- `docs/USER_GUIDE.de.md`
- `docs/USER_GUIDE.en.md`
- `docs/USER_GUIDE.fr.md`
- `views/help_content_additions.py`
- `docs/help/README.md`
- `docs/help/index.html`

Die Menütexte wurden anschließend mit den tatsächlichen Übersetzungen abgeglichen:

- Deutsch: `Kachellayout fixieren`
- Englisch: `Fix tile layout`
- Französisch: `Fixer la disposition des tuiles`

Die statische HTML-Hilfe wurde aus dem deutschen Handbuch neu generiert. Die historischen Hinweise „seit v2.2.38“ und „seit v2.2.41“ sind durch die Versionsreferenz-Sperre geschützt.

## 5. Zusätzliche Härtung

Der DAU-Prüfblock „Theme-Disziplin“ erkannte zuvor nur sechsstellige Hexfarben. Er erkennt jetzt auch die häufige Kurzform, beispielsweise `#666`. Fest codierte Cockpit-Farben außerhalb von DesignManager und `ui_colors.py` werden damit zuverlässiger entdeckt.

## 6. Auditergebnisse

### Enterprise-DAU-Audit

- 10 vollständige Schleifen
- 165.960 Prüfungen
- 0 Findings

Geprüfte Blöcke:

- Menü-Konventionen
- Übersetzungs- und Platzhalterparität
- lokale Verweis-Integrität
- Signal-Verdrahtung
- Theme-Disziplin
- Dialog-/Reiter-Erreichbarkeit
- Schutz historischer Versionsangaben

### Reales DAU-Erststartszenario

- 19 von 19 Schritten bestanden
- Kontoanlage, Datenbankmigration und Standardkategorien
- Budget und Tracking
- Kategorieintegrität
- Schutz gegen `inf`, `nan` und Überläufe
- 0 Fehler

### Enterprise UI-/ADHS-Audit

- 1.000 Loops
- 4.300 Prüfungen
- 0 FAIL
- 200 wiederholte WARN-Einträge aus zwei Qt-freien Ersatzprüfungen

Die beiden Hinweise betreffen Formularlabel-Ableitung und destruktive Metadatenketten. Sie sind keine gefundenen Funktionsfehler, sondern markieren Bereiche, die erst mit einer echten Qt-/Screenreader-Laufzeit vollständig geprüft werden können.

### Final-Release-Audit

- 1.000 Loops
- 19.125 Prüfungen
- 0 Fehler
- 0 Warnungen

### Tests und statische Gates

- 60 von 60 gezielten Cockpit-/Guide-/DesignManager-Regressionen bestanden
- vollständige Testsuite in isolierten Shards: 736 bestanden, 10 kontrolliert übersprungen
- Kompilierung bestanden
- i18n-Audit bestanden
- Handbuch-Vollständigkeitsaudit bestanden
- Version-Synchronisierung bestanden
- Release-Lint nach Bereinigung bestanden

## 7. Umgebungsbedingte offene Prüfungen

Zwei Tests konnten in der vorhandenen Audit-Umgebung nicht ausgeführt werden:

1. Bandit-Sicherheitsgate: Python-Modul `bandit` fehlt.
2. Echter KILLCRITIC-GUI-Worker: `PySide6` fehlt.

Dies sind fehlende Prüfwerkzeuge, keine Source-Code-Funde. Vor einer öffentlichen Binärfreigabe bleiben daher ein Bandit-Lauf sowie ein visueller/offscreen PySide6-Smoke-Test auf Fedora und Windows erforderlich.

## 8. Ergebnis

v2.2.45 verbindet die vollständigere Anleitung mit der technisch robusteren Enterprise-Basis. Die Source-Version ist nach den verfügbaren automatischen Prüfungen releasefähig. Die zwei laufzeitabhängigen externen Gates müssen vor der Binärfreigabe noch in einer Umgebung mit Bandit und PySide6 ausgeführt werden.
