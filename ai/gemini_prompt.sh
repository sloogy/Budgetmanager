#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"Prompt...\""
  exit 1
fi
gemini -p "$*"
