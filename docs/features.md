# BudgetManager v2.3.0 — Feature-Übersicht

BudgetManager ist eine lokale Desktop-App für Budgetplanung, Buchungen, Kategorien, Fixkosten, wiederkehrende Zahlungen, Sparziele und Auswertungen.

## LifePlanner-Modulpakete (seit v2.2.62)

- Unsigned `.lpmodule`-Pakete für Windows x86_64 und Linux x86_64; der lokale Import erfordert eine manuelle Vertrauensbestätigung.
- Eigene SHA-256-Datei je Paket und strukturelle Prüfung vor Veröffentlichung.
- Profilbezogene Daten- und Bridge-Pfade über den bestehenden LifePlanner-Laufzeitvertrag.

## Freie Cockpit-Anordnung (seit v2.2.60)

- Manuelles Layout über die gesamte Kachel-Kopfzeile oder den Griff `≡`.
- Zwei gleich breite Zielspalten ab 720 Pixel Breite.
- Reihenfolge und Spaltenzuordnung werden dauerhaft gespeichert.
- Tabellen, Buttons und Diagramme bleiben normal bedienbar.

## Bedienung, Berichte und Release-Härtung in v2.2.52

- Einfach-/Erweitert-Modus mit reduziertem Standard für neue Installationen.
- XLSX-/PDF-Berichte, anonymisierte Diagnose und atomare Restore-Kopie.
- Voll-Coverage-, Performance- und visuelle Plattform-Gates.
- Dashboard-Karten, KPI-Trends, Ringdiagramm und Flächenverlauf aus v2.2.42.
- Automatisches Absenken leerer, geschrumpfter Kacheln aus v2.2.41.
- Fixierter Drag-and-drop-Modus mit gespeicherter Reihenfolge und Spaltenzuordnung.
- DesignManager bleibt alleinige Quelle für Farben, Kontraste und Dashboard-Zustände.
- Migration vorhandener Layout-Einstellungen beider Zwischenversionen.

## Kernfunktionen

### Budgetplanung

- Jahresbudget mit 12 Monatswerten und Totalspalte.
- Typen: Einkommen, Ausgaben, Ersparnisse.
- Haupt- und Unterkategorien.
- Fixkosten- und Wiederkehrend-Markierung.
- Fälligkeitstag je Kategorie.
- Budget-Saldo und Monats-/Jahresübersichten.
- Budgetvorschläge auf Basis historischer Buchungen.
- Optionales Drag & Drop in der Budgetübersicht zum Umhängen von Kategorien.

### Kategorien

- Kategorien-Manager mit Baumansicht.
- Drag & Drop für Parent/Child-Ebenen.
- Kontextmenü zum Verschieben, Umbenennen, Löschen und Zur-Hauptkategorie-Machen.
- Schutz gegen Self-Parenting, Typ-Mischung und Zyklen.
- Bulk-Bearbeitung für Fixkosten, Wiederkehrend und Fälligkeitstag.
- Import/Export von Kategorien über Excel/CSV.

### Tracking / Buchungen

- Buchungen erfassen, bearbeiten und löschen.
- Filter nach Jahr, Monat, Zeitraum, Typ und Kategorie.
- Schnellfilter für letzte 14/30 Tage.
- Tags und Detailtexte.
- Import/Export für Buchungen.
- Direkte Buchung wiederkehrender Einträge.

### Wiederkehrende Buchungen und Fixkosten

- Fällige Buchungen erkennen.
- Fixkosten aus Budgetwerten übernehmen.
- Monatliches Fälligkeitsdatum inklusive Monatsende.
- Optionaler bevorzugter Standard-Buchungstag.
- Einstellung „kein bevorzugter Tag“ für manuelle Pflege.

### Cockpit und Übersicht

- Ruhige Startseite mit Monatsstatus, Budget-Ampel, Budgetwarnungen, offenen Buchungen und letzten Buchungen.
- Rechtsklick-Menüs im Cockpit mit echten Schnellaktionen.
- Übersicht über Budget vs. Ist-Buchungen.
- Diagramme und Tabellen im Übersichtstab.
- Verschiebbare/skalierbare Panels.

### Sparziele

- Sparziele als eigener Bereich.
- Zielbetrag, Fortschritt und Status auf einen Blick.
- Sichtbar im Cockpit und in der Übersicht.

### Einstellungen und Komfort

- Mehrsprachig: Deutsch, Englisch, Französisch.
- Währung: CHF, EUR, USD, GBP.
- Themes und Designprofile.
- Tab-Layout und Fensterzustand werden gespeichert.
- Backup/Restore inklusive Einstellungen.
- Persistentes Undo/Redo.
- Multi-Account-System mit Quick/PIN/Passwort-Modus.
- Stabilitätsfallback unter Wayland über `xcb`, abschaltbar mit `BM_ALLOW_WAYLAND=1`.

## Neu bzw. release-relevant in v2.2.13

- v2.2.13 als Basis mit Cockpit-, Budgetwarnungs-, Wayland-, i18n-, Restore- und Selbstheilungs-Fixes zusammengeführt.
- Cockpit-Rechtsklick-Menüs sind wieder nutzbar und zeigen echte Cockpit-Aktionen.
- Budgetwarnungen sind direkt im Cockpit sichtbar.
- Harte Cockpit-Bezeichnungen wurden in Übersetzungsschlüssel überführt.
- README, Installationsdoku, Feature-Übersicht, Hilfe, technische Dokumente und Manifest-Beispiele wurden auf v2.2.13 bereinigt.
- CI prüft zusätzlich die Formatierung des ganzen Projekts (`black --check`) und Typen in `model/`, `utils/` und `updater/` (`mypy`).
  Lokal dafür `python tools/gepinnte_werkzeuge.py black --check model/` verwenden: Das Skript nimmt die in
  `requirements-dev.txt` gepinnte Version, nicht die des Rechners.
- Alte Arbeitsberichte und Cache-Ordner wurden aus dem Release-Paket entfernt.

## Technik

- Python 3.11+
- PySide6 / Qt 6
- SQLite mit automatischen Migrationen
- JSON-basierte i18n-Dateien unter `locales/`
- Zentrale App-Version in `app_info.py`
- GitHub-Actions-Build für Windows/Linux/Portable-ZIP

## Tests

```bash
python tools/sync_version.py --check
python -m compileall -q . -x '(^|/)(\.git|\.venv|__pycache__|build|dist)(/|$)'
python tools/i18n_audit.py
python tools/dau_first_run_check.py
pytest tests/ -v
```
- **Soft-0-Budget / sanfte Null-Bilanz:** Prüft die Gesamtplanung `Einnahmen − Ausgaben − Ersparnisse`, schlägt Überschüsse für Ersparnisse oder Übertrag vor und behandelt Defizite zuerst über Ersparnisse, danach nur über flexible Ausgaben. Keine automatische Änderung; Fixkosten/POTs bleiben geschützt.
