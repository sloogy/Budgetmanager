#!/usr/bin/env bash
set -euo pipefail

# BudgetManager – Linux Starter (Fedora/Ubuntu)
# Verwendung:
#   chmod +x run.sh
#   ./run.sh
#
# Startet bevorzugt die fertige Linux-Binary ./BudgetManager.
# Wenn keine Binary vorhanden ist, startet er den Quellcode über eine lokale .venv.

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

export QT_ENABLE_HIGHDPI_SCALING="${QT_ENABLE_HIGHDPI_SCALING:-1}"
export QT_AUTO_SCREEN_SCALE_FACTOR="${QT_AUTO_SCREEN_SCALE_FACTOR:-1}"
export QT_SCALE_FACTOR_ROUNDING_POLICY="${QT_SCALE_FACTOR_ROUNDING_POLICY:-PassThrough}"

if [[ -f "$DIR/BudgetManager" ]]; then
    chmod +x "$DIR/BudgetManager" 2>/dev/null || true
    exec "$DIR/BudgetManager" "$@"
fi

if ! command -v python3 >/dev/null 2>&1; then
    echo "Fehler: python3 wurde nicht gefunden." >&2
    echo "Fedora: sudo dnf install python3 python3-pip" >&2
    echo "Ubuntu: sudo apt install python3 python3-pip python3-venv" >&2
    exit 1
fi

PY_VERSION="$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
PY_OK="$(python3 -c 'import sys; print(int(sys.version_info >= (3, 11)))')"
if [[ "$PY_OK" != "1" ]]; then
    echo "Fehler: Python >= 3.11 erforderlich (gefunden: $PY_VERSION)" >&2
    exit 1
fi

if [[ ! -d "$DIR/.venv" ]]; then
    echo "Erstelle lokale Python-Umgebung: .venv"
    python3 -m venv "$DIR/.venv"
fi

# shellcheck source=/dev/null
source "$DIR/.venv/bin/activate"

REQ_FILE="$DIR/requirements.txt"
STAMP_FILE="$DIR/.venv/.budgetmanager_requirements_ok"
if [[ -f "$REQ_FILE" ]]; then
    if [[ ! -f "$STAMP_FILE" || "$REQ_FILE" -nt "$STAMP_FILE" ]]; then
        echo "Installiere/aktualisiere Python-Abhängigkeiten..."
        python -m pip install --upgrade pip
        python -m pip install -r "$REQ_FILE"
        date > "$STAMP_FILE"
    fi
fi

exec python "$DIR/main.py" "$@"
