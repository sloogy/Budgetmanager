"""v2.2.6 KILLCRITIC-Regression: Der Tracking-Lernzustand
(``tracking_learning_state``, gekeyt auf ``typ`` + ``category``) muss bei
Rename, Reassign und Undo/Redo eines Renames genauso mitgeführt werden wie die
übrigen namensreferenzierenden Tabellen.

Vorher verwaiste die Nutzerentscheidung (watch/ignored/snooze/ended) unter dem
alten Namen: die Kategorie tauchte unter dem neuen Namen wieder im Lernmodus
auf, und die alte Zeile blieb als Leiche stehen. Der Delete-Pfad war bereits
korrekt (``_CATEGORY_TEXT_REFERENCE_TABLES``); Rename/Reassign/Undo nutzten
handgeschriebene SQL-Listen, in denen genau diese Tabelle fehlte.
"""

from __future__ import annotations

import sqlite3

import pytest

from model.budget_overview_model import BudgetOverviewModel
from model.category_model import CategoryModel
from model.migrations import migrate_all
from model.typ_constants import TYP_EXPENSES


@pytest.fixture
def conn() -> sqlite3.Connection:
    c = sqlite3.connect(":memory:")
    c.row_factory = sqlite3.Row
    migrate_all(c)
    yield c
    c.close()


def _states(conn) -> list[tuple]:
    return sorted(
        (r[0], r[1], r[2])
        for r in conn.execute(
            "SELECT typ, category, status FROM tracking_learning_state"
        )
    )


def test_rename_carries_learning_state(conn):
    cat = CategoryModel(conn)
    cid = cat.create(TYP_EXPENSES, "Hobbys")
    BudgetOverviewModel(conn).set_learning_action(TYP_EXPENSES, "Hobbys", "ignore")

    cat.rename_and_cascade(
        cid, typ=TYP_EXPENSES, old_name="Hobbys", new_name="Freizeit"
    )

    assert _states(conn) == [(TYP_EXPENSES, "Freizeit", "ignored")]


def test_undo_redo_rename_keeps_learning_state_consistent(conn):
    cat = CategoryModel(conn)
    cid = cat.create(TYP_EXPENSES, "Hobbys")
    BudgetOverviewModel(conn).set_learning_action(TYP_EXPENSES, "Hobbys", "ignore")

    cat.rename_and_cascade(
        cid, typ=TYP_EXPENSES, old_name="Hobbys", new_name="Freizeit"
    )
    assert cat.undo.undo() is True
    assert _states(conn) == [(TYP_EXPENSES, "Hobbys", "ignored")]

    assert cat.undo.redo() is True
    assert _states(conn) == [(TYP_EXPENSES, "Freizeit", "ignored")]


def test_reassign_does_not_orphan_learning_state(conn):
    cat = CategoryModel(conn)
    src = cat.create(TYP_EXPENSES, "Quelle")
    tgt = cat.create(TYP_EXPENSES, "Ziel")
    BudgetOverviewModel(conn).set_learning_action(TYP_EXPENSES, "Quelle", "ignore")

    cat.delete_category_safely(src, data_action="reassign", reassign_to_id=tgt)

    remaining = _states(conn)
    assert all(row[1] != "Quelle" for row in remaining), remaining


def test_rename_into_existing_learning_state_does_not_crash(conn):
    """Ziel-Name hat bereits einen Lernzustand → kein PK-Konflikt, Quelle weg."""
    cat = CategoryModel(conn)
    a = cat.create(TYP_EXPENSES, "Alpha")
    tgt = cat.create(TYP_EXPENSES, "Beta")
    bom = BudgetOverviewModel(conn)
    bom.set_learning_action(TYP_EXPENSES, "Alpha", "ignore")
    bom.set_learning_action(TYP_EXPENSES, "Beta", "irregular")

    # Reassign Alpha -> Beta: Beta-Lernzustand bleibt erhalten, Alpha verschwindet.
    cat.delete_category_safely(a, data_action="reassign", reassign_to_id=tgt)

    remaining = _states(conn)
    assert all(row[1] != "Alpha" for row in remaining), remaining
    assert (TYP_EXPENSES, "Beta", "irregular") in remaining


def test_delete_still_purges_learning_state(conn):
    """Delete-Pfad war schon korrekt – bleibt korrekt (Nicht-Regression)."""
    cat = CategoryModel(conn)
    cid = cat.create(TYP_EXPENSES, "Weg")
    BudgetOverviewModel(conn).set_learning_action(TYP_EXPENSES, "Weg", "ignore")

    cat.delete_category_safely(cid, data_action="delete_all")

    assert _states(conn) == []
