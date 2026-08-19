"""Isolierter End-to-End-Selbsttest des portablen Updaters."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path


def run_updater_self_test() -> int:
    """Prüft Staging, Integrität, Rollback-Backup, Austausch und Datenerhalt.

    Der Test arbeitet ausschliesslich in einem temporären Verzeichnis. Weder die
    laufende Installation noch echte Nutzerdaten werden verändert.
    """

    result: dict[str, object] = {"ok": False, "mode": "portable-sandbox"}
    try:
        from updater import apply_update, common

        with tempfile.TemporaryDirectory(prefix="budgetmanager-updater-e2e-") as tmp:
            app_root = Path(tmp) / "app"
            app_root.mkdir(parents=True)
            (app_root / "main.py").write_text("OLD_MAIN\n", encoding="utf-8")
            (app_root / "app_info.py").write_text("OLD_INFO\n", encoding="utf-8")
            data_file = app_root / "data" / "user-data.keep"
            data_file.parent.mkdir(parents=True)
            data_file.write_text("KEEP_ME\n", encoding="utf-8")

            version = "9.9.9-selftest"
            updates = app_root / "updates"
            staging = updates / "staging" / version
            payload = staging / "BudgetManager-update"
            payload.mkdir(parents=True)
            (payload / "main.py").write_text("NEW_MAIN\n", encoding="utf-8")
            (payload / "app_info.py").write_text("NEW_INFO\n", encoding="utf-8")
            (payload / "feature.txt").write_text("NEW_FEATURE\n", encoding="utf-8")

            marker = {
                "version": version,
                "asset_type": "portable",
                "download_url": "self-test://local",
                "tree_sha256": common.staged_tree_sha256(payload),
            }
            (staging / "_update_marker.json").write_text(
                json.dumps(marker, indent=2), encoding="utf-8"
            )
            updates.mkdir(parents=True, exist_ok=True)
            (updates / "last_check.json").write_text(
                json.dumps({"staged_version": version}), encoding="utf-8"
            )

            original_common_app_dir = common.app_dir
            original_apply_app_dir = apply_update.app_dir
            original_is_windows = apply_update.is_windows
            previous_no_restart = os.environ.get("BM_UPDATER_NO_RESTART")
            try:
                common.app_dir = lambda: app_root
                apply_update.app_dir = lambda: app_root
                apply_update.is_windows = lambda: False
                os.environ["BM_UPDATER_NO_RESTART"] = "1"
                return_code = apply_update.main()
            finally:
                common.app_dir = original_common_app_dir
                apply_update.app_dir = original_apply_app_dir
                apply_update.is_windows = original_is_windows
                if previous_no_restart is None:
                    os.environ.pop("BM_UPDATER_NO_RESTART", None)
                else:
                    os.environ["BM_UPDATER_NO_RESTART"] = previous_no_restart

            backups = list((updates / "backup").glob("pre_update_*.zip"))
            checks = {
                "return_code": return_code == 0,
                "main_replaced": (app_root / "main.py").read_text(encoding="utf-8")
                == "NEW_MAIN\n",
                "feature_installed": (app_root / "feature.txt").is_file(),
                "user_data_preserved": data_file.read_text(encoding="utf-8")
                == "KEEP_ME\n",
                "rollback_backup_created": len(backups) == 1,
                "top_level_payload_resolved": common.find_staged_root(staging)
                == payload,
            }
            if not all(checks.values()):
                failed = [name for name, passed in checks.items() if not passed]
                raise RuntimeError(
                    "Updater-Selbsttest fehlgeschlagen: " + ", ".join(failed)
                )

            result.update(
                {
                    "ok": True,
                    "checks": checks,
                    "backup_count": len(backups),
                }
            )
            print(json.dumps(result, ensure_ascii=False, sort_keys=True))
            return 0
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 1
