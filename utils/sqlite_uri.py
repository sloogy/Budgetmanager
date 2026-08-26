"""SQLite-URIs, die auch mit Sonderzeichen und Laufwerksbuchstaben halten.

Eine SQLite-Datei liesse sich schlicht ueber ihren Pfad oeffnen. Sobald aber
Optionen wie ``mode=ro`` dazukommen, muss der Pfad in eine URI - und dort
bedeuten drei Zeichen etwas anderes als im Dateinamen:

* ``#`` beginnt ein Fragment, alles danach faellt weg,
* ``?`` beginnt die Abfrage, ``sicherung?2024.db`` wuerde zu ``sicherung``
  plus einem Parameter ``2024.db``,
* ``%`` leitet eine Escape-Sequenz ein, ``100%e.db`` wird zu einem
  ungueltigen ``%e``.

Ein Backup-Pfad kommt aus einem Dateidialog, der Nutzer darf ihn nennen, wie
er will. Der frueher gebaute ``f"file:{pfad.as_posix()}?mode=ro"`` ging
deshalb an genau diesen Namen kaputt.

Warum ``Path.as_uri()`` und nicht ``urllib.request.pathname2url``: Beide
prozentkodieren richtig, aber ``as_uri`` ist Teil des Pfadobjekts und kennt
den Laufwerksbuchstaben von Haus aus - ``C:\\Ordner\\a.db`` wird zu
``file:///C:/Ordner/a.db``, die Form, die SQLite unter Windows erwartet.
``pathname2url`` liefert nur das Pfadstueck und ueberlaesst den Zusammenbau
dem Aufrufer, also genau der Stelle, an der sich der Fehler einschleicht.

Die Abfrage wird bewusst erst hinter der fertigen URI angehaengt: Nur so ist
sicher, dass das ``?`` aus der Option stammt und nicht aus dem Dateinamen.
"""

from __future__ import annotations

from pathlib import Path

__all__ = ["read_only_uri"]


def read_only_uri(path: str | Path) -> str:
    """URI, die ``path`` schreibgeschuetzt oeffnet (``sqlite3.connect(..., uri=True)``).

    Relative Pfade werden vorher absolut gemacht - ``as_uri()`` weist sie
    sonst zurueck, und der Aufrufer haette nur die Ausnahme, nicht die Datei.
    """
    p = Path(path)
    if not p.is_absolute():
        p = p.absolute()
    return p.as_uri() + "?mode=ro"
