#!/usr/bin/env bash
set -euo pipefail
if [[ ! -d .git ]]; then
  git init -q
  git config core.autocrlf false || true
fi
