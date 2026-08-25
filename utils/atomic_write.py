"""Schreiben, das einen Stromausfall uebersteht.

``pfad.write_text(...)`` ueberschreibt die Datei an Ort und Stelle. Faellt der
Strom mittendrin aus, liegt danach die halbe Datei da - genau der Fall, den
Loop 13 aufraeumen musste und Loop 21 in FPM noch einmal fand.

Drei Dinge gehoeren dazu, und keines allein reicht:

1. **In eine Zwischendatei schreiben und umbenennen.** ``os.replace`` ist
   atomar: Es gibt die Datei entweder ganz alt oder ganz neu, nie halb.
2. **``fsync`` auf die Zwischendatei.** Ohne ihn steht der Inhalt nur im
   Cache des Systems. Das Umbenennen ist dann atomar, aber es benennt
   moeglicherweise eine leere Datei um.
3. **``fsync`` auf das Verzeichnis.** Sonst ueberlebt zwar der Inhalt, aber
   der Verzeichniseintrag, der auf ihn zeigt, ist noch nicht geschrieben.

Der Name der Zwischendatei traegt die Prozessnummer. Zwei Instanzen, die
gleichzeitig speichern, benutzten sonst dieselbe und schrieben sich
gegenseitig kaputt - die Instanzsperre aus Loop 14 deckt nur denselben
Datenordner ab.

Wortgleich in FPM, BudgetManager, FreizeitManager und LifePlanner.
"""

from __future__ import annotations

import logging
import os
import secrets
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TextIO

_log = logging.getLogger(__name__)


def _temp_path(ziel: Path) -> Path:
    """Erzeugt einen kollisionsfreien Temp-Namen auch innerhalb eines Prozesses.

    Die PID allein trennt mehrere App-Instanzen, aber nicht zwei Threads oder
    verschachtelte Saves derselben Instanz. Gerade unter Windows führt eine
    solche Kollision schnell zu ``PermissionError``/``FileNotFoundError`` beim
    anschliessenden ``os.replace``. Thread-ID + Zufallstoken verhindern das,
    die PID bleibt für Diagnose und die bestehende Invariante sichtbar.
    """
    token = secrets.token_hex(4)
    return ziel.with_name(
        f"{ziel.name}.tmp-{os.getpid()}-{threading.get_ident()}-{token}"
    )


def _replace_atomically(source: Path, target: Path) -> None:
    """``os.replace`` mit kurzem Retry für typische Windows-Dateisperren.

    Virenscanner, Indexer und Sync-Clients können eine gerade geschlossene
    Datei für wenige Millisekunden exklusiv halten. Ein sofortiger Abbruch
    verliert dann z.B. eine Settings-Änderung, obwohl ein zweiter Versuch
    erfolgreich wäre. Nur bekannte Sharing-/Access-Fehler werden wiederholt;
    volle Datenträger, Rechtefehler ohne Windows-Lock usw. bleiben fail-fast.
    """
    attempts = 6 if os.name == "nt" else 1
    retry_winerrors = {5, 32, 33}  # ACCESS_DENIED, SHARING/LOCK_VIOLATION
    for attempt in range(attempts):
        try:
            os.replace(source, target)
            return
        except OSError as exc:
            winerror = getattr(exc, "winerror", None)
            should_retry = (
                os.name == "nt"
                and winerror in retry_winerrors
                and attempt < attempts - 1
            )
            if not should_retry:
                raise
            time.sleep(0.025 * (2**attempt))


def _fsync_verzeichnis(ordner: Path) -> None:
    """Haelt den Verzeichniseintrag fest.

    Nicht jedes Dateisystem erlaubt das - Windows kennt es gar nicht, in
    Containern schlaegt es manchmal fehl. Kein Grund abzubrechen: Der Inhalt
    ist zu diesem Zeitpunkt bereits sicher geschrieben.
    """
    if os.name == "nt":
        return
    try:
        fd = os.open(str(ordner), os.O_RDONLY)
    except OSError as fehler:
        _log.debug(
            "Verzeichnis %s nicht zum Synchronisieren zu oeffnen: %s", ordner, fehler
        )
        return
    try:
        os.fsync(fd)
    except OSError as fehler:
        _log.debug("fsync auf %s nicht moeglich: %s", ordner, fehler)
    finally:
        os.close(fd)


def atomar_schreiben(
    pfad: str | os.PathLike,
    inhalt: str,
    *,
    nur_besitzer: bool = True,
) -> None:
    """Schreibt ``inhalt`` nach ``pfad``, ohne dass eine halbe Datei entstehen kann.

    ``nur_besitzer`` setzt 0600, und zwar auf der Zwischendatei - vor dem
    Umbenennen. Danach waere die Datei fuer einen Augenblick mit dem
    Standard-umask sichtbar, und genau in dem Augenblick steht sie offen.
    """
    ziel = Path(pfad)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    zwischen = _temp_path(ziel)
    # finally statt except: Eine liegengebliebene .tmp-Datei mit halbem
    # Inhalt sieht beim naechsten Blick aus wie ein Datenrest - und zwar
    # auch dann, wenn der Abbruch ein Strg-C war und keine Ausnahme, die
    # sich fangen liesse.
    geschafft = False
    try:
        with zwischen.open("w", encoding="utf-8", newline="\n") as datei:
            datei.write(inhalt)
            datei.flush()
            os.fsync(datei.fileno())
        if nur_besitzer:
            _sichern(zwischen)
        _replace_atomically(zwischen, ziel)
        geschafft = True
    finally:
        if not geschafft:
            try:
                zwischen.unlink(missing_ok=True)
            except OSError as fehler:
                _log.debug("%s blieb liegen: %s", zwischen.name, fehler)
    _fsync_verzeichnis(ziel.parent)


def _sichern(pfad: Path) -> None:
    """0600, wenn das Dateisystem es kennt. Scheitern ist nie fatal."""
    try:
        os.chmod(pfad, 0o600)
    except (OSError, NotImplementedError) as fehler:
        # FAT/exFAT kennen keine POSIX-Modi. Ein Stick soll deswegen nicht
        # unbrauchbar sein - aber schweigen darf es nicht, die Datei bleibt
        # dann offen.
        _log.warning("Zugriffsrechte auf %s nicht gesetzt: %s", pfad.name, fehler)


@contextmanager
def atomar_offen(
    pfad: str | os.PathLike,
    *,
    nur_besitzer: bool = True,
) -> Iterator[TextIO]:
    """Wie ``atomar_schreiben``, aber fuer Inhalte, die stueckweise entstehen.

    Gedacht fuer Ausgaben, die zeilenweise aufgebaut werden - Brueckendateien
    etwa, in denen jede Zeile ein Datensatz ist. Wer sie direkt in die
    Zieldatei schreibt, hinterlaesst bei einem Abbruch eine Datei mit
    abgeschnittener letzter Zeile, die von einer vollstaendigen nicht zu
    unterscheiden ist - bis der Empfaenger ueber sie stolpert.

        with atomar_offen(pfad) as datei:
            for satz in saetze:
                datei.write(json.dumps(satz) + "\n")

    Sichtbar wird die Datei erst, wenn der Block ohne Fehler endet.
    """
    ziel = Path(pfad)
    ziel.parent.mkdir(parents=True, exist_ok=True)
    zwischen = _temp_path(ziel)
    geschafft = False
    try:
        with zwischen.open("w", encoding="utf-8", newline="\n") as datei:
            yield datei
            datei.flush()
            os.fsync(datei.fileno())
        if nur_besitzer:
            _sichern(zwischen)
        _replace_atomically(zwischen, ziel)
        geschafft = True
    finally:
        if not geschafft:
            try:
                zwischen.unlink(missing_ok=True)
            except OSError as fehler:
                _log.debug("%s blieb liegen: %s", zwischen.name, fehler)
    _fsync_verzeichnis(ziel.parent)
