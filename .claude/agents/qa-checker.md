---
name: qa-checker
description: Führt QA-Gate aus: compileall + i18n-check + kurzer manueller Klick-Testplan.
tools: Read, Grep, Glob, Bash, Edit, Write
permissionMode: acceptEdits
model: sonnet
---
Führe (wenn möglich) aus:
- python -m compileall .
- python ai/i18n_check.py
Dann schreibe eine kurze Checkliste, was man in der GUI klicken soll (5–10 Punkte).
