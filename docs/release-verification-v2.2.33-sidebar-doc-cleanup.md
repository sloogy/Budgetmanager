# Release-Verifikation v2.2.33 – Sidebar-Theming und Dokumentenbereinigung

Stand: 25. Juli 2026

## Behobener Fehler

Bei einem hellen BudgetManager-Design konnte die linke Navigation dennoch dunkel bleiben. Ursache war eine lokale Stylesheet-Regel in `views/main_window.py`, die Farben über Qt-`palette(...)` bezog. Diese Palette stammte unter GNOME aus dem dunklen Systemdesign und war spezifischer als das allgemeine App-Stylesheet.

Die Korrektur in v2.2.33 ist vorhanden:

- Sidebar-Farben stammen ausschließlich aus dem aktiven BudgetManager-Profil.
- `hintergrund_seitenleiste` wird im ThemeManager tatsächlich gerendert.
- Der lokale Shell-Stil enthält nur noch Layoutregeln und keine Systemfarben.
- Stylesheets werden bei Theme-Wechseln nicht mehr aneinandergehängt.

## Dokumentenbereinigung

- Historische Audit-, Vergleichs-, Matrix- und Protokolldateien wurden aus dem Projekt-Hauptordner nach `docs/archive/release-evidence/` verschoben.
- Die Dateien wurden nicht gelöscht; ein Archivindex dokumentiert den Bestand.
- `README.md` beschreibt jetzt v2.2.33 statt eines veralteten v2.2.13-Abschnitts.
- `README_INSTALLATION.md` nennt den aktuellen Sidebar-/GNOME-Fix.
- Generierte Ordner wie `__pycache__` und `.pytest_cache` wurden entfernt.

## Prüfungen

- Python-Kompilierung: bestanden.
- Sidebar-Theming-Regressionstests: 11/11 bestanden.
- Gezielte Release-/Dokumentationsprüfungen: 64/64 bestanden.
- Gesamte Testsuite in Teilgruppen: 622 bestanden, 9 übersprungen.
- Zwei Tests konnten in der Prüf-Umgebung ausschließlich wegen fehlender optionaler Werkzeuge nicht ausgeführt werden: `bandit` und `PySide6`.
- Final-Release-Audit: 1.000 Schleifen, 18.980 Prüfungen, 0 Warnungen, 0 Fehler.
- Versionssynchronisation: v2.2.33 konsistent.
- Architektur-Gate: bestanden.

## Verbleibender Zielsystemtest

Da die Prüf-Umgebung keine PySide6-/GNOME-Oberfläche bereitstellt, muss die fertige ZIP auf Fedora einmal visuell gestartet werden. Erwartetes Ergebnis: Bei einem hellen Profil sind Seitenleiste, Navigationstext und Inhaltsbereich hell bzw. profilkonform; das GNOME-Dark-Setting überschreibt sie nicht mehr.
