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
# Symlink-Fallback für FAT/exFAT-Filesysteme (keine Symlink-Unterstützung)
if ln -sfn "$(pwd)/$OUTDIR" .ai/dispatch/latest 2>/dev/null; then
  : # symlink ok
else
  mkdir -p .ai/dispatch/latest
  # Inhalt wird am Ende kopiert (nach allen Writes)
  _LATEST_COPY=1
fi

# Run Gemini + Codex concurrently (full output to files)
set +e
gemini -p "Write a concise plan and i18n checklist for: $TASK. Keep it short." > "$OUTDIR/GEMINI_PLAN.md" 2>&1 &
GPID=$!
codex exec "Implement: $TASK. Use multi-agent roles: explorer then worker then reviewer. Keep changes minimal. Run python -m compileall . and keep output concise." > "$OUTDIR/CODEX_IMPL.md" 2>&1 &
CPID=$!

wait $GPID; gemini_rc=$?
wait $CPID; codex_rc=$?
set -e

set +e
python -m compileall . > "$OUTDIR/SMOKE.txt" 2>&1
smoke_rc=$?
python ai/i18n_check.py > "$OUTDIR/I18N.txt" 2>&1
i18n_rc=$?
set -e

if [[ -d .git ]]; then
  git diff --stat > "$OUTDIR/DIFFSTAT.txt" 2>&1 || true
fi

./ai/summary_append.sh "Run ${STAMP} (big)"   "task: ${TASK}"   "workers: gemini + codex(multi-agent)"   "gemini_rc: ${gemini_rc}"   "codex_rc: ${codex_rc}"   "smoke_rc: ${smoke_rc}"   "i18n_rc: ${i18n_rc}"   "artifacts: ${OUTDIR}/"

SUMMARY_FILE="${CLAUDE_PROJECT_DIR:-.}/SUMMARY.md"
{
  echo "### Gemini plan (tail)"
  tail -n 80 "$OUTDIR/GEMINI_PLAN.md" || true
  echo ""
  echo "### Codex implementation (tail)"
  tail -n 80 "$OUTDIR/CODEX_IMPL.md" || true
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

# Auf FAT-Systemen: Dateien in latest/ kopieren
if [[ "${_LATEST_COPY:-0}" == "1" ]]; then
  cp -f "$OUTDIR"/* .ai/dispatch/latest/ 2>/dev/null || true
fi
