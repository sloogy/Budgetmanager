from __future__ import annotations

import re
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_active_markdown_links_resolve_locally() -> None:
    documents = [
        ROOT / "README.md",
        ROOT / "README_INSTALLATION.md",
        ROOT / "FEATURES.md",
        *sorted((ROOT / "docs").glob("*.md")),
    ]
    missing: list[str] = []
    for document in documents:
        text = document.read_text(encoding="utf-8")
        for match in re.finditer(r"\[[^\]]*\]\(([^)]+)\)", text):
            target = match.group(1).strip().split("#", 1)[0]
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            target_path = (document.parent / target.replace("%20", " ")).resolve()
            try:
                target_path.relative_to(ROOT)
            except ValueError:
                continue
            if not target_path.exists():
                line = text.count("\n", 0, match.start()) + 1
                missing.append(f"{document.relative_to(ROOT)}:{line} -> {target}")
    assert not missing, "Fehlende lokale Dokumentationsziele:\n" + "\n".join(missing)


def test_update_zip_rejects_casefold_and_separator_collisions(tmp_path: Path) -> None:
    from updater.common import safe_extract_zip

    archive = tmp_path / "collision.zip"
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr("BudgetManager/App.txt", "first")
        zf.writestr("budgetmanager\\app.TXT", "second")

    with pytest.raises(ValueError, match="Doppelte|kollidierende"):
        safe_extract_zip(archive, tmp_path / "staging")
