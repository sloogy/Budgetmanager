"""Welche Bruecken-Ordner es auf diesem Rechner gibt.

Welcher Ordner der aktive ist, haengt davon ab, wie das Programm gestartet
wurde: Im LifePlanner gibt der Host ihn vor - einen eigenen je Profil -,
eigenstaendig liegt er im Benutzerverzeichnis. Wer beides gemischt nutzt, hat
mehrere Bruecken und sieht in jeder nur die Haelfte. Loop 20 machte das
sichtbar, hier wird es behoben.

Geschrieben wird weiterhin ausschliesslich in den aktiven Ordner - zwei
Schreiber auf derselben Datei waeren ein Rueckschritt hinter Loop 27.
Gelesen wird aus allen bekannten, der aktive zuletzt: Bei gleicher Kennung
gewinnt damit, was hier und jetzt gilt. Doppeltes Lesen schadet nicht, weil
beide Seiten ihren Importzustand ueber die Kennung des Datensatzes fuehren
und nicht ueber die Datei.

Das Register enthaelt nur Pfade, verraet damit aber Profilnamen und die
Ordnerstruktur des Nutzers. Darum 0700 auf den Ordner und 0600 auf die Datei,
wie ueberall sonst in der Suite.

Wortgleich in FPM, BudgetManager und LifePlanner. Der FreizeitManager
braucht es nicht: Er kennt keinen eigenstaendigen Brueckenbetrieb - ohne Host
gibt es dort keinen Ordner, den man verfehlen koennte.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from model.file_permissions import secure_dir
from utils.atomic_write import atomar_schreiben
from utils.defensive_log import uebersprungen

#: Wieviele Ordner das Register hoechstens behaelt. Mehr als eine Handvoll
#: Profile plus den eigenstaendigen Ordner gibt es in der Praxis nicht; die
#: Grenze verhindert, dass eine kaputt geschriebene Datei unbegrenzt waechst.
MAX_ORDNER = 32

_ENV_REGISTER = "FPM_SUITE_BRIDGE_REGISTRY"
_ORDNERNAME = "fpm-suite"
_DATEINAME = "bridges.json"
_SCHEMA = "fpm.suite.bridges.v1"


def register_pfad() -> Path:
    """Wo das Register liegt.

    Die Umgebungsvariable ist der Weg, auf dem Tests und ein Betrieb mit
    getrennten Benutzerdaten das Register verlegen koennen, ohne dass sie
    einander in die Quere kommen.
    """
    override = os.environ.get(_ENV_REGISTER, "").strip()
    if override:
        return Path(override).expanduser()
    basis = os.environ.get("XDG_CONFIG_HOME", "").strip()
    wurzel = Path(basis).expanduser() if basis else Path.home() / ".config"
    return wurzel / _ORDNERNAME / _DATEINAME


def _lesen() -> list[str]:
    """Die eingetragenen Pfade, so wie sie dastehen.

    Ein kaputtes Register ist kein Grund, die Bruecke anzuhalten: Es ist ein
    Verzeichnis von Ordnern, keine Datenquelle. Fehlt oder klemmt es, bleibt
    der aktive Ordner - also genau der Stand vor dieser Datei.
    """
    pfad = register_pfad()
    try:
        roh = pfad.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as fehler:
        uebersprungen("Bruecken-Register lesen", fehler)
        return []
    try:
        daten = json.loads(roh)
    except json.JSONDecodeError as fehler:
        uebersprungen("Bruecken-Register auswerten", fehler)
        return []
    if not isinstance(daten, dict):
        return []
    eintraege = daten.get("ordner")
    if not isinstance(eintraege, list):
        return []
    return [e for e in eintraege if isinstance(e, str) and e]


def eintragen(ordner: str | os.PathLike) -> None:
    """Haelt fest, dass dieser Ordner benutzt wird.

    Steht er schon drin, wird nichts geschrieben: Die Funktion haengt an der
    Ordner-Aufloesung und laeuft damit bei jedem Bruecken-Zugriff. Ein
    Schreibvorgang je Zugriff waere reine Last - und ein weiterer Kandidat
    fuer eine halb geschriebene Datei.
    """
    try:
        ziel = Path(ordner).expanduser().resolve()
    except OSError as fehler:
        uebersprungen("Brueckenordner aufloesen", fehler)
        return
    text = str(ziel)
    vorhanden = _lesen()
    if text in vorhanden:
        return
    behalten = [p for p in vorhanden if p != text and Path(p).is_dir()]
    neu = [text, *behalten][:MAX_ORDNER]
    pfad = register_pfad()
    try:
        pfad.parent.mkdir(parents=True, exist_ok=True)
        secure_dir(pfad.parent)
        atomar_schreiben(
            pfad,
            json.dumps({"schema": _SCHEMA, "ordner": neu}, indent=2) + "\n",
        )
    except OSError as fehler:
        uebersprungen("Bruecken-Register schreiben", fehler)


def bekannte_ordner(aktiv: str | os.PathLike) -> tuple[Path, ...]:
    """Alle Brueckenordner, aus denen gelesen werden soll - aktiver zuletzt.

    Zuletzt, weil der Aufrufer die Ordner in dieser Reihenfolge durchgeht und
    ein spaeterer Datensatz denselben mit gleicher Kennung ueberschreibt. Was
    im gerade benutzten Ordner steht, ist der juengere Stand.

    Ordner, die es nicht mehr gibt, fallen still heraus: Ein geloeschtes
    Profil soll keine Fehlermeldung erzeugen.
    """
    try:
        ziel = Path(aktiv).expanduser().resolve()
    except OSError as fehler:
        uebersprungen("Brueckenordner aufloesen", fehler)
        return (Path(aktiv),)
    andere: list[Path] = []
    gesehen = {ziel}
    for eintrag in _lesen():
        kandidat = Path(eintrag)
        if kandidat in gesehen:
            continue
        try:
            if not kandidat.is_dir():
                continue
        except OSError as fehler:
            uebersprungen("Brueckenordner pruefen", fehler)
            continue
        gesehen.add(kandidat)
        andere.append(kandidat)
    return (*andere, ziel)
