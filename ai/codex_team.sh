#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"Task (klar, klein, konkret)\""
  exit 1
fi

TASK="$*"

# Implementierung: --full-auto (workspace-write + on-request approvals)
# Multi-agent: via config oder zusätzlich per --enable.
codex --full-auto --enable multi_agent exec "
Du arbeitest im BudgetManager Repo.

Arbeitsmodus: Multi-agent Team.
- Spawn parallel: explorer (finde relevante Dateien/Codepfade), reviewer (Risiken+Tests).
- Danach worker: implementiere minimalen Fix/Feature genau für TASK.
- Nach dem Patch: führe 'python -m compileall .' aus und gib 'How to test' Schritte.

TASK:
${TASK}

Regeln:
- Nur minimale Änderungen.
- Keine unnötigen Refactors.
- Keine großen Textwände; kurze, klare Summary.
"
