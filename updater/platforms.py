from __future__ import annotations

import platform


def platform_key() -> str:
    """Gibt den Asset-Key zurück, der im Manifest verwendet wird."""
    sysname = platform.system().lower()
    if "windows" in sysname:
        return "windows"
    if "linux" in sysname:
        return "linux"
    # macOS optional später
    if "darwin" in sysname or "mac" in sysname:
        return "macos"
    return sysname
