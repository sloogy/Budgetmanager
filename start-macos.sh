#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 wurde nicht gefunden. Bitte Python 3.12 oder neuer installieren."
  exit 1
fi

if [ ! -d ".venv" ]; then
  echo "Erstelle virtuelle Umgebung..."
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install -U pip
python -m pip install -r requirements.txt
python main.py "$@"
