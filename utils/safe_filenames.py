"""Dateinamen, die auch unter Windows welche sind.

Die beiden Slug-Funktionen im Projekt - ``model.user_model._make_slug`` fuer
``<konto>.enc`` und ``theme_manager._slugify`` fuer ``<profil>.json`` - filtern
korrekt auf ``[a-zA-Z0-9]`` beziehungsweise ``[a-z0-9_-]``. Die unter Windows
verbotenen Zeichen sind damit erschlagen, die reservierten Geraetenamen aber
nicht: Ein Konto oder Theme namens "Con", "Aux", "Nul" oder "Prn" ergibt
``con.enc`` beziehungsweise ``nul.json``. Windows behandelt diese Namen
unabhaengig von der Endung als Geraete - das Anlegen schlaegt fehl oder
schreibt ins Nichts, und der Nutzer sieht ein Konto, dessen Datenbank es nicht
gibt.

Auf Linux sind das ganz gewoehnliche Dateien. Ein Test, der die Datei wirklich
anlegt, waere auf dem Fedora-Entwicklungsrechner deshalb immer gruen; geprueft
wird hier die Namensbildung selbst.
"""

from __future__ import annotations

# MS-DOS-Erbe, bis heute in jeder Windows-Version aktiv. Die Liste ist
# abgeschlossen und aendert sich nicht mehr.
RESERVIERTE_GERAETENAMEN = frozenset(
    {"con", "prn", "aux", "nul"}
    | {f"com{ziffer}" for ziffer in range(1, 10)}
    | {f"lpt{ziffer}" for ziffer in range(1, 10)}
)


def entschaerfe_geraetenamen(slug: str) -> str:
    """Haengt ``_`` an, wenn ``slug`` ein reservierter Geraetename ist.

    Die Pruefung ist bewusst unabhaengig von Gross-/Kleinschreibung, weil
    Windows es auch ist, und arbeitet auf dem bereits bereinigten Slug - also
    auf dem Teil vor der Endung, denn genau den wertet Windows aus.
    """
    if slug.casefold() in RESERVIERTE_GERAETENAMEN:
        return slug + "_"
    return slug
