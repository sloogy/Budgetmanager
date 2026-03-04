# Code-Inkonsistenz-Analyse: BudgetManager

Diese Analyse dokumentiert identifizierte Inkonsistenzen in der Architektur, den Konventionen und der UI-Struktur des Projekts.

## 1. Architektur: MVC-Verletzungen
Es besteht kein konsistentes Muster für den Datenzugriff. Während die Model-Schicht existiert, wird sie oft umgangen.

*   **Befund:** In `views/tabs/overview_tab.py` und `views/main_window.py` werden SQL-Queries direkt über `self.conn.execute()` ausgeführt.
*   **Risiko:** Hohe Kopplung zwischen UI und Datenbank-Schema; Erschwerung von Tests und Schema-Migrationen.
*   **Soll-Zustand:** Datenzugriff ausschließlich über spezialisierte Klassen in `model/` (z. B. `BudgetModel`).

## 2. Sprachlicher Mix (Denglisch)
Die Codebasis verwendet eine Mischung aus Deutsch und Englisch, was zu unnötiger Komplexität führt.

*   **Befund:** Klassen/Methoden sind Englisch, aber Datenbank-Keys und interne Logik-Strings (z. B. `'Ausgaben'`, `'Einkommen'`) sind Deutsch hartkodiert.
*   **Folge:** Notwendigkeit von Mapping-Funktionen in `utils/i18n.py` (z. B. `db_typ_from_display`), um zwischen Anzeige-Sprache und DB-Keys zu vermitteln.
*   **Soll-Zustand:** Konsistente Verwendung von englischen Bezeichnern in der Logik und Datenbank; Lokalisierung ausschließlich in der View-Schicht.

## 3. Lückenhafte Internationalisierung (i18n)
Das vorhandene i18n-System wird nicht flächendeckend eingesetzt.

*   **Befund:** Hartkodierter HTML-Text in `views/main_window.py` (AboutDialog) und lückenhafte Übersetzung von Fehlermeldungen.
*   **Befund:** Inkonsistente Verwendung von Emojis in Window-Titeln.
*   **Soll-Zustand:** Alle benutzerseitigen Texte müssen über `i18n.tr()` geladen werden.

## 4. UI- und Theme-Inkonsistenzen
Das visuelle Erscheinungsbild ist in einigen Bereichen hartkodiert, was das Theme-System aushebelt.

*   **Theming:** In `views/tabs/overview_tab.py` und diversen Dialogen sind Farben direkt im Code definiert, statt `theme_manager.py` oder CSS-Variablen zu nutzen.
*   **Layout:** Margins und Spacing variieren stark zwischen verschiedenen Dialogen (z. B. `budget_entry_dialog.py` vs. `savings_goals_dialog.py`).
*   **Shortcuts:** Dezentrale Definition führt zu Kollisionen (z. B. `Ctrl+E`).

## 5. Fehlerbehandlung
Einheitliche Standards für das Error-Reporting fehlen innerhalb der Module.

*   **Befund:** Mischung aus leisem Ignorieren (`except Exception: pass`), Debug-Logging und dem globalen `excepthook`.
*   **Soll-Zustand:** Einheitliches Logging-Niveau und (wo angebracht) benutzerfreundliche Fehlermeldungen über das i18n-System.
