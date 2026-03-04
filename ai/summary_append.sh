#!/usr/bin/env bash
set -euo pipefail

# Append a markdown section to the repo-root SUMMARY.md (token-sparender Single-Source)
SUMMARY_FILE="${SUMMARY_FILE:-$CLAUDE_PROJECT_DIR/SUMMARY.md}"
if [[ -z "${CLAUDE_PROJECT_DIR:-}" ]]; then
  # fallback: assume script runs from repo root
  SUMMARY_FILE="${SUMMARY_FILE:-SUMMARY.md}"
fi

title="${1:-}"
shift || true

{
  echo ""
  echo "## ${title}"
  echo "- time: $(date '+%Y-%m-%d %H:%M:%S')"
  for item in "$@"; do
    echo "- ${item}"
  done
  echo ""
} >> "$SUMMARY_FILE"
