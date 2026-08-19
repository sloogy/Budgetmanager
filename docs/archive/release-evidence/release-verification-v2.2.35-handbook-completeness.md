# Release-Prüfung v2.2.35 – Handbuch-Vollständigkeit

## Ergebnis

Die Benutzerhilfe wurde gegen das tatsächlich vorhandene Funktionsinventar geprüft und ergänzt. Die Dokumentation ist für die geprüften Kernbereiche vollständig, dreisprachig und widerspruchsfrei.

**Dokumentationsfreigabe: PASS**

## Behobene Dokumentationsfehler

1. **Monatsabschluss:** Die frühere Aussage einer Monatssperre war falsch. Das Häkchen setzt nur einen Vermerk für Cockpit und Erinnerungen; Budget und Buchungen bleiben bearbeitbar.
2. **Export und Drucken:** Tatsächlich vorhanden sind CSV und TXT. Direkter Druck, Druckvorschau, PDF-Berichte und XLSX-Berichte sind nicht implementiert und werden nun ausdrücklich so bezeichnet.
3. **Datenbankverwaltung:** Der aktuelle Weg führt über den Reiter Konto oder Datei → Einstellungen → Konto & Daten, nicht über einen veralteten Extras-Menüpunkt.
4. **Soft-0-Budget:** Einstellung, Formel, Voraussetzungen, Prioritäten, Abgrenzung zum Lernmodus und Fehlersuche sind beschrieben.

## Ergänzte Funktionsbereiche

- Tracking-Lernmodus
- Forecast-Modi Normal/Flexibel, POT/Rückstellung und Inkrementell
- Jahreswechsel, Jahr kopieren und 13. Monatslohn
- Tracking-Filter inklusive Haupt-/Unterkategorien
- Cockpit, Favoriten, Tags und Sparziele
- Kontotypen und zusätzliche Konten
- Datenordner-Umzug, Backup, Restore und Datenbankverwaltung
- Einstellungen, Designprofile und GNOME-Dark-Abgrenzung
- Tastenkürzel
- Updates, Logs und Diagnosebericht
- tatsächliche Export- und Druckgrenzen

## Erzeugte Hilfevarianten

- In-App-Hilfe mit 30 Themen in Deutsch, Englisch und Französisch
- Benutzerhandbücher DE/EN/FR
- statische, lokal lesbare HTML-Hilfe
- Mindmaps DE/EN/FR plus deutscher Fallback
- reproduzierbare Generatoren für HTML-Handbuch und Mindmaps
- automatischer Vollständigkeits-Audit

## Prüfungen

| Prüfung | Ergebnis |
|---|---|
| Handbuch-Vollständigkeitsaudit | 9/9 Prüfbereiche PASS |
| Dokumentations-/Regressionstests | 46 bestanden |
| Gesamte Pytest-Suite, in vier Gruppen | 630 bestanden, 9 übersprungen |
| Nicht ausführbare Umgebungstests | 2: Bandit und PySide6 fehlen im Prüfcontainer |
| Release-Logik-Audit | 100/100 Loops, 0 Findings |
| Final-Release-Audit | 1.000 Loops, 18.990 Checks, 0 Warnungen, 0 Fehler |
| Architektur-Gate | PASS |
| i18n-Audit | PASS |
| Python-Syntaxprüfung | 256 Dateien PASS |
| Lint-/Release-Prozedur | PASS |

Die zwei nicht ausführbaren Tests sind keine gefundenen Programmfehler: Der Prüfcontainer enthält weder das optionale Sicherheitswerkzeug `bandit` noch das GUI-Paket `PySide6`. Alle übrigen Tests der aufgeteilten Suite liefen erfolgreich.

## Bewusste Grenze

v2.2.35 ergänzt und korrigiert die Dokumentation. Sie implementiert **keinen** direkten Druck, keine Druckvorschau, keine PDF-Berichte und keinen XLSX-Berichtsexport. Für Ausdruck oder PDF kann der vorhandene CSV-Export in LibreOffice oder Excel geöffnet werden.
