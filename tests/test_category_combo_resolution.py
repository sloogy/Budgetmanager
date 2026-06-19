"""Regressionstests für editierbare Kategorie-Comboboxen.

Qt hält bei editierbaren QComboBoxen currentData() oft auf dem vorherigen
Eintrag, obwohl der Benutzer im Suchfeld bereits einen anderen Text getippt
hat. Die Schnelleingabe darf dann nicht auf die alte Kategorie buchen.
"""
from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FakeCombo:
    def __init__(
        self,
        rows: list[tuple[str, object]],
        current_index: int = 0,
        typed_text: str | None = None,
        editable: bool = True,
    ):
        self.rows = rows
        self._current_index = current_index
        self._typed_text = typed_text
        self._editable = editable

    def currentData(self):
        if self._current_index < 0:
            return None
        return self.rows[self._current_index][1]

    def currentText(self):
        if self._typed_text is not None:
            return self._typed_text
        if self._current_index < 0:
            return ""
        return self.rows[self._current_index][0]

    def currentIndex(self):
        return self._current_index

    def itemText(self, i: int):
        return self.rows[i][0]

    def itemData(self, i: int):
        return self.rows[i][1]

    def count(self):
        return len(self.rows)

    def isEditable(self):
        return self._editable


def _picker():
    qtcore = types.ModuleType("PySide6.QtCore")
    qtcore.Qt = types.SimpleNamespace(
        MatchContains=1,
        CaseInsensitive=0,
        NoItemFlags=0,
    )
    qtwidgets = types.ModuleType("PySide6.QtWidgets")
    qtwidgets.QComboBox = object

    class _Completer:
        PopupCompletion = 1

        def __init__(self, *args, **kwargs):
            pass

    qtwidgets.QCompleter = _Completer
    pyside = types.ModuleType("PySide6")

    names = ["PySide6", "PySide6.QtCore", "PySide6.QtWidgets"]
    old = {name: sys.modules.get(name) for name in names}
    try:
        sys.modules["PySide6"] = pyside
        sys.modules["PySide6.QtCore"] = qtcore
        sys.modules["PySide6.QtWidgets"] = qtwidgets
        spec = importlib.util.spec_from_file_location(
            "category_picker_under_test", ROOT / "views" / "category_picker.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    finally:
        for name, module in old.items():
            if module is None:
                sys.modules.pop(name, None)
            else:
                sys.modules[name] = module


def test_typed_existing_category_beats_stale_current_data():
    picker = _picker()
    combo = FakeCombo(
        [("Lebensmittel", "Lebensmittel"), ("Miete", "Miete")],
        current_index=0,
        typed_text="Miete",
    )
    assert picker.resolve_combo_category(combo) == "Miete"


def test_tree_label_and_favorite_marker_resolve_to_real_data():
    picker = _picker()
    combo = FakeCombo(
        [("★ Wohnen › Miete", "Miete"), ("Freizeit", "Freizeit")],
        current_index=1,
        typed_text="Miete",
    )
    assert picker.resolve_combo_category(combo) == "Miete"


def test_new_typed_category_does_not_return_old_current_data():
    picker = _picker()
    combo = FakeCombo(
        [("Lebensmittel", "Lebensmittel"), ("Miete", "Miete")],
        current_index=0,
        typed_text="Neue Kategorie",
    )
    assert picker.resolve_combo_category(combo) == "Neue Kategorie"


def test_non_editable_dropdown_uses_current_data_only():
    picker = _picker()
    combo = FakeCombo(
        [("★ Wohnen › Miete", "Miete"), ("Lebensmittel", "Lebensmittel")],
        current_index=0,
        typed_text=None,
        editable=False,
    )
    assert picker.resolve_combo_category(combo) == "Miete"


def test_category_search_filters_items_but_keeps_matching_group_header():
    picker = _picker()
    grouped = [
        ("header", "★ Favoriten", None),
        ("item", "★ Wohnen › Miete", "Miete"),
        ("item", "★ Freizeit", "Freizeit"),
        ("header", "Normale Buchungen", None),
        ("item", "Lebensmittel › Coop", "Coop"),
    ]
    assert picker.filter_grouped_categories(grouped, "mie") == [
        ("header", "★ Favoriten", None),
        ("item", "★ Wohnen › Miete", "Miete"),
    ]


def test_category_search_matches_child_name_and_real_name():
    picker = _picker()
    grouped = [
        ("header", "Normale Buchungen", None),
        ("item", "Lebensmittel › Coop", "Coop"),
    ]
    assert picker.filter_grouped_categories(grouped, "coop") == grouped
    assert picker.filter_grouped_categories(grouped, "lebens") == grouped
