"""Regressionstests v2.2.31.

Befund A: tools/lint_procedure_check.py:check_generated_artifacts() war toter
Code – dirnames wurden zuerst beschnitten, danach gegen dieselbe Namensmenge
geprueft. Dadurch landeten __pycache__/.pytest_cache im v2.2.30-Release-ZIP,
obwohl das Gate PASS meldete.

Befund B: TagsModel lieferte uneinheitlich Tag-Objekte und rohe dicts.
"""

from __future__ import annotations

import ast
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model.migrations import migrate_all
from model.tags_model import Tag, TagsModel
from tests.conftest import verbindung_merken

GATE = ROOT / "tools" / "lint_procedure_check.py"


# ────────────────────────────────────────────────────────────────
# Befund A – Artefakt-Erkennung im Release-Gate
# ────────────────────────────────────────────────────────────────


def _check_generated_artifacts_source() -> str:
    """Quelltext der Pruef-Funktion isoliert extrahieren."""
    tree = ast.parse(GATE.read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.FunctionDef)
            and node.name == "check_generated_artifacts"
        ):
            return ast.get_source_segment(GATE.read_text(encoding="utf-8"), node) or ""
    raise AssertionError("check_generated_artifacts() nicht gefunden")


def test_detection_happens_before_pruning():
    """Kernregression: Erkennung MUSS vor der dirnames-Zuweisung stehen.

    Genau diese Reihenfolge war in v2.2.30 vertauscht und machte den Check tot.
    """
    src = _check_generated_artifacts_source()
    detect_pos = src.find("generated_dir_names")
    # Die Slice-Zuweisung dirnames[:] = ... ist das Pruning.
    prune_pos = src.find("dirnames[:]")
    assert detect_pos != -1, "Erkennungsbedingung fehlt"
    assert prune_pos != -1, "Pruning fehlt (wird fuer Laufzeit/venv-Schutz gebraucht)"
    detect_in_loop = src.find("if dirname in generated_dir_names")
    assert detect_in_loop != -1, "Meldebedingung fehlt"
    assert detect_in_loop < prune_pos, (
        "Erkennung steht nach dem Pruning – der Check waere wieder tot "
        "(Regression von v2.2.30)"
    )


def test_pruning_is_still_present():
    """Das Pruning darf nicht ersatzlos entfernt worden sein."""
    src = _check_generated_artifacts_source()
    assert "_is_excluded_path" in src, "venv-/Abstiegsschutz entfernt"


def test_workflow_cleans_before_verifying():
    """Der Cleaner MUSS im Tag-Build vor dem Lint-Gate laufen.

    Sonst meldet das (jetzt scharfe) Gate die Artefakte, die der Cleaner
    unmittelbar davor haette entfernen sollen, und der Build bricht ab.
    """
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    clean_pos = workflow.find("tools/clean_release_tree.py")
    lint_pos = workflow.find("tools/lint_procedure_check.py")
    assert clean_pos != -1, "Clean-Step fehlt im Tag-Build"
    assert lint_pos != -1, "Lint-Step fehlt im Tag-Build"
    assert clean_pos < lint_pos, "Cleaner laeuft nach dem Lint-Gate"


def test_workflow_suppresses_bytecode_during_tests():
    """PYTHONDONTWRITEBYTECODE haelt den Baum waehrend der Tests sauber."""
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "PYTHONDONTWRITEBYTECODE" in workflow


def test_gate_function_reports_injected_artifacts(monkeypatch, tmp_path):
    """Funktionsebene: injizierte Artefakte werden gemeldet."""
    sys.path.insert(0, str(ROOT / "tools"))
    import lint_procedure_check as gate

    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "__pycache__").mkdir()
    (tmp_path / "pkg" / "__pycache__" / "m.cpython-313.pyc").write_bytes(b"\x00")
    (tmp_path / ".pytest_cache").mkdir()
    (tmp_path / ".pytest_cache" / "CACHEDIR.TAG").write_text("x", encoding="utf-8")

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    errors = gate.check_generated_artifacts()
    joined = "\n".join(errors)
    assert "__pycache__" in joined, f"__pycache__ nicht gemeldet: {errors}"
    assert ".pytest_cache" in joined, f".pytest_cache nicht gemeldet: {errors}"


def test_pyc_files_are_found_recursively(monkeypatch, tmp_path):
    """Befund A2: *.pyc liegt nur in Unterordnern – rglob ist Pflicht."""
    sys.path.insert(0, str(ROOT / "tools"))
    import lint_procedure_check as gate

    deep = tmp_path / "a" / "b" / "c"
    deep.mkdir(parents=True)
    (deep / "stale.pyc").write_bytes(b"\x00")

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    errors = gate.check_generated_artifacts()
    assert any(
        "stale.pyc" in e for e in errors
    ), f"tief liegende .pyc nicht gefunden (rglob fehlt?): {errors}"


def test_root_relative_patterns_stay_root_relative(monkeypatch, tmp_path):
    """Muster mit Pfadtrenner duerfen NICHT baumweit greifen.

    Ein 'users.json' in einem Unterordner ist Testfixture, kein Nutzerdatum;
    nur data/users.json an der Wurzel ist ein Release-Verstoss.
    """
    sys.path.insert(0, str(ROOT / "tools"))
    import lint_procedure_check as gate

    nested = tmp_path / "tests" / "fixtures" / "data"
    nested.mkdir(parents=True)
    (nested / "users.json").write_text("{}", encoding="utf-8")

    monkeypatch.setattr(gate, "ROOT", tmp_path)
    errors = gate.check_generated_artifacts()
    assert not any(
        "users.json" in e for e in errors
    ), f"wurzelrelatives Muster hat baumweit gegriffen: {errors}"


def test_clean_tree_passes_gate(monkeypatch, tmp_path):
    """Ein sauberer Baum meldet keine Artefakte."""
    sys.path.insert(0, str(ROOT / "tools"))
    import lint_procedure_check as gate

    (tmp_path / "model").mkdir()
    (tmp_path / "model" / "x.py").write_text("x = 1\n", encoding="utf-8")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    assert gate.check_generated_artifacts() == []


# Hinweis: Ein Test gegen den LIVE-Baum ("enthaelt ROOT gerade Artefakte?")
# waere prinzipiell flaky – der Testlauf selbst erzeugt __pycache__, sofern
# PYTHONDONTWRITEBYTECODE nicht gesetzt ist. Die Durchsetzung erfolgt deshalb
# ueber die oben geprueften Build-Steps (clean -> lint), nicht hier.


# ────────────────────────────────────────────────────────────────
# Befund B – einheitlicher Tags-Rueckgabetyp
# ────────────────────────────────────────────────────────────────


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    return verbindung_merken(conn)


def test_all_read_methods_return_tag_objects():
    with closing(_db()) as conn:
        m = TagsModel(conn)
        m.create("Urlaub", "#ff8800", "Reise")
        for meth in ("list_all", "list_tags", "get_all_tags"):
            rows = getattr(m, meth)()
            assert rows, f"{meth} lieferte nichts"
            assert all(
                isinstance(r, Tag) for r in rows
            ), f"{meth} liefert {type(rows[0]).__name__} statt Tag (Regression v2.2.30)"


def test_get_tags_for_entry_returns_tag_objects():
    with closing(_db()) as conn:
        m = TagsModel(conn)
        tid = m.create("Urlaub", "#ff8800")
        conn.execute(
            "INSERT INTO tracking(date,typ,category,amount,details) "
            "VALUES('2026-07-01','Ausgaben','Reise',100.0,'x')"
        )
        conn.commit()
        rid = int(conn.execute("SELECT id FROM tracking").fetchone()[0])
        m.assign_to_entry(rid, tid)
        rows = m.get_tags_for_entry(rid)
        assert rows and all(isinstance(r, Tag) for r in rows)


def test_dict_style_access_still_works():
    """Rueckwaertskompatibilitaet: bestehende Views nutzen t["id"]."""
    with closing(_db()) as conn:
        m = TagsModel(conn)
        m.create("Urlaub", "#ff8800", "Reise {kategorie}")
        tag = m.get_all_tags()[0]
        assert tag["name"] == "Urlaub"
        assert tag["color"] == "#ff8800"
        assert tag["action_text"] == "Reise {kategorie}"
        assert int(tag["id"]) > 0


def test_attribute_and_mapping_access_agree():
    with closing(_db()) as conn:
        m = TagsModel(conn)
        m.create("Urlaub", "#ff8800", "Reise")
        tag = m.list_all()[0]
        for key in ("id", "name", "color", "action_text"):
            assert tag[key] == getattr(tag, key)
            assert tag.get(key) == getattr(tag, key)
            assert key in tag


def test_tag_converts_to_dict():
    with closing(_db()) as conn:
        m = TagsModel(conn)
        m.create("Urlaub", "#ff8800", "Reise")
        tag = m.list_all()[0]
        as_dict = dict(tag)
        assert as_dict == tag.to_dict()
        assert set(as_dict) == {"id", "name", "color", "action_text"}


def test_unknown_key_raises_keyerror():
    with closing(_db()) as conn:
        m = TagsModel(conn)
        m.create("Urlaub")
        tag = m.list_all()[0]
        try:
            tag["gibtsnicht"]
        except KeyError:
            pass
        else:
            raise AssertionError("unbekannter Key haette KeyError ausloesen muessen")
        assert tag.get("gibtsnicht") is None
        assert tag.get("gibtsnicht", "fallback") == "fallback"
        assert "gibtsnicht" not in tag


def test_missing_entry_tags_table_returns_empty_list():
    """Alte DBs ohne entry_tags duerfen nicht crashen."""
    with closing(sqlite3.connect(":memory:")) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("CREATE TABLE tags(id INTEGER PRIMARY KEY, name TEXT, color TEXT)")
        conn.commit()
        assert TagsModel(conn).get_tags_for_entry(1) == []
