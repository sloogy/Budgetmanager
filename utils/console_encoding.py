"""UTF-8 fuer stdout/stderr - ohne jede weitere Abhaengigkeit.

Die Windows-Konsole faehrt standardmaessig cp850/cp1252 und kann Umlaute und
Emojis (⬇️, ❌, ✓, ⟲) nicht kodieren. Jede Ausgabe damit stirbt dort an einem
UnicodeEncodeError; im logging-Modul wird der abgefangen und durch
"--- Logging error ---" ersetzt - also genau die Diagnosezeilen, die man bei
einem Windows-Problem braucht.

Dieses Modul hat bewusst keine Importe ausser sys. Es wird beim Start als
erstes gebraucht, unter anderem von model/logging_config.py: Waere die
Umstellung nur ueber updater/common.py erreichbar, zoege jede
Logging-Einrichtung requests und packaging mit in den Startpfad.
"""

from __future__ import annotations

import sys


def enable_utf8_console() -> None:
    """Stellt stdout und stderr auf UTF-8 um, mit errors='replace' als Netz.

    Robust gegen fehlende Streams - in einem windowed PyInstaller-Build ohne
    Konsole sind stdout und stderr None - und gegen Streams ohne
    ``reconfigure`` (etwa die Testumgebung, die sie durch eigene Objekte
    ersetzt).
    """
    for stream in (sys.stdout, sys.stderr):
        if stream is None:
            continue
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is None:
            continue
        try:
            reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
