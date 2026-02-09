from __future__ import annotations

import hashlib
import os
import shutil
from pathlib import Path
from typing import Iterable


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def copy_tree(src: Path, dst: Path, exclude_names: Iterable[str]) -> None:
    exclude = set(exclude_names)
    ensure_dir(dst)

    for root, dirs, files in os.walk(src):
        root_p = Path(root)
        rel = root_p.relative_to(src)

        # prune dirs
        dirs[:] = [d for d in dirs if d not in exclude]

        target_dir = dst / rel
        ensure_dir(target_dir)

        for fn in files:
            if fn in exclude:
                continue
            s = root_p / fn
            t = target_dir / fn
            shutil.copy2(s, t)


def remove_tree_contents(dst: Path, exclude_names: Iterable[str]) -> None:
    exclude = set(exclude_names)
    if not dst.exists():
        return

    for child in dst.iterdir():
        if child.name in exclude:
            continue
        if child.is_dir():
            shutil.rmtree(child, ignore_errors=True)
        else:
            try:
                child.unlink()
            except FileNotFoundError:
                pass
