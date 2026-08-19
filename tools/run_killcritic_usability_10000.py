#!/usr/bin/env python3
"""Qt-freier Controller für den 10.000-Loop-KILLCRITIC-Usability-Audit.

Jeder Worker läuft in einem eigenen Prozess. Dadurch beeinflussen globale
Qt-Plattformdestruktoren weder spätere Loops noch den Gesamtnachweis.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import signal
import shutil
import subprocess
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKER = ROOT / "tools" / "killcritic_usability_audit_10000.py"


def app_version() -> str:
    text = (ROOT / "app_info.py").read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*["\']([^"\']+)', text, re.MULTILINE)
    return match.group(1) if match else "unknown"


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def write_json(path: Path | None, payload: dict[str, object]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def write_csv(path: Path | None, rows: list[dict[str, object]]) -> None:
    if path is None:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("loop", "domain", "checks", "result", "new_findings"),
        )
        writer.writeheader()
        writer.writerows(rows)


def execute_worker(
    *,
    offset: int,
    loops: int,
    seed: int,
    output_dir: Path,
    token: str,
    timeout_seconds: int,
) -> tuple[dict[str, object] | None, list[dict[str, object]], str]:
    part_json = output_dir / f"part-{token}.json"
    part_csv = output_dir / f"part-{token}.csv"
    stdout_path = output_dir / f"part-{token}.stdout.log"
    stderr_path = output_dir / f"part-{token}.stderr.log"
    command = [
        sys.executable,
        str(WORKER),
        "--worker",
        "--loops",
        str(loops),
        "--loop-offset",
        str(offset),
        "--seed",
        str(seed),
        "--json",
        str(part_json),
        "--csv",
        str(part_csv),
    ]
    env = os.environ.copy()
    env.setdefault("QT_QPA_PLATFORM", "offscreen")
    env.setdefault("QT_LOGGING_RULES", "qt.qpa.*=false")
    timed_out = False
    with stdout_path.open("w", encoding="utf-8") as stdout_handle, stderr_path.open(
        "w", encoding="utf-8"
    ) as stderr_handle:
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            env=env,
            text=True,
            stdout=stdout_handle,
            stderr=stderr_handle,
            start_new_session=True,
        )
        try:
            process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            timed_out = True
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                # Keine Pipe-Kommunikation: der Controller kann auch bei einem
                # defekten nativen Qt-Prozess fortfahren und den Bereich teilen.
                pass

    payload: dict[str, object] | None = None
    rows: list[dict[str, object]] = []
    try:
        if part_json.exists():
            candidate = json.loads(part_json.read_text(encoding="utf-8"))
            if (
                int(candidate.get("loops", -1)) == loops
                and int(candidate.get("loop_offset", -1)) == offset
            ):
                payload = candidate
        if part_csv.exists():
            with part_csv.open(newline="", encoding="utf-8") as handle:
                rows = [dict(row) for row in csv.DictReader(handle)]
            if len(rows) != loops:
                rows = []
    except (OSError, ValueError, json.JSONDecodeError):
        payload = None
        rows = []

    stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    stderr = stderr_path.read_text(encoding="utf-8", errors="replace")
    diagnostic = (
        f"exit={process.poll()} timeout={timed_out} "
        f"stdout={clean(stdout[-500:])!r} stderr={clean(stderr[-500:])!r}"
    )
    return payload, rows, diagnostic


def _save_state(path: Path, state: dict[str, object]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _resume_command(args: argparse.Namespace, state_dir: Path) -> list[str]:
    command = [
        sys.executable,
        str(Path(__file__).resolve()),
        "--loops",
        str(args.loops),
        "--seed",
        str(args.seed),
        "--batch-size",
        str(args.batch_size),
        "--worker-timeout",
        str(args.worker_timeout),
        "--state-dir",
        str(state_dir),
        "--resume",
    ]
    if args.json:
        command.extend(["--json", str(Path(args.json).resolve())])
    if args.csv:
        command.extend(["--csv", str(Path(args.csv).resolve())])
    return command


def run(args: argparse.Namespace) -> int:
    loops = max(1, int(args.loops))
    batch_size = max(10, int(args.batch_size))
    timeout_seconds = max(15, int(args.worker_timeout))
    state_dir = (
        Path(args.state_dir).resolve()
        if args.state_dir
        else Path(tempfile.mkdtemp(prefix="bm-killcritic-controller-"))
    )
    state_dir.mkdir(parents=True, exist_ok=True)
    parts_dir = state_dir / "parts"
    parts_dir.mkdir(exist_ok=True)
    state_path = state_dir / "state.json"

    if args.resume and state_path.exists():
        state = json.loads(state_path.read_text(encoding="utf-8"))
    else:
        pending: list[list[int]] = []
        offset = 0
        while offset < loops:
            chunk = min(batch_size, loops - offset)
            pending.append([offset, chunk, 0])
            offset += chunk
        state = {
            "started_epoch": time.time(),
            "pending": pending,
            "rows": [],
            "details": [],
            "checks": 0,
            "findings": 0,
            "worker_failures": 0,
            "worker_attempts": 0,
            "verified": 0,
            "next_progress": 1000,
        }

    attempts_this_generation = 0
    while state["pending"]:
        current_offset, chunk, retry = state["pending"].pop(0)
        state["worker_attempts"] += 1
        attempts_this_generation += 1
        token = (
            f"{current_offset:05d}-{chunk:04d}-{retry}-"
            f"{state['worker_attempts']:04d}"
        )
        payload, part_rows, diagnostic = execute_worker(
            offset=int(current_offset),
            loops=int(chunk),
            seed=int(args.seed),
            output_dir=parts_dir,
            token=token,
            timeout_seconds=timeout_seconds,
        )
        valid = payload is not None and len(part_rows) == int(chunk)
        if not valid:
            if int(retry) < 1:
                state["pending"].insert(0, [current_offset, chunk, int(retry) + 1])
            elif int(chunk) > 10:
                left = int(chunk) // 2
                state["pending"].insert(
                    0, [int(current_offset) + left, int(chunk) - left, 0]
                )
                state["pending"].insert(0, [current_offset, left, 0])
            else:
                state["worker_failures"] += 1
                state["findings"] += 1
                state["details"].append(
                    {
                        "loop": int(current_offset) + 1,
                        "domain": "batch_worker",
                        "code": "worker_failure",
                        "detail": (
                            f"Loops {int(current_offset) + 1}-"
                            f"{int(current_offset) + int(chunk)}: {diagnostic}"
                        ),
                    }
                )
                state["verified"] += int(chunk)
        else:
            state["checks"] += int(payload.get("checks", 0))
            state["findings"] += int(payload.get("findings", 0))
            state["details"].extend(payload.get("details", []))
            state["rows"].extend(part_rows)
            state["verified"] += int(chunk)
            while (
                int(state["verified"]) >= int(state["next_progress"])
                and int(state["next_progress"]) <= loops
            ):
                print(
                    f"Loop {int(state['next_progress']):05d}: "
                    f"checks={int(state['checks'])} "
                    f"findings={int(state['findings'])} "
                    f"worker_attempts={int(state['worker_attempts'])}",
                    flush=True,
                )
                state["next_progress"] += 1000

        # In der Ausführungsumgebung können native Qt-Ressourcen nach mehreren
        # Child-Prozessen am Elternprozess hängen bleiben. Ein kontrolliertes
        # exec nach sechs Workern setzt den Controller vollständig zurück, ohne
        # einen Loop oder Befund zu verlieren.
        if attempts_this_generation >= 6 and state["pending"]:
            _save_state(state_path, state)
            print(
                f"Controller-Checkpoint: verified={state['verified']} "
                f"pending={len(state['pending'])}",
                flush=True,
            )
            return subprocess.call(_resume_command(args, state_dir), cwd=ROOT)

    normalized: list[dict[str, object]] = []
    for row in state["rows"]:
        normalized.append(
            {
                "loop": int(row["loop"]),
                "domain": row["domain"],
                "checks": int(row["checks"]),
                "result": row["result"],
                "new_findings": int(row["new_findings"]),
            }
        )
    normalized.sort(key=lambda row: int(row["loop"]))
    details = list(state["details"])
    unique = {
        (str(item.get("domain")), str(item.get("code")), str(item.get("detail")))
        for item in details
    }
    elapsed = time.time() - float(state["started_epoch"])
    summary: dict[str, object] = {
        "app_version": app_version(),
        "seed": int(args.seed),
        "loops": loops,
        "verified_loop_rows": len(normalized),
        "batch_size": batch_size,
        "worker_attempts": int(state["worker_attempts"]),
        "worker_failures": int(state["worker_failures"]),
        "checks": int(state["checks"]),
        "findings": int(state["findings"]),
        "unique_findings": len(unique),
        "duration_seconds": round(elapsed, 3),
        "domains": dict(Counter(row["domain"] for row in normalized)),
        "finding_codes": dict(Counter(str(item.get("code")) for item in details)),
        "details": details[:1000],
    }
    write_csv(Path(args.csv).resolve() if args.csv else None, normalized)
    write_json(Path(args.json).resolve() if args.json else None, summary)
    print(
        f"KILLCRITIC USABILITY AUDIT DONE: loops={loops} "
        f"verified_rows={len(normalized)} checks={state['checks']} "
        f"findings={state['findings']} unique={len(unique)} "
        f"duration={elapsed:.2f}s",
        flush=True,
    )
    for finding in details[:30]:
        print(
            f"  FAIL L{finding.get('loop')} {finding.get('domain')}/"
            f"{finding.get('code')}: {finding.get('detail')}",
            flush=True,
        )
    result = 1 if int(state["findings"]) or len(normalized) != loops else 0
    shutil.rmtree(state_dir, ignore_errors=True)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--loops", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=20260717)
    parser.add_argument("--batch-size", type=int, default=75)
    parser.add_argument("--worker-timeout", type=int, default=45)
    parser.add_argument("--json", type=Path)
    parser.add_argument("--csv", type=Path)
    parser.add_argument("--state-dir", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--resume", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
