#!/usr/bin/env bash
set -euo pipefail
TASK="${1:-}"
if [[ -z "$TASK" ]]; then
  echo "Usage: $0 '<task>'" >&2
  exit 2
fi

./ai/ensure_git.sh

STAMP="$(date +%Y%m%d_%H%M%S)"
OUTDIR=".ai/dispatch/${STAMP}"
mkdir -p "$OUTDIR"
ln -sfn "$OUTDIR" .ai/dispatch/latest

# routing heuristic
route="codex"
if echo "$TASK" | grep -Eqi '(changelog|release|readme|doku|übersetz|i18n|sprache|locale)'; then
  route="gemini"
fi

# Run worker (store full output in OUTDIR, but keep SUMMARY.md short)
worker_rc=0
if [[ "$route" == "gemini" ]]; then
  set +e
  gemini -p "$TASK" > "$OUTDIR/GEMINI.md" 2>&1
  worker_rc=$?
  set -e
else
  set +e
  codex exec "$TASK" > "$OUTDIR/CODEX.md" 2>&1
  worker_rc=$?
  set -e
fi

set +e
python -m compileall . > "$OUTDIR/SMOKE.txt" 2>&1
smoke_rc=$?
python ai/i18n_check.py > "$OUTDIR/I18N.txt" 2>&1
i18n_rc=$?
set -e

if [[ -d .git ]]; then
  git diff --stat > "$OUTDIR/DIFFSTAT.txt" 2>&1 || true
fi

# ---- SINGLE OUTPUT: append everything to repo-root SUMMARY.md ----
./ai/summary_append.sh "Run ${STAMP} (small)"   "task: ${TASK}"   "route: ${route}"   "worker_rc: ${worker_rc}"   "smoke_rc: ${smoke_rc}"   "i18n_rc: ${i18n_rc}"   "artifacts: ${OUTDIR}/"

SUMMARY_FILE="${CLAUDE_PROJECT_DIR:-.}/SUMMARY.md"
{
  echo "### Worker output (tail)"
  if [[ "$route" == "gemini" ]]; then
    tail -n 60 "$OUTDIR/GEMINI.md" || true
  else
    tail -n 60 "$OUTDIR/CODEX.md" || true
  fi
  echo ""
  echo "### DIFFSTAT"
  if [[ -f "$OUTDIR/DIFFSTAT.txt" ]]; then
    cat "$OUTDIR/DIFFSTAT.txt"
  else
    echo "(kein git diff oder kein Git-Repo)"
  fi
  echo ""
  echo "### Smoke (tail)"
  tail -n 40 "$OUTDIR/SMOKE.txt" || true
  echo ""
  echo "### i18n Check (tail)"
  tail -n 40 "$OUTDIR/I18N.txt" || true
  echo ""
  echo "> Vollausgaben liegen unter: ${OUTDIR}/"
} >> "$SUMMARY_FILE"
