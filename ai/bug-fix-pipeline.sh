#!/usr/bin/env bash
# Bug-Fix Pipeline: Codex analysiert + fixt → Claude reviewed den Fix.
#
# Verwendung: ./ai/bug-fix-pipeline.sh "Beschreibung des Bugs"
#
# Ablauf:
#   1. Codex: Bug analysieren + minimalen Fix implementieren
#   2. git diff erfassen (was Codex geändert hat)
#   3. Claude: Code-Review via code-reviewer Agent (Qualitätscheck)
#
# Ausgabe: Diff + Review-Bericht

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"Bug-Beschreibung\""
  exit 1
fi

BUG_TASK="$*"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REVIEW_OUT="$REPO_DIR/.claude/last_review.md"
DIFF_OUT="$REPO_DIR/.claude/last_codex_diff.diff"

mkdir -p "$REPO_DIR/.claude"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔧 BUG-FIX PIPELINE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Task: $BUG_TASK"
echo ""

# ── SCHRITT 1: Codex analysiert & fixt ───────────────────────────
echo "📋 Schritt 1: Codex analysiert und fixt Bug..."
echo ""

# Vorher: Git-Status sichern
cd "$REPO_DIR"
BEFORE_HASH=$(git rev-parse HEAD 2>/dev/null || echo "no-git")

codex exec "
Du arbeitest im BudgetManager Repo (Python/PySide6).

AUFGABE: Analysiere und fixe diesen Bug:
${BUG_TASK}

Regeln:
- Minimaler Fix (nur das Nötige ändern)
- Keine ungefragten Refactors
- Nach dem Fix: python -m compileall . (nur wenn sinnvoll)
- Gib kurze Summary: Was war das Problem? Wie gefixt?
" 2>&1 | tee /tmp/codex_bug_fix_output.txt

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📊 Schritt 2: Diff erfassen..."

# Git-Diff des Codex-Fixes
if git diff HEAD --stat 2>/dev/null | grep -q "file"; then
  git diff HEAD > "$DIFF_OUT"
  echo "Diff gespeichert: $DIFF_OUT"
  echo ""
  git diff HEAD --stat
elif git diff --cached --stat 2>/dev/null | grep -q "file"; then
  git diff --cached > "$DIFF_OUT"
  echo "Diff (staged) gespeichert: $DIFF_OUT"
else
  echo "Keine Git-Änderungen erkannt."
  git diff > "$DIFF_OUT" 2>/dev/null || true
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 Schritt 3: Claude Review (Qualitätscheck)..."
echo ""

# Review-Prompt für Claude (wird von Claude selbst nach Pipeline-Ende verarbeitet)
cat > "$REVIEW_OUT" << REVIEW_EOF
# Code-Review: Bug-Fix durch Codex

## Bug-Beschreibung
${BUG_TASK}

## Review-Kriterien (BudgetManager Standards)
Prüfe den Fix gegen folgende Punkte:
- [ ] Minimale Änderung (kein Over-Engineering)
- [ ] i18n korrekt (tr()/trf() statt hardcodierte Strings)
- [ ] DB-Zugriff via db_transaction() bei Schreiboperationen
- [ ] Kein SQL-Injection-Risiko (Whitelist-Prüfung bei dynamischem SQL)
- [ ] Fehlerbehandlung angemessen (kein swallow-all except)
- [ ] Tests berücksichtigt (pytest-kompatibel)
- [ ] Keine duplicate Methoden oder toter Code eingeführt

## Diff (von Codex erstellt)
$(cat "$DIFF_OUT" 2>/dev/null | head -200 || echo "(kein diff)")

## Codex Output
$(cat /tmp/codex_bug_fix_output.txt 2>/dev/null | tail -50 || echo "(kein output)")
REVIEW_EOF

echo "Review-Prompt gespeichert: $REVIEW_OUT"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ Pipeline abgeschlossen."
echo ""
echo "→ Claude führt jetzt den Review durch."
echo "   Review-Datei: $REVIEW_OUT"
echo ""
echo "ANWEISUNG AN CLAUDE:"
echo "Bitte lies $REVIEW_OUT und führe den Review durch."
echo "Beantworte: Besteht der Fix die Qualitätsprüfung? Was muss ggf. nachgebessert werden?"
