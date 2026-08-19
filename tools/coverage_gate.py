#!/usr/bin/env python3
"""Eindeutiges Coverage-Gate für Gesamtcode und Sicherheitsmodule.

Das Werkzeug liest bewusst *ein vollständiges* pytest-cov-JSON. Es erzeugt
daneben eine kleine, maschinenlesbare Zusammenfassung. Dadurch können eine
Teilabdeckung und der vollständige CI-Nachweis nicht mehr verwechselt werden.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

DEFAULT_MINIMUMS = {
    "model/restore_bundle.py": 70.0,
    "updater/manifest_signing.py": 85.0,
    "utils/secure_excel.py": 85.0,
}
DEFAULT_OVERALL_MINIMUM = 40.0


def _percent(summary: dict) -> float:
    return float(
        summary.get("percent_covered", summary.get("percent_covered_display", 0.0))
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--json", type=Path, default=Path("audit_artifacts/coverage_full.json")
    )
    parser.add_argument(
        "--summary-json",
        type=Path,
        default=Path("audit_artifacts/coverage_gate_summary.json"),
    )
    parser.add_argument("--overall-min", type=float, default=DEFAULT_OVERALL_MINIMUM)
    args = parser.parse_args()

    if not args.json.is_file():
        print("Coverage-Gate FEHLGESCHLAGEN")
        print(f"- Vollständiges Coverage-Artefakt fehlt: {args.json}")
        print(
            "- Zuerst die komplette Suite ausführen: pytest --cov --cov-branch "
            "--cov-report=json:audit_artifacts/coverage_full.json"
        )
        return 1

    data = json.loads(args.json.read_text(encoding="utf-8"))
    files = data.get("files", {})
    overall = _percent(data.get("totals", {}))
    errors: list[str] = []
    module_results: dict[str, dict[str, float | bool]] = {}

    if overall < args.overall_min:
        errors.append(f"Gesamt: {overall:.1f}% < {args.overall_min:.1f}%")

    for name, minimum in DEFAULT_MINIMUMS.items():
        summary = files.get(name, {}).get("summary", {})
        actual = _percent(summary)
        passed = actual >= minimum
        module_results[name] = {
            "actual": round(actual, 3),
            "minimum": minimum,
            "passed": passed,
        }
        if not passed:
            errors.append(f"{name}: {actual:.1f}% < {minimum:.1f}%")

    summary_payload = {
        "source": str(args.json),
        "overall": {
            "actual": round(overall, 3),
            "minimum": args.overall_min,
            "passed": overall >= args.overall_min,
        },
        "critical_modules": module_results,
        "passed": not errors,
        "errors": errors,
    }
    args.summary_json.parent.mkdir(parents=True, exist_ok=True)
    args.summary_json.write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )

    if errors:
        print("Coverage-Gate FEHLGESCHLAGEN")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Coverage-Gate BESTANDEN: Gesamt {overall:.1f}% und "
        f"{len(DEFAULT_MINIMUMS)} kritische Module"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
