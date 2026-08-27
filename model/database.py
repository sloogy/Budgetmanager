from __future__ import annotations

import atexit
import itertools
import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path

logger = logging.getLogger(__name__)


def _configure_connection(conn: sqlite3.Connection, *, is_memory: bool = False) -> None:
    """Setzt Performance- und Sicherheits-Pragmas auf einer SQLite-Connection.

    - foreign_keys=ON  → Fremdschlüssel-Constraints werden geprüft
    - journal_mode=WAL → Write-Ahead-Logging (nur File-DB, nicht :memory:)
    - synchronous=NORMAL → Guter Kompromiss zwischen Speed und Sicherheit
    - busy_timeout=10000 → 10 Sekunden warten statt sofort "database is locked"
    """
    conn.execute("PRAGMA foreign_keys = ON;")
    if not is_memory:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
    conn.execute("PRAGMA busy_timeout = 10000;")
    # Kleine Desktop-Datenbanken profitieren von einem RAM-Tempstore;
    # Sortierungen/Group-Bys im Cockpit/Tracking landen dadurch seltener auf Disk.
    conn.execute("PRAGMA temp_store = MEMORY;")


def open_db(path: str) -> sqlite3.Connection:
    """Öffnet die Haupt-Datenbank mit row_factory und Pragmas."""
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    _configure_connection(conn)
    return conn


def open_db_raw(path: str) -> sqlite3.Connection:
    """Öffnet eine Datenbank ohne row_factory (für Management-Operationen)."""
    conn = sqlite3.connect(path, timeout=10.0)
    _configure_connection(conn)
    return conn


def checkpoint_wal(conn: sqlite3.Connection) -> bool:
    """Schreibt das WAL in die .db-Datei zurueck und leert es.

    Warum das noetig ist: ``_configure_connection`` schaltet fuer jede Datei-DB
    WAL ein. Committete Transaktionen stehen danach zunaechst nur in
    ``budgetmanager.db-wal``, nicht in ``budgetmanager.db``. Jeder Vorgang, der
    die .db-Datei als Datei anfasst - Backup-Bundle, Datenuebernahme in einen
    anderen Ordner - wuerde ohne Checkpoint einen veralteten Stand mitnehmen,
    und zwar unbemerkt: Die Pruefsumme im Manifest passt ja zu dem, was
    kopiert wurde.

    Rueckgabe: ``True``, wenn das WAL vollstaendig zurueckgeschrieben wurde.
    ``False`` heisst, dass ein anderer Leser/Schreiber die Datei gerade
    blockiert - dann bleibt die .db-Datei hinter dem WAL zurueck und der
    Aufrufer muss einen anderen Weg gehen.
    """
    try:
        row = conn.execute("PRAGMA wal_checkpoint(TRUNCATE);").fetchone()
    except sqlite3.Error as exc:
        logger.debug("wal_checkpoint fehlgeschlagen: %s", exc)
        return False
    if row is None:
        # :memory: und journal_mode=DELETE liefern keine Zeile - dort gibt es
        # kein WAL, also ist auch nichts nachzuholen.
        return True
    busy = row[0]
    return not busy


_savepoint_counter = itertools.count()


@contextmanager
def db_transaction(conn: sqlite3.Connection):
    """Context Manager für atomare Datenbank-Transaktionen.

    Verwendung::

        from model.database import db_transaction

        with db_transaction(conn):
            conn.execute("INSERT INTO …")
            conn.execute("UPDATE …")
        # → automatisch COMMIT bei Erfolg, ROLLBACK bei Exception

    Läuft bereits eine Transaktion, wird der Block über einen SAVEPOINT
    geklammert. Vorher lief er dort ohne jede Klammer mit: ein Fehler rollte
    dann **nichts** zurück, und die halb geschriebenen Zeilen blieben in einer
    fremden Transaktion stehen, bis irgendein späterer ``commit()`` sie
    festschrieb. Ein SAVEPOINT macht den Block auch verschachtelt atomar, ohne
    die äußere Klammer vorzeitig zu schließen.
    """
    if conn.in_transaction:
        name = f"db_tx_{next(_savepoint_counter)}"
        conn.execute(f"SAVEPOINT {name}")
        # try/finally statt except: Der Block soll auch bei GeneratorExit oder
        # KeyboardInterrupt zurueckgerollt werden, und der Ausnahmen-Ratchet
        # bekommt keinen weiteren breiten Handler.
        erfolgreich = False
        try:
            yield conn
            erfolgreich = True
        finally:
            if not erfolgreich:
                conn.execute(f"ROLLBACK TO {name}")
            conn.execute(f"RELEASE {name}")
        return
    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


# ── Verschlüsselter Modus (In-Memory) ──────────────────────────


class EncryptedSession:
    """Verwaltet eine verschlüsselte In-Memory-DB-Session.

    Hält die Connection, den DB-Key und den Dateipfad.
    Bietet save() zum verschlüsselten Speichern auf Disk.
    Registriert sich bei atexit für automatisches Speichern.

    Verwendung::

        session = EncryptedSession.open_with_key("user.enc", db_key, salt)
        conn = session.conn
        session.save()
    """

    def __init__(
        self, conn: sqlite3.Connection, enc_path: str, db_key: bytes, salt: bytes
    ):
        self.conn = conn
        # intern halten (damit wir später Properties anbieten können)
        self._enc_path = str(enc_path)
        self._db_key = db_key
        self._salt = salt
        self._closed = False
        self._frozen = False  # wenn True: keine Saves auf Disk (z.B. nach Restore)
        self._saving = False

        # Im verschluesselten Modus ist die SQLite-DB im RAM.  Jeder erfolgreiche
        # conn.commit() muss deshalb direkt die .enc-Datei aktualisieren, sonst
        # koennen native Qt/PySide-Abstuerze die letzten Aenderungen verlieren.
        try:
            if hasattr(self.conn, "set_after_commit_callback"):
                self.conn.set_after_commit_callback(self._save_after_commit)
        except Exception as exc:
            logger.debug("Commit-Auto-Save konnte nicht aktiviert werden: %s", exc)

        # Auto-Save bei App-Exit
        atexit.register(self._atexit_save)

    @classmethod
    def open_with_key(
        cls, enc_path: str, db_key: bytes, salt: bytes
    ) -> EncryptedSession:
        """Öffnet eine verschlüsselte DB mit dem db_key."""
        from model.crypto import decrypt_db_from_file

        conn = decrypt_db_from_file(enc_path, db_key)
        return cls(conn, enc_path, db_key, salt)

    def save(self, *, reason: str = "manual") -> None:
        """Speichert die In-Memory-DB verschlüsselt auf Disk."""
        if self._closed or self._frozen or self._saving:
            return
        self._saving = True
        try:
            from model.crypto import save_memory_db

            save_memory_db(self.conn, self._enc_path, self._db_key, self._salt)
            if reason == "commit":
                logger.debug(
                    "Verschlüsselte DB nach Commit gespeichert: %s",
                    Path(self._enc_path).name,
                )
            else:
                logger.info(
                    "Verschlüsselte DB gespeichert: %s", Path(self._enc_path).name
                )
        except Exception as e:
            logger.error("Fehler beim Speichern der verschlüsselten DB: %s", e)
        finally:
            self._saving = False

    def _save_after_commit(self, _reason: str = "commit") -> None:
        """Persistiert erfolgreiche DB-Commits sofort in die verschlüsselte Datei."""
        self.save(reason="commit")

    def close(self) -> None:
        """Speichert (falls aktiv) und schliesst die Session."""
        if self._closed:
            return
        # Wenn die Session eingefroren wurde (z.B. nach Restore),
        # speichern wir NICHT mehr auf Disk, schliessen aber die Connection sauber.
        if not self._frozen:
            self.save(reason="close")
        try:
            self.conn.close()
        finally:
            self._closed = True

    def freeze(self) -> None:
        """Stoppt zukünftige Saves auf Disk.

        Wichtig nach einem Restore/Import, wenn wir die .enc Datei ersetzt haben,
        damit der Auto-Save nicht sofort wieder die alte In-Memory-DB darüber schreibt.
        """
        self._frozen = True

    def unfreeze(self) -> None:
        """Hebt freeze() wieder auf (z.B. wenn Restore abgebrochen wurde)."""
        self._frozen = False

    # ── Read-only Properties (für Backup/Tools) ─────────────────

    @property
    def enc_path(self) -> str:
        return self._enc_path

    @property
    def db_key(self) -> bytes:
        return self._db_key

    @property
    def salt(self) -> bytes:
        return self._salt

    def _atexit_save(self) -> None:
        """Wird bei App-Exit aufgerufen."""
        if not self._closed:
            try:
                self.save(reason="atexit")
            except Exception as e:
                logger.error("atexit save failed: %s", e)
