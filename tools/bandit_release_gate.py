#!/usr/bin/env python3
"""Fail-closed Bandit-Gate ohne historische Baseline.

Jeder MEDIUM- oder HIGH-Fund blockiert den Release. Bewusst dynamische SQL-
Stellen müssen lokal mit einer begründeten ``# nosec B608``-Markierung geprüft
sein; dadurch kann eine alte Baseline neue Schwachstellen nicht verdecken.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = ROOT / "audit_artifacts" / "BANDIT_CURRENT.json"
SCAN_TARGETS = ("model", "updater", "utils", "views", "tools", "main.py")


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _run_bandit(output: Path) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    command = [
        sys.executable,
        "-m",
        "bandit",
        "-q",
        "-r",
        *SCAN_TARGETS,
        "-f",
        "json",
        "-o",
        str(output),
    ]
    return int(subprocess.run(command, cwd=ROOT, check=False).returncode)


def evaluate(current: dict[str, Any]) -> dict[str, Any]:
    results = list(current.get("results", []))
    severity_counts = Counter(
        str(item.get("issue_severity", "UNKNOWN")) for item in results
    )
    blocking = [
        item
        for item in results
        if str(item.get("issue_severity", "")).upper() in {"MEDIUM", "HIGH"}
    ]
    return {
        "status": "PASS" if not blocking else "FAIL",
        "policy": "zero-medium-zero-high",
        "current_total": len(results),
        "severity_counts": dict(sorted(severity_counts.items())),
        "blocking_findings": blocking,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bandit-json", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--summary-json", type=Path)
    parser.add_argument("--skip-scan", action="store_true")
    # Kompatibilität zu alten CI-Aufrufen; die Baseline wird absichtlich ignoriert.
    parser.add_argument("--baseline", type=Path)
    args = parser.parse_args()

    output = args.bandit_json.resolve()
    if not args.skip_scan:
        rc = _run_bandit(output)
        if rc not in {0, 1} or not output.is_file():
            print(f"Bandit-Werkzeugfehler, Exit-Code {rc}", file=sys.stderr)
            return 2
    elif not output.is_file():
        print(f"Bandit-JSON fehlt: {output}", file=sys.stderr)
        return 2

    summary = evaluate(_load(output))
    if args.summary_json:
        path = args.summary_json.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print(
        "Bandit Release Gate: "
        f"{summary['status']} | total={summary['current_total']} "
        f"blocking={len(summary['blocking_findings'])}"
    )
    return 0 if summary["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
