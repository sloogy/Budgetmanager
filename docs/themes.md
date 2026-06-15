# Theme-System — BudgetManager v2.0.8

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

Für v2.0.8 wurden keine neuen Theme-Profile eingeführt. Relevant ist vor allem, dass Settings robust über Defaults geladen werden und gespeicherte Designprofile bei Teil-Settings nicht verloren gehen.
