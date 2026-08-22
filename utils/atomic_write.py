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
from pathlib import Path

_log = logging.getLogger(__name__)


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
        _log.debug("Verzeichnis %s nicht zum Synchronisieren zu oeffnen: %s",
                   ordner, fehler)
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
    zwischen = ziel.with_name(f"{ziel.name}.tmp-{os.getpid()}")
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
        os.replace(zwischen, ziel)
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
