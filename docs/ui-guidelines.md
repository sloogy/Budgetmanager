# UI & UX Richtlinien (BudgetManager)

## Design-Prinzipien
- **Konsistenz**: Einheitliche Verwendung von Emojis, Abständen und Schriftgrößen.
- **Theming**: Keine hartkodierten Farben im Code. Nutzung des `ThemeManager` oder `UIColors`-Dataclass.
- **Interaktion**: Unterstützung von Tastenkürzeln (Shortcuts) und Kontextmenüs in allen Tabellen.

## Theme-System
- Alle UI-Elemente müssen Theme-aware sein.
- **Häufige Fehler**: Nutzung von `QColor("#...")` oder hartkodiertem `setStyleSheet` mit Farbwerten.
- **Lösung**: Farben über `theme_manager.get_type_colors()` oder zentrale Farbvariablen beziehen.

## Tastenkürzel (Shortcuts)
| Kürzel | Aktion |
|--------|--------|
| **Strg + N** | Schnelleingabe (Global) |
| **Strg + F** | Globale Suche |
| **Strg + Q** | Quick-Add |
| **F2** | Element bearbeiten |
| **Entf** | Element löschen |
| **Strg + Z** | Rückgängig (Undo) |

## UI-Konventionen
- **Dialog-Titel**: Einheitliches Schema (z. B. `⚡ Schnelleingabe`).
- **Tabellen**: 
  - `SelectRows` standardmäßig aktiv.
  - `verticalHeader` ausblenden, wenn Zeilennummern nicht relevant sind.
  - Alternierende Zeilenfarben aktivieren.
- **Nachrichten**: 
  - `critical` für echte Fehler.
  - `warning` für Validierungshinweise.
  - `information` für Erfolgsmeldungen.

## Bekannte UI-Probleme (Work-in-Progress)
- **Shortcut-Kollisionen**: Prüfe immer `main_window.py` auf doppelte Belegungen (z. B. Ctrl+E).
- **Dunkel-Modus**: Prüfe neue Dialoge immer auf Lesbarkeit im "Dracula" oder "Nord" Theme.
