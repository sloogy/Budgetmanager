from __future__ import annotations

from pathlib import Path

import pytest

from model.date_ranges import month_bounds, year_bounds

ROOT = Path(__file__).resolve().parents[1]


def test_month_bounds_are_half_open_and_cover_year_edges() -> None:
    assert month_bounds(2024, 1) == ("2024-01-01", "2024-02-01")
    assert month_bounds(2024, 2) == ("2024-02-01", "2024-03-01")
    assert month_bounds(2024, 12) == ("2024-12-01", "2025-01-01")
    assert year_bounds(2024) == ("2024-01-01", "2025-01-01")


@pytest.mark.parametrize("bad_month", [0, 13, -1])
def test_month_bounds_reject_invalid_months(bad_month: int) -> None:
    with pytest.raises(ValueError):
        month_bounds(2024, bad_month)


def test_no_duplicate_private_month_bounds_remain() -> None:
    for rel in ["model/tracking_model.py", "views/tabs/cockpit_tab.py"]:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "def _month_bounds" not in src
        assert "from model.date_ranges import" in src


def test_busy_timeout_matches_connection_timeout_intent() -> None:
    for rel in [
        "model/database.py",
        "model/crypto.py",
        "views/startup_wizard.py",
        "views/backup_restore_dialog.py",
    ]:
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "PRAGMA busy_timeout = 10000;" in src
        assert "PRAGMA busy_timeout = 5000;" not in src
