# Architektur & System-Analyse (BudgetManager)

## Übersicht
Der BudgetManager folgt einer **MVC-Architektur** (Model-View-Controller), wobei die Trennung zwischen Datenlogik (`model/`) und Benutzeroberfläche (`views/`) konsequent umgesetzt wird.

## Kern-Komponenten
- **Haupteinstieg**: `main.py` (Initialisierung, Login, MainWindow).
- **Models**:
  - `database.py`: Verbindungshandling (SQLite, WAL-Mode).
  - `migrations.py`: Schema-Versionierung (aktuell v10).
  - `app_paths.py`: Zentrale Pfadverwaltung (Portable Mode).
  - `undo_redo_model.py`: Persistenter Aktions-Stack.
- **Views**:
  - `main_window.py`: Hauptfenster mit Tab-Management.
  - `tabs/`: Hauptansichten (Overview, Budget, Tracking, Categories).

## Identifizierte Architektur-Herausforderungen (Technik-Schulden)
1. **MVC-Verletzungen**: Teilweise werden SQL-Queries direkt in den Views ausgeführt (`overview_tab.py`, `main_window.py`). Diese sollten in entsprechende Models verschoben werden.
2. **"Denglisch" im Code**: Klassen/Methoden sind Englisch, aber Logik-Strings (z. B. 'Ausgaben') sind oft Deutsch hartkodiert.
3. **i18n-Lücken**: Das Internationalisierungssystem wird noch nicht flächendeckend für alle Fehlermeldungen und Dialogtitel eingesetzt.
4. **Fehlerbehandlung**: Inkonsistente Verwendung von stummen `except: pass`-Blöcken vs. Logging.

## Sicherheits-Standards
- **Verschlüsselung**: PBKDF2-HMAC-SHA256 (200.000 Iterationen) für PIN/Passwort.
- **Datenhaltung**: Verschlüsselte DBs laufen im RAM (SQLCipher/Fernet-Struktur).
- **Integrität**: Automatische Backups vor Migrationen oder Resets.

---

*Stand der Analyse: v0.4.8.0*
