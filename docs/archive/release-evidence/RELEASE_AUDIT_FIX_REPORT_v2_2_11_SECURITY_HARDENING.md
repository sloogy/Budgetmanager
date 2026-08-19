# BudgetManager v2.2.11 – SICHERHEITSANALYSE

## Rahmen
Basis: **v2.2.10 BACKUP AUTH**. Randbedingung: **Die Datenbank ist immer verschlüsselt.**

Genau das verschiebt die Angriffsfläche. Wenn die Nutzdaten sicher verschlüsselt
sind, greift ein Angreifer nicht die Chiffre an, sondern:

1. **den Schlüssel** – wo liegt er, wer darf ihn lesen?
2. **den Weg hinein** – was gelangt ungeprüft in die Installation?

Beide Achsen wurden systematisch geprüft (Krypto, Schlüsselspeicher,
Backup/Restore-Kette, SQL, Pfad-/Dateihandling, Logging).

---

## Befunde und Fixes

### 🔴 HOCH – Schlüsselmaterial war world-readable
`users.json` wurde mit dem Standard-umask geschrieben, auf typischen
Linux-Systemen **`0644`**. Empirisch bestätigt:

```
users.json Rechte: 0o644  (world-readable: True)
  !! db_key_b64 = UaxF7MSoswo2hVD2raOu... (Länge 44)
```

- Bei **Quick-Konten** liegt `db_key_b64` dort **im Klartext**. Jeder andere
  lokale Benutzer konnte die Datei lesen und damit die `.enc` **vollständig
  entschlüsseln**. Die Verschlüsselung war gegenüber lokalen Mitbenutzern
  faktisch wirkungslos.
- Bei **PIN/Passwort-Konten** lagen `wrapped_db_key_b64` und `pw_hash` offen –
  Material für einen bequemen Offline-Brute-Force.

**Fix:** Neues Qt-freies Modul `model/file_permissions.py`. `users.json`, die
`.enc`-Datenbank und `.bmr`-Backups werden mit **`0600`** abgelegt. Entscheidendes
Detail: Die Rechte werden **auf der Temp-Datei vor dem `os.replace`** gesetzt –
sonst gäbe es ein Zeitfenster, in dem die fertige Datei mit umask-Rechten
sichtbar ist. Unter Windows sind POSIX-Modi wirkungslos; das ist korrekt und
unschädlich (dort schützen die ACLs des Benutzerprofils). `chmod`-Fehler auf
FAT/exFAT-Sticks werden geschluckt, damit ein Backup daran nicht scheitert.

### 🔴 HOCH – Backups wurden nie auf Integrität geprüft
Das Manifest enthielt seit jeher `sha256` der Quelldatenbank. **Verifiziert hat
ihn niemand.** Ein beschädigtes oder gezielt manipuliertes `.bmr` wurde
kommentarlos **über die aktive Datenbank** gespielt.

**Fix:** `restore_bundle.verify_bundle()` prüft Archivstruktur, Grössen und den
SHA256 gegen das Manifest (`hmac.compare_digest`). Eingehängt in **beide**
Restore-Pfade: den normalen Restore (`_extract_bmr_to_temp`) und den
Konto-Restore mit `users.json` (`_restore_full_account_bundle`). Sehr alte
Bundles ohne Hash werden nicht hart abgewiesen, aber protokolliert – Struktur
und Grössen sind dann trotzdem geprüft.

### 🟠 MITTEL – Zip-Slip strukturell ausgeschlossen
Ein `.bmr` ist ein ZIP. Es gilt jetzt eine **Whitelist erlaubter Einträge**
(`manifest.json`, `database.enc|db`, `settings.json`, `users.json`). Ein Archiv
mit Fremdeinträgen wird abgewiesen; **kein Name aus dem Archiv wird je als
Pfad verwendet**.

### 🟠 MITTEL – Zip-Bomb-Schutz
Harte Grössenlimits: Metadateien je 5 MB, Datenbank 4 GB. Es wird zusätzlich
**hart begrenzt gelesen**, damit ein gefälschter Grössen-Header im ZIP-Header
nicht ausreicht, um den Speicher zu fluten.

### 🟠 MITTEL – Ziel-Dateiname aus dem Backup gehärtet
Im Konto-Restore stammte der Ziel-Dateiname aus dem Manifest. `Path(...).name`
verhinderte bereits Traversal; jetzt wird zusätzlich die **Endung erzwungen**,
damit ein präpariertes Bundle die DB-Bytes nicht über `users.json` oder
`settings.json` schreiben kann. Kollision mit `users.json` wird explizit abgewiesen.

---

## Geprüft und für gut befunden (bewusst **nicht** verändert)

| Bereich | Ergebnis |
|---|---|
| Schlüsselableitung | PBKDF2-HMAC-SHA256, **600 000 Runden** (OWASP), `os.urandom` für Salt und db_key |
| Nutzdaten | Fernet (AES-CBC + HMAC), Salt pro Datei |
| Domain-Separation | `pw_hash` nutzt `PW_VERIFY_CONTEXT` → **nicht key-äquivalent**; Legacy-Hashes werden beim Login erkannt und migriert |
| Vergleiche | durchgehend `hmac.compare_digest` → keine Timing-Leaks |
| SQL-Injection | alle Werte über Platzhalter; f-String-SQL nur für Tabellennamen aus festen Whitelists (`_safe_table`, `_RESET_TABLE_WHITELIST`) |
| Logging | keine Geheimnisse (Passwort, PIN, db_key, Restore-Key) im Log |
| Atomarität | `os.replace` + `fsync` auf allen sensiblen Schreibpfaden |

---

## Bewusst unverändert: der Quick-Modus

Bei **Quick-Konten liegt der `db_key` im Klartext** in `users.json` – ohne
Geheimnis gibt es schlicht nichts, womit man ihn verschlüsseln könnte. Das ist
der inhärente Preis des schnellen Zugangs, nicht ein behebbarer Bug. Er ist
jetzt wenigstens durch Dateirechte (`0600`) abgesichert.

**Wer echten Schutz vor lokalen Mitbenutzern braucht, muss PIN oder Passwort
verwenden.** Für deinen Testbetrieb ist Quick weiterhin genau richtig.

---

## Empirische Verifikation

Angriffsszenarien gegen `verify_bundle()`:

| Szenario | Ergebnis |
|---|---|
| gültiges Bundle | akzeptiert (`database.enc`), Rechte `0600` |
| DB-Inhalt manipuliert, Manifest unverändert | **abgewiesen** – „Pruefsumme stimmt nicht" |
| DB abgeschnitten (halbe Übertragung) | **abgewiesen** |
| Zip-Slip (`../../../../etc/cron.d/pwn`) | **abgewiesen** – unerwarteter Eintrag |
| Zip-Bomb (6 MB `settings.json`) | **abgewiesen** – Limit überschritten |
| kein gültiges ZIP | **abgewiesen** |
| Manifest fehlt | **abgewiesen** |

Dateirechte nach dem Fix: `users.json` → `0600`, `.enc` → `0600`, `.bmr` → `0600`.

---

## Tests / Gates
- Versions-Sync: **PASS** (2.2.11)
- Compile: **PASS**
- i18n-Audit + Parität: **PASS** (de=en=fr, je 2308 Keys) – keine neuen Keys nötig
- DAU-Erststart: **PASS**
- Release-Logik-Audit: **100 Loops, 0 Findings**
- Deep-Logic-Audit: **500 Loops / 3500 Checks, 0 Findings**
- Lint-/Release-Prozedur: **PASS**
- pytest headless: **397 passed, 2 skipped** (384 + 13 neue Sicherheitstests)

## Einschränkungen
- Die 2 übersprungenen Tests sind die bekannten Qt/PySide-GUI-Smoke-Tests.
- **Bestandsdateien:** Die Rechte werden beim nächsten Schreiben korrigiert. Wenn
  du sichergehen willst, einmal auf Fedora ausführen:
  `chmod 600 ~/.local/share/BudgetManager/users.json ~/.local/share/BudgetManager/*.enc`
  (Pfad ggf. anpassen).
- Ein Angreifer mit **Root-Rechten** oder physischem Zugriff auf ein entsperrtes
  System ist durch Dateirechte nicht aufzuhalten – das ist Stand der Technik.

## Releasefähigkeit

**v2.2.11 SECURITY HARDENING**
