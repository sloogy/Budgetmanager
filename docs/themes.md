# Theme-System — BudgetManager v2.2.67

## Überblick

BudgetManager nutzt Designprofile unter `views/profiles/` sowie zentrale Farbhelfer in `views/ui_colors.py` und `theme_manager.py`.

## Verwendung

1. Einstellungen öffnen.
2. Bereich Darstellung wählen.
3. Designprofil auswählen.
4. Speichern oder anwenden.

## Technische Hinweise

- Profile liegen als JSON-Dateien unter `views/profiles/`.
- Die App speichert das aktive Profil in `active_design_profile`.
- Zuletzt genutzte helle/dunkle Profile werden separat gespeichert.
- Harte Farben in Widgets sollten vermieden werden; nutze zentrale UI-Farben.

## Release-Hinweis

v2.2.43 führt kein weiteres Profil ein, sondern verbindet die Optik aus v2.2.42 mit dem Kachellayout aus v2.2.41. Der DesignManager bleibt die alleinige Quelle für Dashboard-Hintergründe, Ränder, Texte, Akzent-, Status- und Trendfarben. Auch Drag-Griff, Leerzustände und KPI-Typografie werden über Objektrollen im zentralen Stylesheet gestaltet. Beim Theme-Wechsel werden Cockpit, Diagramme und Trends neu aufgebaut.

## Mitternacht – Violett (v2.2.42)

Dunkles Profil nach dem Vorbild moderner Dashboards: fast schwarzer Hintergrund, abgesetzte Kacheln, violetter Akzent `#7150f0`. Der Akzent ist bewusst etwas dunkler als die Vorlage — mit `#7c5cfc` erreichte weiße Schrift darauf nur 4.38:1 und verfehlte WCAG AA.
