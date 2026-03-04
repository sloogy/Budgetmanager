#!/usr/bin/env bash
set -euo pipefail

# BudgetManager – Linux Quellcode-Starter
# Erfordert Python >= 3.11

PY_MAJOR=$(python3 -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$(python3 -c 'import sys; print(sys.version_info.minor)')
PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')

if [ "$PY_MAJOR" -lt 3 ] || { [ "$PY_MAJOR" -eq 3 ] && [ "$PY_MINOR" -lt 11 ]; }; then
    echo "Fehler: Python >= 3.11 erforderlich (gefunden: $PY_VERSION)" >&2
    exit 1
fi

# Aktiviere .venv falls vorhanden
if [ -f ".venv/bin/activate" ]; then
    # shellcheck source=/dev/null
    source ".venv/bin/activate"
else
    echo "Tipp: python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
fi

exec python3 main.py "$@"
