from __future__ import annotations

import hashlib
from pathlib import Path
import sys


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python tools/make_sha256.py <file.zip>")
        return 2
    p = Path(sys.argv[1]).expanduser().resolve()
    if not p.exists():
        print(f"File not found: {p}")
        return 3
    print(sha256_file(p))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
