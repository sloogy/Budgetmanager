"""Regression: global eingestellter Standard-Fälligkeitstag.

Wenn der Nutzer in den Einstellungen z. B. den 25. als bevorzugten Tag setzt,
muss dieser Tag auch bei neuer Kategorie-Erstellung und beim späteren Aktivieren
von "wiederkehrend" greifen. Der alte Fehler war, dass mehrere UI-/Model-Pfade
stumm den Datenbank-Default 1 übernommen haben.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

from model.database import open_db
from model.migrations import migrate_all
from model.category_model import CategoryModel
from model.typ_constants import TYP_EXPENSES
from settings import Settings


def _fresh(tmp_path: Path, monkeypatch, preferred_day: int = 25):
    app_dir = tmp_path / "app"
    app_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("BUDGETMANAGER_APP_DIR", str(app_dir))
    Settings().set("recurring_preferred_day", preferred_day)

    fd, p = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    conn = open_db(p)
    migrate_all(conn, db_path=p)
    return conn, p


def test_create_recurring_category_uses_preferred_day(tmp_path, monkeypatch):
    conn, p = _fresh(tmp_path, monkeypatch, preferred_day=25)
    try:
        cats = CategoryModel(conn)
        cat_id = cats.create(TYP_EXPENSES, "Streaming", is_recurring=True)
        row = conn.execute("SELECT is_recurring, recurring_day FROM categories WHERE id=?", (cat_id,)).fetchone()
        assert int(row["is_recurring"]) == 1
        assert int(row["recurring_day"]) == 25
    finally:
        conn.close()
        os.remove(p)


def test_switching_existing_category_to_recurring_uses_preferred_day(tmp_path, monkeypatch):
    conn, p = _fresh(tmp_path, monkeypatch, preferred_day=25)
    try:
        cats = CategoryModel(conn)
        cat_id = cats.create(TYP_EXPENSES, "Krankenkasse", is_recurring=False)

        cats.update_flags(cat_id, is_recurring=True)

        row = conn.execute("SELECT is_recurring, recurring_day FROM categories WHERE id=?", (cat_id,)).fetchone()
        assert int(row["is_recurring"]) == 1
        assert int(row["recurring_day"]) == 25
    finally:
        conn.close()
        os.remove(p)


def test_existing_recurring_category_keeps_explicit_day_when_only_resaved(tmp_path, monkeypatch):
    conn, p = _fresh(tmp_path, monkeypatch, preferred_day=25)
    try:
        cats = CategoryModel(conn)
        cat_id = cats.create(TYP_EXPENSES, "Miete", is_recurring=True, recurring_day=1)

        cats.update_flags(cat_id, is_recurring=True)

        row = conn.execute("SELECT recurring_day FROM categories WHERE id=?", (cat_id,)).fetchone()
        assert int(row["recurring_day"]) == 1
    finally:
        conn.close()
        os.remove(p)


def test_release_paths_no_longer_hardcode_day_one_for_recurring_defaults():
    files = {
        "views/budget_entry_dialog.py": "CategoryModel.preferred_recurring_day()",
        "views/budget_entry_dialog_extended.py": "CategoryModel.preferred_recurring_day()",
        "views/category_properties_dialog.py": "CategoryModel.preferred_recurring_day()",
        "views/tabs/budget_tab.py": "CategoryModel.preferred_recurring_day()",
    }
    for filename, marker in files.items():
        text = Path(filename).read_text(encoding="utf-8")
        assert marker in text, filename
