# BudgetManager v2.2.44 – Vergleich, Konsolidierung und Enterprise-Audit

**Stand:** 28. Juli 2026  
**Ausgangsstände:**

1. `BudgetManager Source 2 2 43 DASHBOARD LAYOUT DESIGNMANAGER MERGED`
2. `BudgetManager Source 2 2 43 MERGED LAYOUT DASHBOARD`

## 1. Vergleichsumfang

- DesignManager-Hoheit und Theme-Wechsel
- Dashboard-/KPI-Karten und Diagramme
- automatisches und fixiertes Kachellayout
- Drag-and-drop in Ein- und Zweispaltenansicht
- Reihenfolge-/Spaltenpersistenz und Migration alter Settings
- Übersetzungen, Benutzerhilfe und Versionsreferenzen
- Regressionstests und Release-Werkzeuge

Die beiden Archive hatten 38 inhaltlich unterschiedliche gemeinsame Dateien. Die DesignManager-Variante enthielt zusätzlich vier relevante Dateien, darunter zwei gezielte Merge-/Layout-Regressionstests; die Parallelvariante enthielt eine separate Versionsreferenz-Prüfung und eine historische Implementierungsnotiz.

## 2. Übernommene bessere Ansätze

| Bereich | Übernommener Ansatz | Begründung |
|---|---|---|
| Design und Farben | DesignManager-Variante | Cockpit, Trends, Drag-Griff und Chart-Fläche nutzen benannte Objektrollen und das zentrale QSS. Keine lokalen Dashboard-Festfarben. |
| Diagramm-Kachel | DesignManager-Variante | `charts` bleibt Teil der kanonischen Panel-Liste, Reihenfolge, Spaltenzuordnung, Leerzustandslogik und Persistenz. |
| Theme-Wechsel | DesignManager-Variante | Cockpit wird nach Theme-Wechsel neu aufgebaut; Diagramme und Trendzustände übernehmen das neue Profil sofort. |
| Layoutmigration | DesignManager-Variante | Neues und vorübergehendes Settings-Schema werden gelesen und synchron gehalten: `cockpit_layout_mode`/`cockpit_panel_columns` sowie `cockpit_tiles_fixed`/`cockpit_tile_columns`. |
| Einspalten-Drag-and-drop | DesignManager-Variante | Die zugrunde liegende linke/rechte Spaltenzuordnung bleibt bei schmalem Fenster erhalten. |
| Bedienzugang | DesignManager-Variante | Fixierung bleibt sowohl sichtbar in der Cockpit-Kopfzeile als auch unter **Ansicht → Cockpit-Layout** erreichbar. |
| Benutzerhilfe | Parallelvariante | Automatik, Fixierung, Drag-Griff, Spaltenwechsel, Responsive-Verhalten und Reset werden deutlich vollständiger erklärt. |
| Versionsreferenz-Schutz | Parallelvariante | Die historische Versionssperre erhält ein eigenes Regressionstest-Modul statt nur einer Nebenprüfung. |
| Persistenz | neue Konsolidierung | `Settings.set_many()` schreibt zusammengehörige Layoutwerte in einem Speichervorgang. Das verhindert teilweise gespeicherte Mischzustände und reduziert `fsync`-Schreibvorgänge. |
| Idempotenz | neue Konsolidierung | Wiederholtes Setzen desselben Layoutmodus aktualisiert die Darstellung, sendet aber kein falsches Änderungssignal. |

## 3. Bewusst nicht übernommen

- Entfernen der Diagramm-Kachel aus `cockpit_panel_order` und `cockpit_panel_columns`
- lokales `QChartView.setStyleSheet(...)`
- Inline-Farben für Titel, Untertitel und KPI-Trends
- Wegfall des Cockpit-Refreshs beim Theme-Wechsel
- Entfernen der Übergangsschlüssel für Nutzer bereits gestarteter Zwischenversionen
- Menü-only-Lösung ohne sichtbaren Fixier-Schalter im Cockpit
- verkürzte oder auf ältere Versionen zurückgesetzte Dokumentation

Diese Punkte hätten bereits behobene Fehler erneut eingeführt oder den DesignManager teilweise außer Kraft gesetzt.

## 4. Neue Härtungen in v2.2.44

- Atomare Mehrfachspeicherung mit `Settings.set_many()`
- vollständige Layout-Hilfe in Deutsch, Englisch und Französisch
- eigenes Gate `test_release_2244_version_reference_lock.py`
- kombiniertes Gate `test_release_2244_consolidated_merge.py`
- Schutz für DesignManager-Hoheit, Chart-Persistenz, beide Settings-Schemata, Hilfetexte und Übersetzungen
- aktuelle statische HTML-Hilfe neu erzeugt
- Versionsdateien, Installer-Metadaten, Update-Templates und Lockfile-Köpfe auf v2.2.44 synchronisiert

## 5. Prüfergebnisse

### Gezielte Dashboard-/Merge-Regressionen

- **70 Tests bestanden**
- geprüft: Cockpit v2.2.40, Drag-Layout v2.2.41, Tile-Pinning, Dashboard-Look v2.2.42, Merge v2.2.43, neue v2.2.44-Gates und Schutz gegen verwaiste KPI-Fenster

### Gesamte Pytest-Suite

- **732 Tests bestanden**
- **10 Tests kontrolliert übersprungen**
- **2 umgebungsabhängige Tests nicht ausgeführt**:
  - Bandit-Delta-Gate: Modul `bandit` ist in der Audit-Umgebung nicht installiert.
  - KILLCRITIC-Qt-Worker: `PySide6` ist in der Audit-Umgebung nicht installiert.

Die übrigen Tests wurden in vier Dateishards ausgeführt. Das Release-Lint-Gate wurde wegen seiner Baum-Bereinigung zusätzlich isoliert geprüft und bestand.

### Weitere Gates

- Versionssynchronisierung: **PASS**
- Python-Kompilierung: **PASS**
- i18n-Audit DE/EN/FR: **PASS**
- Handbuch-Vollständigkeitsaudit: **PASS**
- DAU-Enterprise-Audit: **10 Loops, 165.960 Prüfungen, 0 Findings**
- Release-Lint nach Cleanup: **PASS**
- Final-Release-Audit: **1.000 Loops, 19.125 Prüfungen, 0 Fehler, 0 Warnungen**

## 6. Enterprise-Release-Audit – 10.000 Loops

Ausgeführt mit:

```bash
python tools/enterprise_release_audit_10000.py \
  --loops 10000 \
  --seed 20260728 \
  --json-out ENTERPRISE_RELEASE_AUDIT_10000_v2_2_44.json
```

**Ergebnis:**

- Status: **PASS**
- Loops: **10.000**
- Prüfungen: **112.000**
- Findings: **0**

Jedes Szenario lief exakt 1.000-mal:

1. Kategoriegebundene und manuelle Tags beim Kategorienwechsel
2. Tag-Lebenszyklus über Löschen, Undo und Redo
3. Buchungsquelle über alle Leseroutinen
4. Sparziel-Zustandsmaschine mit Add/Update/Delete/Undo/Redo
5. Filter gegen unabhängiges Oracle
6. Kategorie-Rename über abhängige Daten
7. Budget-/Jahreskopie
8. wiederkehrende Termine und Monatsgrenzen
9. sichere ZIP-Extraktion inklusive Pfad-Traversal-Abwehr
10. SQLite-Integrität, Fremdschlüssel und verwaiste Tag-Zuordnungen

Der maschinenlesbare Nachweis liegt in `ENTERPRISE_RELEASE_AUDIT_10000_v2_2_44.json`; die 1.000er Release-Matrix liegt in `FINAL_RELEASE_AUDIT_1000_MATRIX_v2_2_44.csv`.

## 7. Freigabestatus

Der konsolidierte Source-Stand ist für einen manuellen Plattform-Smoke-Test geeignet. Vor einer endgültigen Windows-/Fedora-Binärfreigabe bleiben sinnvoll:

- Start und Bedienung mit installiertem PySide6 6.10.x
- visueller Wechsel mehrerer Designprofile
- Drag-and-drop bei breitem und schmalem Fenster
- Bandit-Gate in der vorgesehenen Release-Umgebung
- KILLCRITIC-UI-Audit mit echter Qt-Offscreen-Unterstützung
