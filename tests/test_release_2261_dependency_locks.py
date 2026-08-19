"""Regressionsschutz für versionssynchrone v2.2.61-Hash-Lockfiles."""

from pathlib import Path

from tools.verify_hashed_lock import validate

ROOT = Path(__file__).resolve().parents[1]


def test_release_locks_match_all_direct_and_included_pins() -> None:
    pairs = (
        ("requirements.lock", "requirements.in"),
        ("requirements-build.lock", "requirements-build.in"),
        ("requirements-dev.lock", "requirements-dev.in"),
    )
    for lock, direct in pairs:
        assert validate(ROOT / lock, ROOT / direct) == []


def test_lock_validator_rejects_direct_version_drift(tmp_path: Path) -> None:
    runtime = tmp_path / "runtime.in"
    runtime.write_text("example-package==2.0\n", encoding="utf-8")
    direct = tmp_path / "build.in"
    direct.write_text("-r runtime.in\nbuilder==3.0\n", encoding="utf-8")
    lock = tmp_path / "build.lock"
    lock.write_text(
        "example-package==1.0 \\\n"
        "    --hash=sha256:" + "0" * 64 + "\n\n"
        "builder==3.0 \\\n"
        "    --hash=sha256:" + "1" * 64 + "\n",
        encoding="utf-8",
    )

    errors = validate(lock, direct)
    assert any("example-package ist 1.0, erwartet 2.0" in error for error in errors)
