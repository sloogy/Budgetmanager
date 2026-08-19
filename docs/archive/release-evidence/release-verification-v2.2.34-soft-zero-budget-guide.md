# Release-Verifikation v2.2.34 – Soft-0-Budget-Hilfe

## Ziel

Die Einstellung war fachlich implementiert, aber unter der Bezeichnung „sanfte Null-Bilanz-Regel“ schwer auffindbar und in der Anleitung nicht ausreichend erklärt.

## Änderungen

- UI-Bezeichnung enthält jetzt ausdrücklich **Soft-0-Budget**.
- Kurzer Erklärungstext direkt in den Einstellungen.
- Direkter Knopf zum passenden In-App-Handbuchthema.
- Eigenes Handbuchthema in Deutsch, Englisch und Französisch.
- Ausführliche separate Anleitungsdateien in allen drei Sprachen.
- Benutzeranleitungen, HTML-Hilfe und Mindmaps erweitert.
- Beispiele verwenden CHF und erklären Überschuss, Defizit, Übertrag und Schutzregeln.

## Fachliche Abdeckung

Die Dokumentation entspricht der bestehenden Logik:

- Formel `Einnahmen − Ausgaben − Ersparnisse`.
- Keine automatische Buchung oder Budgetänderung.
- Überschuss in Ersparnisse oder als Übertrag.
- Defizit zuerst über Ersparnisse, dann flexible Ausgaben.
- Fixkosten, POT/Rückstellungen und inkrementelle Jahreskosten geschützt.
- Plan des Zielmonats hat Vorrang; stabile abgeschlossene Historie kann ergänzen.

Die Berechnungslogik wurde nicht verändert.

## Prüfung

- Kompilierung aller Python-Dateien: bestanden.
- Gezielte Soft-0-Budget-, Null-Bilanz- und Sidebar-Tests: 22 bestanden.
- Release-/Versions-/Dokumentationsintegrität: 58 bestanden.
- Gesamtsuite in fünf Dateigruppen: 626 bestanden, 9 übersprungen.
- Zwei Prüfungen konnten in der Container-Umgebung nicht ausgeführt werden:
  - Bandit ist nicht installiert.
  - PySide6 ist nicht installiert; dadurch kann der isolierte Qt-KILLCRITIC-Worker nicht starten.
- i18n-Audit: bestanden; Deutsch, Englisch und Französisch besitzen dieselben Schlüssel.
- Release-Logik-Audit: 100 Durchläufe, 0 Findings.
- Final-Release-Audit: 1’000 Durchläufe, 18’990 Prüfungen, 0 Warnungen, 0 Fehler.
- Architektur-Gate: bestanden.
- Versionssynchronisation: 2.2.34 vollständig synchron.
- Release-Lint nach Bereinigung: bestanden.
