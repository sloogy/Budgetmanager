from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from model.migrations import CURRENT_VERSION, _get_db_version, migrate_all
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES
from tests.conftest import verbindung_merken


def _conn():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    migrate_all(conn)
    return verbindung_merken(conn)


def test_v16_migration_adds_tag_action_text_column():
    conn = _conn()
    assert _get_db_version(conn) == CURRENT_VERSION
    cols = {r[1] for r in conn.execute("PRAGMA table_info(tags)")}
    assert "action_text" in cols
    conn.close()


def test_category_fixed_tags_are_attached_on_tracking_add():
    conn = _conn()
    conn.execute(
        "INSERT INTO categories(typ, name) VALUES(?, ?)",
        (TYP_EXPENSES, "Essen"),
    )
    category_id = conn.execute(
        "SELECT id FROM categories WHERE typ=? AND name=?",
        (TYP_EXPENSES, "Essen"),
    ).fetchone()[0]
    tags = TagsModel(conn)
    tag_food = tags.create("UBS essen", action_text="{datum} {tag}")
    tag_budget = tags.create("Haushalt")
    tags.set_category_tags(category_id, [tag_food, tag_budget])

    entry_id = TrackingModel(conn).add(
        "2026-07-05", TYP_EXPENSES, "Essen", 12.50, "Lunch"
    )

    names = {t["name"] for t in tags.get_tags_for_entry(entry_id)}
    assert names == {"UBS essen", "Haushalt"}
    conn.close()


def test_fixed_category_tags_survive_manual_set_entry_tags():
    conn = _conn()
    conn.execute(
        "INSERT INTO categories(typ, name) VALUES(?, ?)",
        (TYP_EXPENSES, "Essen"),
    )
    category_id = conn.execute("SELECT id FROM categories").fetchone()[0]
    tags = TagsModel(conn)
    fixed = tags.create("Fix")
    manual = tags.create("Extra")
    tags.set_category_tags(category_id, [fixed])
    entry_id = TrackingModel(conn).add("2026-07-05", TYP_EXPENSES, "Essen", 10, "")

    tags.set_entry_tags(entry_id, [manual])

    names = {t["name"] for t in tags.get_tags_for_entry(entry_id)}
    assert names == {"Fix", "Extra"}
    conn.close()


def test_tag_action_text_template_renders_free_details():
    conn = _conn()
    tags = TagsModel(conn)
    tag_id = tags.create("UBS essen", action_text="{datum} {tag} {kategorie}")

    details = tags.render_action_texts(
        [tag_id], category="Essen", booking_date=date(2026, 7, 5)
    )

    assert details == "2026-07-05 UBS essen Essen"
    conn.close()


def test_quick_add_and_tracking_have_no_empty_tag_dead_end_static():
    quick_add = Path("views/quick_add_dialog.py").read_text(encoding="utf-8")
    tracking_tab = Path("views/tabs/tracking_tab.py").read_text(encoding="utf-8")
    category_dialog = Path("views/category_properties_dialog.py").read_text(
        encoding="utf-8"
    )

    assert "tags.no_tags_click_create" in quick_add
    assert "_create_tag_inline" in quick_add
    assert "_create_tag_inline_for_tracking" in tracking_tab
    assert "set_category_tags" in category_dialog
    assert "categories.fixed_tags.label" in category_dialog
