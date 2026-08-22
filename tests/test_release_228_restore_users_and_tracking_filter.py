from __future__ import annotations

import json
import sqlite3
import zipfile
from pathlib import Path

from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.restore_bundle import bundle_user_security_modes, create_bundle
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    return conn


def test_parent_tracking_filter_can_expand_to_children() -> None:
    conn = _conn()
    try:
        cats = CategoryModel(conn)
        parent_id = cats.create(TYP_EXPENSES, "Wohnen")
        cats.create(TYP_EXPENSES, "Miete", parent_id=parent_id)
        cats.create(TYP_EXPENSES, "Strom", parent_id=parent_id)
        cats.create(TYP_EXPENSES, "Lebensmittel")

        tracking = TrackingModel(conn)
        tracking.add("2026-07-01", TYP_EXPENSES, "Wohnen", 10, "Parent")
        tracking.add("2026-07-02", TYP_EXPENSES, "Miete", 1200, "Kind")
        tracking.add("2026-07-03", TYP_EXPENSES, "Strom", 80, "Kind")
        tracking.add("2026-07-04", TYP_EXPENSES, "Lebensmittel", 40, "Nicht enthalten")

        expanded = cats.descendant_names(TYP_EXPENSES, "Wohnen")
        assert expanded == ["Wohnen", "Miete", "Strom"]

        rows = tracking.list_filtered(typ=TYP_EXPENSES, categories=expanded)
        assert {r.category for r in rows} == {"Wohnen", "Miete", "Strom"}
    finally:
        conn.close()


def test_restore_bundle_keeps_users_json_but_security_modes_are_only_metadata(
    tmp_path: Path,
) -> None:
    db = tmp_path / "christian.enc"
    db.write_bytes(b"encrypted-db-placeholder")
    users = tmp_path / "users.json"
    users.write_text(
        json.dumps(
            {
                "users": [
                    {
                        "username": "christian",
                        "security": "password",
                        "db_filename": "christian.enc",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "backup.bmr"
    create_bundle(
        source_db=db,
        out_path=out,
        app="BudgetManager",
        app_version="2.2.8",
        users_json_path=users,
    )

    with zipfile.ZipFile(out, "r") as zf:
        assert "users.json" in zf.namelist()
        manifest = json.loads(zf.read("manifest.json").decode("utf-8"))
        assert manifest["has_users"] is True

    assert bundle_user_security_modes(out) == {"password"}


def test_tracking_add_uses_same_quickadd_dialog_as_cockpit() -> None:
    src = Path("views/tabs/tracking_tab.py").read_text(encoding="utf-8")
    add_body = src.split("    def add(self):", 1)[1].split(
        "    def _ask_savings_withdrawal", 1
    )[0]
    assert "QuickAddDialog" in add_body
    assert "TrackerDialog" not in add_body
