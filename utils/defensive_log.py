"""Melder fuer Stellen, die scheitern duerfen - aber nicht schweigen.

Es gibt Stellen, an denen ein Fehler den Ablauf nicht aufhalten darf: ein
Uebersetzungslauf ueber hunderte Qt-Objekte, eine Menue-Verdrahtung, das
Aufraeumen alter Dateien. Bricht dort einer ab, verliert der Nutzer mehr, als
der Fehler wert ist.

Bis Loop 21 stand an solchen Stellen ``except Exception: pass``. Das loest das
eine Problem und schafft ein groesseres: Der Fehler passiert, und niemand
erfaehrt davon. Eine unuebersetzt gebliebene Beschriftung sah aus wie eine
fehlende Uebersetzung, eine Datei blieb weltlesbar, ohne dass es jemand
bemerkte.

``uebersprungen`` ist die Antwort darauf: weitermachen wie bisher, aber eine
Spur hinterlassen. Gedrosselt, weil diese Stellen in Schleifen ueber viele
Objekte liegen - eine Meldung je Objekt wuerde das Log fluten und die eine
interessante Zeile darin begraben. Gemeldet wird je Ort und Fehlerart einmal
pro Programmlauf.

Wortgleich in FPM, BudgetManager, FreizeitManager und LifePlanner.
"""
from __future__ import annotations

import logging
import threading

_log = logging.getLogger(__name__)
_gesehen: set[str] = set()
_sperre = threading.Lock()


def uebersprungen(was: str, fehler: BaseException, *, stufe: int = logging.DEBUG) -> None:
    """Meldet einen bewusst verschluckten Fehler - je Ursache einmal.

    ``was`` benennt die Stelle, nicht den Fehler: "Uebersetzungslauf",
    "Cockpit-Kontextmenue". Zusammen mit der Fehlerart ergibt das den
    Schluessel, unter dem gedrosselt wird.
    """
    schluessel = f"{was}:{type(fehler).__name__}"
    with _sperre:
        if schluessel in _gesehen:
            return
        _gesehen.add(schluessel)
    _log.log(stufe, "%s uebersprungen: %s", was, fehler)


def zuruecksetzen() -> None:
    """Vergisst, was schon gemeldet wurde. Nur fuer Tests."""
    with _sperre:
        _gesehen.clear()
