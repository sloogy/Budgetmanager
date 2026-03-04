---
name: big
description: Große Tasks: Claude Agent Team (in-process) + Codex Multi-Agents + QA-Gate.
disable-model-invocation: true
user-invocable: true
allowed-tools: Bash, Read
---
1) **Erstelle ein Agent Team** (in-process) mit 3 Teammates:
   - i18n (prüft locale keys/strings)
   - qa (tests/compileall)
   - reviewer (Risiken/Architektur)
   Bitte **plan approval** für Teammates.

2) Starte dann: `bash ai/run_big.sh "$ARGUMENTS"`

3) Lies nur `.ai/dispatch/latest/SUMMARY.md` + QA-Files und gib dem Nutzer:
   - Was wurde geändert
   - Risiken
   - Wie testen
