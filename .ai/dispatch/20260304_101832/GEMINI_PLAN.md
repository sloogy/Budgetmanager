Loaded cached credentials.
I will research the existing icon handling and the current implementation of `backup_restore_dialog.py` to ensure the new utility and fix align with the project's structure.

I will read the existing `utils/icons.py` and search for the backup-related methods within the `views/backup_restore_dialog.py` file to understand the current implementation.

I will read the full implementation of `create_backup` in `views/backup_restore_dialog.py` and also check `model/restore_bundle.py` to see the expected parameters for `create_bundle`.

I will read the `_create_bmr_backup` method in `views/backup_restore_dialog.py` to compare its implementation with `create_backup`.

I will search for all occurrences of `create_bundle` in the codebase and also find all emojis used in the project to ensure they are handled correctly.

I will read the entire `utils/icons.py` file again to ensure I have the full content and understand the current implementation of the theme mapping and fallback logic.

I will read the `create_backup` method in `views/backup_restore_dialog.py` again, focusing on the `create_bundle` call to confirm if `users_json_path` is included.

I will search for all emojis in the project again to identify any missing from the `utils/icons.py` mapping and ensure the plan covers them.

I will search for the i18n keys related to "users included" and check the contents of the `locales/` directory to ensure all necessary translations are present.

I will read `locales/de.json` and search for the `settings_included` key to verify its presence and see how it's defined.

Hier ist der Plan und die i18n-Checkliste für die Umsetzung.

### **1. Plan: Utils & Backup-Fix**

#### **Teil 1: `utils/icons.py` (Emoji-Icons mit Theme-Fallback)**
*   **Ziel:** Plattformunabhängige Icons, die unter Linux/KDE native Theme-Icons nutzen und sonst Emojis rendern.
*   **Umsetzung:**
    1.  `get_icon(emoji)`-Funktion sicherstellen (Mapping Emoji → Freedesktop-Icon-Name vorhanden).
    2.  **Priorität 1:** `QIcon.fromTheme(name)` für native Optik.
    3.  **Priorität 2 (Fallback):** `QPixmap` + `QPainter` zeichnet das Emoji direkt.
    4.  **Priorität 3 (Last Resort):** Falls Emoji nicht darstellbar (Heuristik), Zeichnen eines farbigen Kreises mit dem ersten Buchstaben des Emojis (Mapping in `_EMOJI_FALLBACK`).
    5.  **Caching:** `@lru_cache` verwenden, um Performance-Einbußen beim Rendering zu vermeiden.

#### **Teil 2: `backup_restore_dialog.py` (users.json im Backup)**
*   **Ziel:** Vollständige Backups (Datenbank + Settings + User-Konten), um "unterschiedliche Größen"-Bugs zu beheben.
*   **Umsetzung:**
    1.  In `create_backup()` den Pfad via `from model.user_model import _users_file_path` abrufen.
    2.  Beim Aufruf von `create_bundle(...)` den Parameter `users_json_path=_users_file_path()` ergänzen.
    3.  **Validierung:** Erfolg-Meldung (`QMessageBox`) um Info erweitern, ob `users.json` enthalten ist (analog zu den Settings).

---

### **2. i18n Checklist**

*   [ ] **Neue Keys hinzufügen** in `de.json`, `en.json`, `fr.json`:
    *   `dlg.users_included`: "Benutzerkonten wurden mitgesichert" (DE), "User accounts included" (EN), "Comptes utilisateurs inclus" (FR).
*   [ ] **Bestehende Keys prüfen**:
    *   `dlg.settings_included`: Muss in allen Sprachen existieren (für die Konsistenz der Erfolgsmeldung).
    *   `backup.manual_note`: Standard-Kommentar für manuelle Backups prüfen.
*   [ ] **Qualitätssicherung**:
    *   Lauf `python ai/i18n_check.py` nach den Änderungen zur Synchronitätsprüfung.
    *   Sicherstellen, dass Platzhalter in allen Sprachen identisch sind.

---

**Nächster Schritt:** Umsetzung der Änderungen in `utils/icons.py` (Mapping vervollständigen) und `views/backup_restore_dialog.py`.
