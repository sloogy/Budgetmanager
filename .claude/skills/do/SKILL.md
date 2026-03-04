---
name: do
description: Dispatch für kleine Tasks. Startet Gemini/Codex je nach Task und liefert QA-Output aus .ai/dispatch/latest.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read
---
1) Führe aus: `bash ai/run_small.sh "$ARGUMENTS"`
2) Lies danach nur `SUMMARY.md` (Repo-Root).
3) Gib eine kurze QA-Zusammenfassung (OK/NOK, Risiken, How-to-test).
