#!/usr/bin/env bash
set -euo pipefail
echo "## Claude Subagents (.claude/agents)"
if [[ -d .claude/agents ]]; then
  ls -1 .claude/agents | sed 's/^/- /'
else
  echo "- (none)"
fi

echo "\n## Claude Skills (.claude/skills)"
if [[ -d .claude/skills ]]; then
  find .claude/skills -maxdepth 2 -name SKILL.md -print | sed 's#^#- #' 
else
  echo "- (none)"
fi

echo "\n## Codex config (.codex/config.toml)"
if [[ -f .codex/config.toml ]]; then
  echo "- sandbox_mode / approval_policy / multi_agent configured"
  grep -E '^(sandbox_mode|approval_policy|agents\.max_threads|agents\.max_depth|\[features\])' .codex/config.toml || true
else
  echo "- (none)"
fi

echo "\n## Gemini commands (.gemini/commands)"
if [[ -d .gemini/commands ]]; then
  find .gemini/commands -name '*.toml' -maxdepth 3 -print | sed 's#^#- #' 
else
  echo "- (none)"
fi
