from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_package_contains_no_user_databases_or_keys():
    data_dir = ROOT / "data"
    assert not (data_dir / "users.json").exists()
    assert list(data_dir.glob("*.enc")) == []


def test_version_files_are_synchronised():
    import app_info

    version = app_info.APP_VERSION
    # Die Versionsquelle ist app_info.py. Der Test darf nicht bei jedem
    # Release eine alte Versionsnummer hardcodieren.
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)

    version_json = json.loads((ROOT / "version.json").read_text(encoding="utf-8"))
    assert version_json["version"] == version

    for rel in ["latest.json.template", "docs/latest.json.template"]:
        data = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        assert data["version"] == version
        assert data["release_tag"] == f"v{version}"
        assert f"/v{version}/" in data["assets"]["windows"]["url"]

    iss = (ROOT / "installer" / "budgetmanager_setup.iss").read_text(encoding="utf-8")
    assert f'#define MyAppVersion "{version}"' in iss


def test_update_dialog_uses_structured_check_result_and_visible_windows_helper():
    dialog_src = (ROOT / "views" / "update_dialog.py").read_text(encoding="utf-8")
    common_src = (ROOT / "updater" / "common.py").read_text(encoding="utf-8")
    apply_src = (ROOT / "updater" / "apply_update.py").read_text(encoding="utf-8")

    assert "read_check_result" in dialog_src
    assert "last_check.json" in common_src
    assert "CREATE_NEW_CONSOLE" in apply_src
    assert "DETACHED_PROCESS |" not in apply_src



def test_update_check_writes_success_result_for_gui(monkeypatch, tmp_path):
    import zipfile

    import updater.check_update as check_update
    from updater.common import AssetInfo, Manifest

    source_zip = tmp_path / "asset.zip"
    with zipfile.ZipFile(source_zip, "w") as zf:
        zf.writestr("BudgetManager-v2.0.9-portable/BudgetManager", "binary")

    writes = []

    monkeypatch.setattr(check_update, "read_current_version", lambda: "2.0.8")
    monkeypatch.setattr(check_update, "detect_platform_key", lambda: "linux")
    monkeypatch.setattr(
        check_update,
        "fetch_manifest",
        lambda *_args, **_kwargs: Manifest(
            version="2.0.9",
            release_tag="v2.0.9",
            channel="stable",
            assets={
                "linux": AssetInfo(
                    url="https://example.invalid/BudgetManager-v2.0.9-portable.zip",
                    sha256="",
                    asset_type="portable-zip",
                )
            },
        ),
    )
    monkeypatch.setattr(check_update, "cache_zip_path", lambda remote: tmp_path / f"update_{remote}.zip")
    monkeypatch.setattr(check_update, "download_file", lambda url, dest: dest.write_bytes(source_zip.read_bytes()))
    monkeypatch.setattr(check_update, "staging_dir_for", lambda remote: tmp_path / "staging" / remote)
    monkeypatch.setattr(
        check_update,
        "write_staged_marker",
        lambda remote, manifest, asset: (tmp_path / "staging" / remote / "_update_marker.json").write_text("{}", encoding="utf-8"),
    )
    monkeypatch.setattr(check_update, "write_check_result", lambda data: writes.append(dict(data)))

    assert check_update.main() == 0
    assert writes, "GUI braucht ein strukturiertes Erfolgsergebnis nach erfolgreichem Staging"
    assert writes[-1]["available"] is True
    assert writes[-1]["staged"] is True
    assert writes[-1]["remote"] == "2.0.9"


def test_apply_uses_checked_version_not_highest_stale_staging(monkeypatch, tmp_path):
    """apply_update muss die von check_update gestagte Version anwenden,
    nicht blind die höchste vorhandene Staging-Version.

    Reproduziert den Fall: ein alter, höher nummerierter Staging-Ordner
    (z.B. Beta 2.1.0) liegt herum, während Stable gerade 2.0.9 vorbereitet hat.
    """
    import updater.common as common
    import updater.apply_update as apply_update

    updates = tmp_path / "updates"
    (updates / "staging").mkdir(parents=True, exist_ok=True)

    # updates_dir in beiden relevanten Namensräumen auf tmp umbiegen
    monkeypatch.setattr(common, "updates_dir", lambda: updates)
    monkeypatch.setattr(apply_update, "updates_dir", lambda: updates)

    for v in ("2.0.8", "2.0.9", "2.1.0"):
        d = updates / "staging" / v
        d.mkdir(parents=True, exist_ok=True)
        (d / "dummy.txt").write_text("x", encoding="utf-8")

    # check_update hat 2.0.9 gestaged und das Ergebnis geschrieben
    common.write_check_result({
        "available": True, "staged": True,
        "current": "2.0.8", "remote": "2.0.9", "staged_version": "2.0.9",
    })

    assert apply_update.target_staged_version() == "2.0.9", \
        "apply muss die gestagete 2.0.9 nehmen, nicht die stale 2.1.0"

    # Ohne Prüfergebnis: sicherer Fallback auf höchste vorhandene Version
    common.clear_check_result()
    assert apply_update.target_staged_version() == "2.1.0"

    # Bevorzugte Version ohne Inhalt → Fallback auf höchste vorhandene
    common.write_check_result({"available": True, "staged": True,
                               "remote": "2.0.5", "staged_version": "2.0.5"})
    assert apply_update.target_staged_version() == "2.1.0"


def test_setup_assistant_enter_hooks_referenced_by_steps_exist():
    """Regression: Der Erststart-Assistent darf nicht auf fehlende on_enter-Methoden verweisen."""
    src = (ROOT / "views" / "setup_assistant_dialog.py").read_text(encoding="utf-8")
    assert "def _enter_tracking_first" in src
    assert "on_enter=self._enter_tracking_first" in src


def test_budget_overview_drag_drop_can_move_child_back_to_root():
    """Regression: Drag&Drop aus einem Parent heraus muss möglich sein.

    In der Budgetübersicht gibt es nicht immer einen sichtbaren Typ-Header
    als Drop-Ziel. target_row < 0 steht für freie Tabellenfläche und muss
    als "Zur Hauptkategorie machen" behandelt werden.
    """
    src = (ROOT / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")
    assert "if target_row < 0 or target_row >= self.table.rowCount():" in src
    assert "new_parent_id = None" in src
    assert "def _make_category_root" in src
    assert "categories.make_root" in src
