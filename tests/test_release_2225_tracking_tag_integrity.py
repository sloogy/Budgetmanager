from __future__ import annotations

import sqlite3
from datetime import date

import pytest

from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.tags_model import TagsModel
from model.tracking_model import TrackingModel
from model.typ_constants import TYP_EXPENSES


_OPEN_CONNECTIONS: list[sqlite3.Connection] = []


@pytest.fixture(autouse=True)
def _close_connections_after_test():
    yield
    while _OPEN_CONNECTIONS:
        _OPEN_CONNECTIONS.pop().close()


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    migrate_all(conn)
    _OPEN_CONNECTIONS.append(conn)
    return conn


def _tag_ids(tags: TagsModel, entry_id: int) -> set[int]:
    return {int(row["id"]) for row in tags.get_tags_for_entry(entry_id)}


def test_category_change_replaces_old_fixed_tags_and_keeps_manual_tags():
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)

    old_category = categories.create(TYP_EXPENSES, "Alt")
    new_category = categories.create(TYP_EXPENSES, "Neu")
    old_fixed = tags.create("Alt fix")
    new_fixed = tags.create("Neu fix")
    manual = tags.create("Manuell")
    tags.set_category_tags(old_category, [old_fixed])
    tags.set_category_tags(new_category, [new_fixed])

    entry_id = tracking.add(date(2026, 7, 1), TYP_EXPENSES, "Alt", 10, "")
    tags.set_entry_tags(entry_id, [manual])
    tracking.update(entry_id, date(2026, 7, 2), TYP_EXPENSES, "Neu", 11, "")

    assert _tag_ids(tags, entry_id) == {new_fixed, manual}


def test_tracking_delete_undo_redo_preserves_complete_tag_set():
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)

    category_id = categories.create(TYP_EXPENSES, "Essen")
    fixed = tags.create("Fix")
    manual = tags.create("Manuell")
    tags.set_category_tags(category_id, [fixed])
    entry_id = tracking.add(date(2026, 7, 1), TYP_EXPENSES, "Essen", 20, "")
    tags.set_entry_tags(entry_id, [manual])
    expected = {fixed, manual}

    tracking.delete(entry_id)
    assert tracking.undo.undo()
    assert _tag_ids(tags, entry_id) == expected

    assert tracking.undo.redo()
    assert not conn.execute("SELECT 1 FROM tracking WHERE id=?", (entry_id,)).fetchone()

    assert tracking.undo.undo()
    assert _tag_ids(tags, entry_id) == expected


def test_tracking_insert_redo_restores_fixed_tags():
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)

    category_id = categories.create(TYP_EXPENSES, "Miete")
    fixed = tags.create("Fixkosten")
    tags.set_category_tags(category_id, [fixed])
    entry_id = tracking.add(date(2026, 7, 1), TYP_EXPENSES, "Miete", 1500, "")

    assert tracking.undo.undo()
    assert tracking.undo.redo()
    assert _tag_ids(tags, entry_id) == {fixed}


def test_tracking_update_undo_redo_restores_each_tag_state():
    conn = _conn()
    categories = CategoryModel(conn)
    tracking = TrackingModel(conn)
    tags = TagsModel(conn)

    old_category = categories.create(TYP_EXPENSES, "Alt")
    new_category = categories.create(TYP_EXPENSES, "Neu")
    old_fixed = tags.create("Alt fix")
    new_fixed = tags.create("Neu fix")
    manual = tags.create("Manuell")
    tags.set_category_tags(old_category, [old_fixed])
    tags.set_category_tags(new_category, [new_fixed])

    entry_id = tracking.add(date(2026, 7, 1), TYP_EXPENSES, "Alt", 10, "")
    tags.set_entry_tags(entry_id, [manual])
    old_tags = {old_fixed, manual}

    tracking.update(entry_id, date(2026, 7, 2), TYP_EXPENSES, "Neu", 11, "")
    new_tags = {new_fixed, manual}
    assert _tag_ids(tags, entry_id) == new_tags

    assert tracking.undo.undo()
    assert _tag_ids(tags, entry_id) == old_tags

    assert tracking.undo.redo()
    assert _tag_ids(tags, entry_id) == new_tags


def test_tracking_read_methods_preserve_booking_source():
    conn = _conn()
    CategoryModel(conn).create(TYP_EXPENSES, "Miete")
    tracking = TrackingModel(conn)
    entry_id = tracking.add(
        date.today(),
        TYP_EXPENSES,
        "Miete",
        1500,
        "",
        source="auto_fixcost",
    )

    readers = (
        tracking.list_all_sorted,
        lambda: tracking.list_recent_sorted(2),
        lambda: tracking.list_filtered(category="Miete"),
        lambda: tracking.last_n_by_abs_amount(5),
    )
    for reader in readers:
        row = next(item for item in reader() if item.id == entry_id)
        assert row.source == "auto_fixcost"
