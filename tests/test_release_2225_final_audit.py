"""Regressionstests fuer das v2.2.28 Final-Release-Audit.

Sichert headless (ohne Qt) ab:
  1. Ultimo-Klemmung der Faelligkeiten (Kern-Bugfix)
  2. SQL-Identifier-/Whitelist-Guards der vier gehaerteten Stellen
  3. d9-Teilfix: die zwei Statusrueckmeldungen in main_window sind
     nicht mehr modal, sondern laufen ueber die Statusleiste
  4. Audit-Tool vorhanden, 10 Domaenen, CSV-Namensschema versioniert
  5. Version 2.2.28 als einzige Quelle synchron
"""

from __future__ import annotations

import re
import sqlite3
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


# ── 1. Ultimo-Klemmung ───────────────────────────────────────────────────
def _open(due_day, year, month, today, *, booked=0.0, budget=100.0):
    from model.fixed_cost_due import is_open_this_month

    return is_open_this_month(
        is_fix=True,
        is_recurring=True,
        budget=budget,
        booked=booked,
        due_day=due_day,
        year=year,
        month=month,
        today=today,
    )


def test_due_31_open_on_feb_ultimo_non_leap():
    open_, rest = _open(31, 2026, 2, date(2026, 2, 28))
    assert open_ is True and rest == 100.0


def test_due_31_open_on_feb_ultimo_leap():
    open_, rest = _open(31, 2024, 2, date(2024, 2, 29))
    assert open_ is True and rest == 100.0


def test_due_31_not_open_before_feb_ultimo_leap():
    open_, _ = _open(31, 2024, 2, date(2024, 2, 28))
    assert open_ is False


def test_due_31_open_on_april_30():
    open_, _ = _open(31, 2026, 4, date(2026, 4, 30))
    assert open_ is True


def test_due_semantics_unchanged_in_full_months():
    assert _open(31, 2026, 1, date(2026, 1, 30))[0] is False
    assert _open(31, 2026, 1, date(2026, 1, 31))[0] is True


def test_due_past_month_always_open_and_booked_never_open():
    assert _open(31, 2026, 2, date(2026, 3, 5))[0] is True
    open_, rest = _open(15, 2026, 6, date(2026, 6, 20), booked=100.0)
    assert open_ is False and rest == 0.0


# ── 2. SQL-Guards ────────────────────────────────────────────────────────
def test_migrations_cols_rejects_non_identifier():
    from model.migrations import _cols

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE demo (id INTEGER, name TEXT)")
    assert _cols(conn, "demo") == {"id", "name"}
    assert _cols(conn, "demo; DROP TABLE demo") == set()
    assert _cols(conn, 'demo") --') == set()
    conn.close()


def test_tags_model_has_column_rejects_non_identifier():
    from model.tags_model import TagsModel

    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE tags (id INTEGER, name TEXT)")
    tm = TagsModel(conn)
    assert tm._has_column("tags", "name") is True
    assert tm._has_column("tags; --", "name") is False
    conn.close()


def test_tracking_model_cols_rejects_non_identifier():
    from model.tracking_model import TrackingModel

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE tracking (id INTEGER, date TEXT)")
    tr = TrackingModel(conn)
    assert "date" in tr._cols("tracking")
    assert tr._cols("tracking OR 1=1") == set()
    conn.close()


def test_undo_push_to_other_stack_rejects_foreign_table():
    from model.undo_redo_model import UndoRedoModel, UndoRow
    import pytest

    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    model = UndoRedoModel(conn)
    row = UndoRow(
        id=1,
        ts="2026-07-17 12:00:00",
        table_name="tracking",
        operation="delete",
        old_data=None,
        new_data=None,
        group_id="g",
    )
    with pytest.raises(ValueError):
        model._push_to_other_stack("evil_table", row)
    conn.close()


def test_category_usage_where_guard_source():
    src = (ROOT / "model" / "category_model.py").read_text(encoding="utf-8")
    assert "_safe_table(table)" in src
    assert r"[A-Za-z_][A-Za-z0-9_]*=\?(?: AND [A-Za-z_][A-Za-z0-9_]*=\?)*" in src


# ── 3. d9: nicht-modale Toasts statt modaler Infos (Enterprise-Merge) ───
def _mw_src() -> str:
    return (ROOT / "views" / "main_window.py").read_text(encoding="utf-8")


def test_keep_one_tab_uses_nonmodal_toast():
    src = _mw_src()
    idx = src.index("cockpit.keep_one_tab")
    window = src[max(0, idx - 400) : idx + 60]
    assert "show_info(" in window
    assert "QMessageBox.information" not in window


def test_data_dir_migrate_done_uses_nonmodal_toast():
    src = _mw_src()
    idx = src.index("settings.data_dir_migrate_done_msg")
    window = src[max(0, idx - 400) : idx + 60]
    assert "show_info(" in window
    assert "QMessageBox.information" not in window


def test_no_modal_info_dialogs_in_views():
    total = 0
    for f in (ROOT / "views").rglob("*.py"):
        total += f.read_text(encoding="utf-8").count("QMessageBox.information")
    total += (
        (ROOT / "settings_dialog.py")
        .read_text(encoding="utf-8")
        .count("QMessageBox.information")
    )
    assert total == 0, f"{total} modale Informationsdialoge gefunden"


def test_i18n_toast_keys_active_in_parity():
    import json

    def flat(d, pre=""):
        out = {}
        for k, v in d.items():
            kk = f"{pre}.{k}" if pre else k
            out.update(flat(v, kk)) if isinstance(v, dict) else out.update({kk: v})
        return out

    sizes = set()
    for lang in ("de", "en", "fr"):
        data = flat(json.loads((ROOT / "locales" / f"{lang}.json").read_text("utf-8")))
        # Titel-Keys sind durch das Toast-System wieder aktiv:
        assert "cockpit.hide_tab_title" in data
        assert "settings.data_dir_migrate_done_title" in data
        assert "cockpit.keep_one_tab" in data
        assert "settings.data_dir_migrate_done_msg" in data
        sizes.add(len(data))
    assert len(sizes) == 1  # Paritaet de = en = fr


# ── 4. Audit-Tool ───────────────────────────────────────────────────────
def test_final_release_audit_tool_shape():
    tool = ROOT / "tools" / "final_release_audit_1000.py"
    assert tool.exists()
    src = tool.read_text(encoding="utf-8")
    for dom in (
        "d1_sql_surface",
        "d2_privacy_sanitize",
        "d3_file_permissions",
        "d4_money_format",
        "d5_due_clamp",
        "d6_migration_idempotent",
        "d7_bundle_tamper",
        "d8_i18n_format_safety",
        "d9_modal_info_load",
        "d10_taborder_decl",
    ):
        assert dom in src
    assert "FINAL_RELEASE_AUDIT_1000_MATRIX_v" in src
    assert "LOOPS_PER_DOMAIN = 100" in src


def test_audit_csv_matrix_present_for_current_version():
    from app_info import APP_VERSION

    csv_path = (
        ROOT
        / "docs/archive/release-evidence"
        / (f"FINAL_RELEASE_AUDIT_1000_MATRIX_v{APP_VERSION.replace('.', '_')}.csv")
    )
    assert csv_path.exists(), csv_path.name


# ── 5. Version ──────────────────────────────────────────────────────────
def test_app_version_is_semver():
    from app_info import APP_VERSION

    assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)


def test_version_json_in_sync():
    import json
    from app_info import APP_VERSION

    data = json.loads((ROOT / "version.json").read_text("utf-8"))
    assert data.get("version") == APP_VERSION


def test_readme_version_examples_updated():
    from app_info import APP_VERSION

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert APP_VERSION in readme
    assert not re.search(r"\b2\.2\.24\b", readme)


def test_release_evidence_index_is_current():
    """Der Archivindex muss das Verzeichnis nennen, nicht die Haelfte davon.

    Von Hand gepflegt driftete er auf 59 von 129 Dateien. Wer eine Datei nicht
    im Index findet, haelt sie fuer nicht vorhanden.
    """
    import subprocess

    fertig = subprocess.run(
        [sys.executable, "tools/release_evidence_index.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    assert fertig.returncode == 0, fertig.stderr


def test_project_root_holds_no_release_evidence():
    """Im Hauptordner liegt kein Auditnachweis mehr.

    Er wuchs um eine Datei je Fassung: fuenfzehn Auditmatrizen von 2.2.60 bis
    2.2.73 lagen dort nebeneinander.
    """
    muster = (
        "FINAL_RELEASE_AUDIT_",
        "ENTERPRISE_RELEASE_AUDIT_",
        "RELEASE_READINESS_",
        "SOURCE_TREE_SHA256_",
        "KILLCRITIC_X10THINK_",
        "UI_USABILITY_ADHS_",
    )
    gefunden = [
        p.name for p in ROOT.iterdir() if p.is_file() and p.name.startswith(muster)
    ]
    assert not gefunden, f"gehoert nach docs/archive/release-evidence: {gefunden}"
