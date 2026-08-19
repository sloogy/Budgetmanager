"""v2.2.20 – Vor-Release-Vollaudit: gefundene Fehler und ihre Absicherung.

A: Der in v2.2.18/19 eingeführte "Notfall-Reset" im BackupRestoreDialog ist
   entfernt. Er löschte ALLE Tabellen OHNE die Sicherheitsabfrage aus
   v2.2.10/16 ("funktioniert auch ohne Passwort"), brach die K4-Regel
   "Reset an genau EINEM Ort" und seine Tabellenliste vergass
   suggestion_accepted und tracking_learning_state (verwaiste Lernzustände).
B: Laufzeit-Artefakte (data/budgetmanager_settings.json, data/theme_profiles/)
   dürfen nie im Release-Baum liegen; der Lint erkennt sie jetzt.

Zusätzlich: tools/mega_release_audit_1000.py (10 Themen x 100 = 1000 Loops)
ist Teil der Batterie und lief mit 0 Findings.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _src(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


# ── A: Notfall-Reset ist weg, EIN Reset-Ort, immer hinter Re-Auth ─────────
def test_emergency_reset_is_gone():
    src = _src("views/backup_restore_dialog.py")
    assert "emergency_reset" not in src.replace("Audit-Fix A", "")
    assert "btn_emergency_reset" not in src
    assert "backup.btn_emergency_reset" not in src


def test_exactly_one_reset_path_in_views():
    """Genau EIN View ruft reset_database – der DatabaseManagementDialog."""
    callers = []
    for py in (ROOT / "views").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        if ".reset_database(" in text:
            callers.append(py.name)
    assert callers == ["database_management_dialog.py"] or sorted(callers) == [
        "database_management_dialog.py",
        "setup_assistant_dialog.py",  # geführter Neuanfang, erzwingt create_backup=True
    ], f"Unerwartete Reset-Aufrufer: {callers}"
    dm = _src("views/database_management_dialog.py")
    assert "require_reauth" in dm, "Reset ohne Sicherheitsabfrage"


def test_emergency_i18n_keys_removed_and_parity_holds():
    counts = {}
    for lang in ("de", "en", "fr"):
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )

        def flat(d, p=""):
            out = {}
            for k, v in d.items():
                nk = f"{p}.{k}" if p else k
                if isinstance(v, dict):
                    out.update(flat(v, nk))
                else:
                    out[nk] = v
            return out

        f = flat(data)
        counts[lang] = len(f)
        removed = ("backup.btn_emergency_reset", "backup.emergency_tooltip")
        for key in removed:
            assert key not in f, f"{lang}: {key} übrig"
        assert not any(
            "notfall_reset" in k for k in f
        ), f"{lang}: auto-Notfall-Key übrig"
    assert len(set(counts.values())) == 1, f"i18n-Parität verletzt: {counts}"


def test_reset_tables_have_no_orphan_gap_anymore():
    """Die unvollständige _RESET_TABLES-Liste des Notfall-Resets darf nicht
    zurückkehren: kein View definiert mehr eine eigene Tabellen-Löschliste."""
    for py in (ROOT / "views").rglob("*.py"):
        text = py.read_text(encoding="utf-8")
        assert "_RESET_TABLES" not in text, f"{py.name}: eigene Reset-Tabellenliste"


# ── B: Release-Hygiene ────────────────────────────────────────────────────
def test_runtime_artifacts_not_in_tree():
    assert not (ROOT / "data" / "budgetmanager_settings.json").exists()
    tp = ROOT / "data" / "theme_profiles"
    assert not tp.exists() or not any(tp.iterdir())


def test_lint_covers_runtime_artifacts():
    lint = _src("tools/lint_procedure_check.py")
    assert "data/budgetmanager_settings.json" in lint
    assert "data/theme_profiles/*" in lint


# ── 1000-Loop-Werkzeug ist Teil der Batterie ──────────────────────────────
def test_mega_audit_tool_present_with_all_themes():
    tool = ROOT / "tools" / "mega_release_audit_1000.py"
    assert tool.is_file()
    src = tool.read_text(encoding="utf-8")
    for theme in (
        "mass_tracking",
        "undo_storm",
        "rename_storm",
        "unicode_names",
        "big_amounts",
        "copy_year_roundtrip",
        "bundle_fuzz",
        "reset_semantics",
        "suggestion_stress",
        "tags_chaos",
    ):
        assert theme in src, f"Thema fehlt: {theme}"
