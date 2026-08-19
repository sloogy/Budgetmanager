# BudgetManager v2.2.43 – Merge- und Prüfbericht

**Datum:** 28. Juli 2026  
**Ausgangsversionen:**

- v2.2.41 – Cockpit Auto/Fixed Drag Layout
- v2.2.42 – Dashboard Look

## Ergebnis

Beide Entwicklungszweige wurden zu **BudgetManager v2.2.43** zusammengeführt. Die Dashboard-Optik aus v2.2.42 bleibt erhalten, während die robustere Layout-, Persistenz- und Drag-and-drop-Logik aus v2.2.41 übernommen wurde.

Der **DesignManager bleibt die verbindliche Quelle für Farben und Styles**. Der Cockpit-Code setzt keine eigenen Farbcodes. Dashboard-Karten, Überschriften, KPI-Trends, Drag-Griff und Diagrammfläche verwenden benannte Objektrollen, deren QSS ausschließlich in `theme_manager.py` erzeugt wird. Diagrammfarben werden über `views.ui_colors.ui_colors()` aus dem aktiven Designprofil bezogen.

## Behobene Merge-Konflikte

1. **Fehlender KPI-Konstruktorparameter**  
   v2.2.42 übergab `icon=...` an `_Card`, der Konstruktor akzeptierte diesen Parameter jedoch nicht. Das hätte das Cockpit beim Aufbau beendet.

2. **Diagramm-Kachel aus Panel-Liste herausgefiltert**  
   Die neue Kachel `charts` war nicht in allen kanonischen Panel- und Reihenfolgelisten enthalten. Sie ist jetzt Teil von Presets, Standardsortierung, Sichtbarkeit und Spaltenzuordnung.

3. **Fehlender Sammelbereich `action_needed`**  
   Der in v2.2.40 gebündelte Handlungsbedarf ist wieder Bestandteil der kanonischen Reihenfolge. Alte Schlüssel `warnings`, `budget_warnings` und `missing` werden migriert.

4. **Einspalten-Drag-and-drop konnte Spalten verlieren**  
   Die robustere v2.2.41-Logik bewahrt die zugrunde liegende Links-/Rechts-Zuordnung auch im responsiven Einspaltenmodus.

5. **Nicht definierte Theme-Variable `border`**  
   Das Dashboard-QSS aus v2.2.42 referenzierte eine nicht definierte Variable. `border` wird nun aus dem aktiven Profilwert `tabelle_gitter` abgeleitet.

6. **Lokale Diagrammformatierung**  
   `QChartView.setStyleSheet(...)` wurde entfernt. Die Diagrammfläche trägt die Rolle `cockpitChartView`; Hintergrund und Rahmen werden im DesignManager gesetzt.

7. **Theme-Wechsel aktualisierte Diagramme/Trends nicht sicher**  
   Nach einem Profilwechsel wird das Cockpit neu aufgebaut beziehungsweise aktualisiert, sodass QtCharts, KPI-Trends und profilabhängige Farben sofort wechseln.

## Layoutverhalten

### Automatikmodus

- Standardmodus für neue und bestehende Installationen, sofern nicht anders gespeichert.
- Leere Bereiche schrumpfen auf ihren kompakten Leerzustand.
- Leere Bereiche sinken innerhalb ihrer zugewiesenen Spalte stabil nach unten.
- Sobald wieder Inhalt vorhanden ist, gilt wieder die normale gespeicherte Reihenfolge.
- Drag-and-drop ist deaktiviert und der Griff unsichtbar.

### Fixierter Modus

- Aktivierbar in der Cockpit-Kopfzeile sowie über **Ansicht → Cockpit-Layout**.
- Dedizierter Drag-Griff verhindert versehentliches Verschieben beim Bedienen der Kachel.
- Kacheln können in ihrer Spalte und zwischen beiden Spalten verschoben werden.
- Reihenfolge und Spaltenzuordnung werden sofort gespeichert.
- Im schmalen Einspaltenlayout bleibt die ursprüngliche Zweispaltenzuordnung erhalten.

## Einstellungsmigration

Die Version liest und synchronisiert beide zwischenzeitlich verwendeten Schemas:

- kanonisch aus v2.2.41:
  - `cockpit_layout_mode`
  - `cockpit_panel_columns`
- Übergangsschema aus v2.2.42:
  - `cockpit_tiles_fixed`
  - `cockpit_tile_columns`

Dadurch wird weder ein bereits angepasstes v2.2.41- noch ein v2.2.42-Layout ungefragt zurückgesetzt.

## DesignManager-Schutz

Eigene Merge-Regressionstests prüfen unter anderem:

- keine literal eingebetteten Farben in Cockpit, Kachelcontainer oder Diagrammcode,
- alle visuellen Rollen besitzen Objektkennungen und DesignManager-QSS,
- KPI-Trendfarben werden über die dynamische Eigenschaft `trendState` gesetzt,
- Diagrammrahmen/-hintergrund liegen im DesignManager,
- Theme-Wechsel aktualisiert das Cockpit,
- `border`, positive und negative Zustandsfarben stammen aus Profilwerten,
- die lokale MainWindow-Ergänzung enthält nur strukturelle Regeln, keine Farben.

## Prüfergebnisse

| Prüfung | Ergebnis |
|---|---:|
| Merge-spezifische Cockpit-/DesignManager-Tests | **47/47 bestanden** |
| Breite Pytest-Suite, ausführbare Tests | **722 bestanden** |
| Kontrolliert übersprungene Tests | **10** |
| Nicht ausführbar wegen fehlender Umgebungspakete | **2** |
| Final Release Audit | **1.000 Loops / 19.125 Checks / 0 Fehler / 0 Warnungen** |
| DAU Enterprise Audit | **10 Loops / 165.960 Checks / 0 Funde** |
| Python-Bytecode-Kompilierung | **bestanden** |
| i18n-Audit DE/EN/FR | **bestanden** |
| Lint-/Release-Prozedur | **bestanden** |

### Umgebungsbedingt nicht ausgeführte Prüfungen

1. **Bandit-Release-Gate**  
   Das Paket `bandit==1.9.4` ist in der Ausführungsumgebung nicht installiert. Ein Installationsversuch scheiterte, weil der verfügbare Paketindex diese Version nicht bereitstellte.

2. **Qt-Offscreen-KILLCRITIC-Smoke-Test**  
   `PySide6==6.10.3` ist in der Ausführungsumgebung nicht installiert. Daher konnte kein echter QWidget-/QtCharts-Lauf gestartet werden.

Diese beiden Punkte sind keine festgestellten Codefehler. Sie bleiben jedoch als **noch auf einem System mit den vollständigen Entwicklungsabhängigkeiten auszuführende Release-Gates** dokumentiert.

## Freigabeeinschätzung

Der Merge ist statisch, logisch, hinsichtlich Persistenz und durch die Qt-freien Release-Audits konsistent. Für die endgültige binäre Freigabe sollte auf dem vorgesehenen Fedora-/Windows-Testsystem noch ein visueller Smoke-Test mit installiertem PySide6 erfolgen:

- Start mit hellem und dunklem Profil,
- Umschalten Automatik/Fixiert,
- Drag-and-drop innerhalb und zwischen Spalten,
- Fenster schmal/breit ziehen,
- Neustart und Prüfung der gespeicherten Positionen,
- Profilwechsel bei sichtbaren KPI-Trends und Diagrammen.
