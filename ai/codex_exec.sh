#!/usr/bin/env bash
set -euo pipefail
if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"Task description...\""
  exit 1
fi
# Non-interactive: codex exec
codex exec "$*"
