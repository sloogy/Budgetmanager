"""Farbabstufung ohne Qt-Abhängigkeit.

Bewusst eigenes Modul: ``views/ui_colors.py`` importiert ``QWidget`` und ist
damit im Prüfcontainer und in Qt-freien Tests nicht ladbar. Die reine
Farbarithmetik gehört deshalb hierher — gleiche Begründung wie bei
``model/fixed_cost_due.py``.
"""

from __future__ import annotations

import re

_HEX = re.compile(r"#([0-9a-fA-F]{6})")


def shade(color: str, factor: float) -> str:
    """Dunkelt (``factor`` < 1) oder hellt (> 1) eine ``#rrggbb``-Farbe ab.

    Unbekannte Eingaben werden unverändert zurückgegeben: ein Stylesheet darf
    an einer unerwarteten Farbangabe nicht scheitern.
    """
    match = _HEX.fullmatch((color or "").strip())
    if not match:
        return color
    raw = match.group(1)
    channels = (int(raw[index : index + 2], 16) for index in (0, 2, 4))
    scaled = tuple(max(0, min(255, round(value * factor))) for value in channels)
    return "#{:02x}{:02x}{:02x}".format(*scaled)
