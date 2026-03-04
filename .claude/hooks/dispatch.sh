#!/usr/bin/env bash
set -euo pipefail

# Reads event JSON from stdin. If user prompt starts with @do or @big, run corresponding scripts.
# Writes results to .ai/dispatch/<timestamp>/ and updates .ai/dispatch/latest symlink.

json="$(cat)"

prompt=$(python - <<'PY'
import json,sys
j=json.load(sys.stdin)
# try common paths
cands=[]
for k in ("prompt","userPrompt","input","text"):
    if k in j and isinstance(j[k],str):
        cands.append(j[k])
# sometimes nested
for k in ("event","data","payload"):
    v=j.get(k)
    if isinstance(v,dict):
        for kk in ("prompt","userPrompt","text"):
            if kk in v and isinstance(v[kk],str):
                cands.append(v[kk])
print(cands[0] if cands else "")
PY <<<"$json")

# Only trigger on explicit prefix (safe)
if [[ "$prompt" == @do* ]]; then
  task="${prompt#@do }"
  exec "$CLAUDE_PROJECT_DIR/ai/run_small.sh" "$task" >/dev/null 2>&1 &
  exit 0
fi
if [[ "$prompt" == @big* ]]; then
  task="${prompt#@big }"
  exec "$CLAUDE_PROJECT_DIR/ai/run_big.sh" "$task" >/dev/null 2>&1 &
  exit 0
fi

exit 0
