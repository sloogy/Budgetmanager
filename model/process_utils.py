"""Plattform-sichere Prozess-/PID-Helfer.

Wichtig: ``os.kill(pid, 0)`` ist nur unter POSIX ein harmloser
Existenz-Check. Unter Windows kann ``os.kill`` Prozesse beenden. Deshalb
muss Windows einen eigenen Query-Pfad verwenden.
"""

from __future__ import annotations

import os
from typing import Any, cast


def is_pid_alive(pid: int | str | None) -> bool:
    """Gibt True zurück, wenn die PID wahrscheinlich zu einem laufenden Prozess gehört.

    Unter POSIX wird das übliche, nicht-destruktive ``os.kill(pid, 0)`` genutzt.
    Unter Windows wird bewusst kein ``os.kill`` verwendet, sondern ein Handle mit
    Query-/Synchronize-Rechten geöffnet und sofort abgefragt.

    Fehlerstrategie:
        - POSIX: ``PermissionError`` bedeutet: Prozess existiert, aber ist nicht
          für uns zugreifbar -> True.
        - Windows: Unklare OpenProcess-/Wait-Fehler werden vorsichtig als True
          behandelt, damit ein Live-Lock nicht versehentlich entfernt wird.
    """
    try:
        pid_i = int(pid or 0)
    except Exception:
        return False
    if pid_i <= 0:
        return False
    if os.name == "nt":
        return _pid_alive_windows(pid_i)
    return _pid_alive_posix(pid_i)


def _pid_alive_posix(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except Exception:
        return False


def _pid_alive_windows(
    pid: int,
) -> bool:  # pragma: no cover - echte Abdeckung via Windows-Smoke
    """Nicht-destruktiver Windows-PID-Check via Kernel32.

    ``OpenProcess`` mit ``PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE`` ist
    ausreichend, um den Prozessstatus via ``WaitForSingleObject(..., 0)`` zu
    prüfen. Es wird **kein** Signal gesendet.
    """
    try:
        import ctypes
        from ctypes import wintypes

        windll = cast(Any, getattr(ctypes, "WinDLL"))
        kernel32 = windll("kernel32", use_last_error=True)
        process_query_limited_information = 0x1000
        synchronize = 0x00100000
        wait_timeout = 0x00000102
        wait_object_0 = 0x00000000
        error_invalid_parameter = 87
        error_access_denied = 5

        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(
            process_query_limited_information | synchronize, False, int(pid)
        )
        if not handle:
            get_last_error = cast(Any, getattr(ctypes, "get_last_error", lambda: 0))
            err = int(get_last_error())
            if err == error_invalid_parameter:
                return False
            if err == error_access_denied:
                return True
            # Fail-safe für den Single-Instance-Guard: lieber blockieren als
            # ein mögliches Live-Lock entfernen und zwei DB-Instanzen zulassen.
            return True
        try:
            result = kernel32.WaitForSingleObject(handle, 0)
            if result == wait_timeout:
                return True
            return result != wait_object_0
        finally:
            kernel32.CloseHandle(handle)
    except Exception:
        # Auf Windows konservativ: unbekannt wird als lebend behandelt.
        return True
