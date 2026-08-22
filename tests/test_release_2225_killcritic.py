"""Regressionstests fuer die KILLCRITIC-X10THINK-Fixes in v2.2.25.

Alle Tests sind Qt-frei und laufen headless: Waisen-Fix im Undo-/Redo-
Loeschpfad (funktional gegen echte In-Memory-DB), Migration 17,
Menu-Mnemonic-Maskierung, Theme-Editor-Schliessleiste (Quelltext),
Guide-Kapitel in drei Sprachen sowie Form und Nachweis des
KILLCRITIC-Werkzeugs.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGS = ("de", "en", "fr")


def _flat(d: dict, pre: str = "") -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in d.items():
        kk = f"{pre}.{k}" if pre else k
        if isinstance(v, dict):
            out.update(_flat(v, kk))
        else:
            out[kk] = v
    return out


def _loc(lang: str) -> dict[str, str]:
    return _flat(json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8")))


# ── 1. Waisen-Fix funktional: add -> delete -> undo -> redo ──────────────
def test_redo_delete_leaves_no_orphaned_entry_tags():
    import sys

    sys.path.insert(0, str(ROOT))
    from model.category_model import CategoryModel
    from model.migrations import migrate_all
    from model.tags_model import TagsModel
    from model.tracking_model import TrackingModel

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    migrate_all(conn)
    cat = CategoryModel(conn)
    trk = TrackingModel(conn)
    tags = TagsModel(conn)

    cid = cat.create("Ausgaben", "KCReg")
    tid = tags.create_tag("kc_reg", "#123456")
    tags.assign_to_category(cid, tid)
    eid = trk.add("2026-03-15", "Ausgaben", "KCReg", 42.0, details="kc")
    assert eid

    trk.delete(eid)
    assert trk.undo.undo()
    assert trk.undo.redo()
    orphans = conn.execute(
        "SELECT COUNT(*) FROM entry_tags et LEFT JOIN tracking t"
        " ON t.id = et.entry_id WHERE t.id IS NULL"
    ).fetchone()[0]
    assert orphans == 0, f"{orphans} verwaiste entry_tags nach Redo"

    # Erneutes Undo stellt Buchung UND Tag wieder her.
    assert trk.undo.undo()
    rows = conn.execute("SELECT entry_id, tag_id FROM entry_tags").fetchall()
    assert len(rows) == 1 and rows[0]["tag_id"] == tid
    conn.close()


# ── 2. Migration 17 registriert und dokumentiert ────────────────────────
def test_migration_17_registered():
    import sys

    sys.path.insert(0, str(ROOT))
    from model import migrations

    assert migrations.CURRENT_VERSION >= 18
    src = (ROOT / "model" / "migrations.py").read_text("utf-8")
    assert "_migrate_v17_cleanup_orphaned_entry_tags" in src
    assert "v16→v17" in src
    assert "v17→v18" in src
    # Loeschpfad-Symmetrie im Undo-Modell
    undo_src = (ROOT / "model" / "undo_redo_model.py").read_text("utf-8")
    assert "DELETE FROM entry_tags WHERE entry_id=?" in undo_src


# ── 3. Menu-Mnemonic in allen drei Sprachen maskiert ────────────────────
def test_account_data_menu_mnemonic_is_unambiguous():
    for lang in LANGS:
        val = _loc(lang)["menu.account_data"]
        # Genau ein echter Mnemonic; literale Ampersands sind als && maskiert.
        assert val.count("&") - 2 * val.count("&&") == 1, f"{lang}: {val!r}"
        assert " & " not in val, f"{lang}: unmaskiertes literales &: {val!r}"


# ── 4. Theme-Editor besitzt eine Schliessen-Leiste ──────────────────────
def test_theme_editor_has_close_bar():
    src = (ROOT / "views" / "theme_editor_dialog.py").read_text("utf-8")
    assert "QDialogButtonBox" in src
    assert 'tr("btn.close")' in src
    assert "buttons.rejected.connect(self.reject)" in src


# ── 5. Guide-Kapitel in drei Sprachen vorhanden ─────────────────────────
def test_guides_cover_new_chapters():
    heads = {
        "de": [
            "## Erststart in vier Schritten",
            "## 9. Cockpit",
            "## 10. Tags",
            "## 11. Konten",
            "## 12. Monatsabschluss",
        ],
        "en": [
            "## First start in four steps",
            "## 9. Cockpit",
            "## 10. Tags",
            "## 11. Accounts",
            "## 12. Month close",
        ],
        "fr": [
            "## Premier démarrage en quatre étapes",
            "## 9. Cockpit",
            "## 10. Tags",
            "## 11. Comptes",
            "## 12. Clôture mensuelle",
        ],
    }
    for lang, needles in heads.items():
        guide = (ROOT / "docs" / f"USER_GUIDE.{lang}.md").read_text("utf-8")
        for n in needles:
            assert n in guide, f"{lang}: {n!r} fehlt"
        # 5.1 steht wieder vor Kapitel 6
        assert guide.index("## 5.1") < guide.index("## 6.")


# ── 6. Werkzeug-Form und Nachweis ───────────────────────────────────────
def test_killcritic_tool_shape():
    src = (ROOT / "tools" / "killcritic_x10think_10000.py").read_text("utf-8")
    assert "LOOPS_PER_DOMAIN = 1000" in src
    for dom in (
        "k1_first_run_path",
        "k2_booking_lifecycle",
        "k3_bundle_roundtrip",
        "k4_guide_coverage",
        "k5_help_wiki",
        "k6_text_quality",
        "k7_update_path",
        "k8_key_discipline",
        "k9_dialog_invariants",
        "k10_regression_shield",
    ):
        assert f"def {dom}(" in src, dom
    assert (
        ROOT
        / "docs"
        / "archive"
        / "release-evidence"
        / "KILLCRITIC_X10THINK_10000_MATRIX_v2_2_25.csv"
    ).exists()
    assert (
        ROOT
        / "docs"
        / "archive"
        / "release-evidence"
        / "KILLCRITIC_X10THINK_10000_v2_2_25.md"
    ).exists()
