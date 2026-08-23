from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


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
        zf.writestr("BudgetManager-v2.0.9-portable/_internal/lib.so", "lib")

    import hashlib

    expected_sha = hashlib.sha256(source_zip.read_bytes()).hexdigest()

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
                    sha256=expected_sha,
                    asset_type="portable-zip",
                )
            },
        ),
    )
    monkeypatch.setattr(
        check_update, "cache_zip_path", lambda remote: tmp_path / f"update_{remote}.zip"
    )
    monkeypatch.setattr(
        check_update,
        "download_file",
        lambda url, dest: dest.write_bytes(source_zip.read_bytes()),
    )
    monkeypatch.setattr(
        check_update, "staging_dir_for", lambda remote: tmp_path / "staging" / remote
    )
    monkeypatch.setattr(
        check_update,
        "write_staged_marker",
        lambda remote, manifest, asset, *, tree_sha256="": (
            tmp_path / "staging" / remote / "_update_marker.json"
        ).write_text(json.dumps({"tree_sha256": tree_sha256}), encoding="utf-8"),
    )
    monkeypatch.setattr(
        check_update, "write_check_result", lambda data: writes.append(dict(data))
    )

    assert check_update.main() == 0
    assert (
        writes
    ), "GUI braucht ein strukturiertes Erfolgsergebnis nach erfolgreichem Staging"
    assert writes[-1]["available"] is True
    assert writes[-1]["staged"] is True
    assert writes[-1]["remote"] == "2.0.9"


def test_apply_uses_checked_version_not_highest_stale_staging(monkeypatch, tmp_path):
    """apply_update muss die von check_update gestagte Version anwenden,
    nicht blind die höchste vorhandene Staging-Version.

    Reproduziert den Fall: ein alter, höher nummerierter Staging-Ordner
    (z.B. Beta 2.1.0) liegt herum, während Stable gerade 2.0.9 vorbereitet hat.
    """
    import updater.apply_update as apply_update
    import updater.common as common

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
    common.write_check_result(
        {
            "available": True,
            "staged": True,
            "current": "2.0.8",
            "remote": "2.0.9",
            "staged_version": "2.0.9",
        }
    )

    assert (
        apply_update.target_staged_version() == "2.0.9"
    ), "apply muss die gestagete 2.0.9 nehmen, nicht die stale 2.1.0"

    # Ohne Prüfergebnis: sicherer Fallback auf höchste vorhandene Version
    common.clear_check_result()
    assert apply_update.target_staged_version() == "2.1.0"

    # Bevorzugte Version ohne Inhalt → Fallback auf höchste vorhandene
    common.write_check_result(
        {
            "available": True,
            "staged": True,
            "remote": "2.0.5",
            "staged_version": "2.0.5",
        }
    )
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


def test_release_ignore_rules_cover_runtime_caches_and_audit_artifacts():
    ignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    assert ".pytest_cache/" in ignore
    assert "__pycache__/" in ignore
    assert "*.py[cod]" in ignore
    assert "data/i18n_audit_report.txt" in ignore
    assert "data/backups/" in ignore
    assert "*.bmr" in ignore


def test_release_tree_contains_no_stale_runtime_audit_artifacts():
    assert not (ROOT / "data" / "i18n_audit_report.txt").exists()


def test_release_cleaner_removes_generated_artifacts_from_source_tree():
    cleaner = (ROOT / "tools" / "clean_release_tree.py").read_text(encoding="utf-8")
    assert "data/backups/*.bmr" in cleaner
    assert "__pycache__" in cleaner
    assert ".pytest_cache" in cleaner
    assert "installer_output" in cleaner


def test_frozen_update_dialog_passes_real_updater_flags():
    src = (ROOT / "views" / "update_dialog.py").read_text(encoding="utf-8")
    assert 'return [sys.executable, "--check-update"]' in src
    assert 'return [sys.executable, "--apply-update"]' in src
    assert '_entrypoint_cmd("updater.check_update") + ["--gui"]' in src


def test_portable_release_zip_uses_stable_launch_names():
    builder = (ROOT / "tools" / "build_release_assets.py").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "build.yml").read_text(
        encoding="utf-8"
    )
    assert "work / WINDOWS_CANONICAL_EXE" in builder
    assert "work / LINUX_CANONICAL_BINARY" in builder
    assert "portable-${platform}" not in workflow
    assert "BudgetManager-v${VERSION}-portable.zip" not in workflow
    assert "BudgetManager-v{version}-portable-windows.zip" in builder
    assert "BudgetManager-v{version}-portable-linux.zip" in builder
    assert "start" in builder and "%DIR%{WINDOWS_CANONICAL_EXE}" in builder
    assert "exec" in builder and "$DIR/{LINUX_CANONICAL_BINARY}" in builder


def test_update_apply_migrates_versioned_portable_binary_to_stable_name(
    monkeypatch, tmp_path
):
    import updater.apply_update as apply_update

    (tmp_path / "BudgetManager").write_text("new", encoding="utf-8")
    monkeypatch.setattr(
        apply_update, "current_exe_filename", lambda: "BudgetManager-v2.0.26-linux"
    )
    monkeypatch.setattr(apply_update, "stable_exe_filename", lambda: "BudgetManager")
    monkeypatch.setattr(
        apply_update, "update_target_exe_filename", lambda: "BudgetManager"
    )

    assert apply_update._staged_target_binary(tmp_path) == tmp_path / "BudgetManager"
    assert apply_update._launch_exe_filename(tmp_path) == "BudgetManager"


def test_active_release_docs_are_version_synced():
    import app_info

    version = app_info.APP_VERSION
    active_docs = [
        ROOT / "README.md",
        ROOT / "README_INSTALLATION.md",
        ROOT / "FEATURES.md",
        ROOT / "docs" / "help" / "README.md",
        ROOT / "docs" / "help" / "index.html",
        ROOT / "docs" / "release-checklist.md",
        ROOT / "docs" / "package-overview.md",
        ROOT / "docs" / "features.md",
    ]
    for path in active_docs:
        text = path.read_text(encoding="utf-8")
        assert version in text, f"{path} enthält nicht die aktuelle Version {version}"
        assert "2.0.25" not in text, f"{path} enthält noch v2.0.25"
        assert "2.0.18" not in text, f"{path} enthält noch v2.0.18"


def test_new_release_i18n_keys_exist_in_all_languages():
    required = {
        "budget_entry.msg.category_missing_create",
        "savings.msg.complete_confirm",
        "tags.msg.delete_used_confirm",
        "theme.msg.delete_confirm",
        "account.msg.delete_user_confirm",
        "tracking.msg.savings_negative_prompt",
        "backup_restore.msg.restore_restart_prompt",
        "backup.legacy_integrity_title",
        "backup.legacy_integrity_text",
        "setup.excel_import_running",
        "about.html",
        "db.info.current",
    }

    def flatten(obj, prefix=""):
        out = {}
        for key, value in obj.items():
            full = f"{prefix}.{key}" if prefix else str(key)
            if isinstance(value, dict):
                out.update(flatten(value, full))
            else:
                out[full] = value
        return out

    for lang in ("de", "en", "fr"):
        data = json.loads(
            (ROOT / "locales" / f"{lang}.json").read_text(encoding="utf-8")
        )
        flat = flatten(data)
        missing = required - set(flat)
        assert not missing, f"{lang}.json missing: {sorted(missing)}"


def test_budget_footer_is_translated_not_visible_total_literal():
    src = (ROOT / "views" / "tabs" / "budget_tab.py").read_text(encoding="utf-8")
    assert 'QTableWidgetItem("TOTAL")' not in src
    assert 'QTableWidgetItem(tr("header.total"))' in src
    assert "ROLE_ROW_KIND" in src
    assert '"footer"' in src


def test_windows_installer_pages_are_de_en_fr_localised():
    iss = (ROOT / "installer" / "budgetmanager_setup.iss").read_text(encoding="utf-8")
    assert 'Name: "french"; MessagesFile: "compiler:Languages\\French.isl"' in iss
    for lang in ("german", "english", "french"):
        for key in (
            "DataDirTitle",
            "DataDirSubtitle",
            "PrefsTitle",
            "PrefsSubtitle",
            "LanguageLabel",
            "CurrencyLabel",
            "CurrencyCHF",
            "PreferredDayLabel",
            "PreferredDayNone",
            "PreferredDayEndOfMonth",
        ):
            assert f"{lang}.{key}=" in iss
    assert "CustomMessage('DataDirTitle')" in iss
    assert "CustomMessage('PrefsTitle')" in iss
    assert "else if ActiveLanguage = 'french'" in iss


def test_user_guides_exist_in_de_en_fr_and_explain_charts_forecast_updater():
    required_terms = {
        "de": ["Forecast", "Diagramme erklärt", "Updates", "Fixkosten"],
        "en": ["Forecast", "Chart guide", "Updates", "Fixed cost"],
        "fr": [
            "Prévisions",
            "Explication des graphiques",
            "Mises à jour",
            "Charge fixe",
        ],
    }
    for lang, terms in required_terms.items():
        path = ROOT / "docs" / f"USER_GUIDE.{lang}.md"
        assert path.exists()
        text = path.read_text(encoding="utf-8")
        import app_info

        assert app_info.APP_VERSION in text
        for term in terms:
            assert term in text


def test_inno_pascal_comments_do_not_contain_nested_braces():
    """Inno Pascal comments use braces; constants like {app} inside them break compilation."""
    script = (ROOT / "installer" / "budgetmanager_setup.iss").read_text(
        encoding="utf-8"
    )
    in_code = False
    for lineno, line in enumerate(script.splitlines(), start=1):
        stripped = line.strip()
        if stripped.lower() == "[code]":
            in_code = True
            continue
        if in_code and stripped.startswith("[") and stripped.endswith("]"):
            in_code = False
        if not in_code:
            continue
        first = line.find("{")
        if first == -1:
            continue
        closing = line.find("}", first + 1)
        if closing == -1:
            continue
        nested = line.find("{", first + 1, closing)
        assert (
            nested == -1
        ), f"Nested '{{' in Inno Pascal comment at line {lineno}: {line}"


def test_startup_update_check_writes_lightweight_available_result(monkeypatch):
    import updater.startup_check as startup_check
    from updater.common import AssetInfo, Manifest

    writes = []
    monkeypatch.setattr(startup_check, "read_current_version", lambda: "2.0.8")
    monkeypatch.setattr(startup_check, "detect_platform_key", lambda: "windows")
    monkeypatch.setattr(
        startup_check,
        "preferred_asset_keys",
        lambda platform: ["windows_installer", "windows"],
    )
    monkeypatch.setattr(startup_check, "clear_startup_check_result", lambda: None)
    monkeypatch.setattr(
        startup_check,
        "fetch_manifest",
        lambda *_args, **_kwargs: Manifest(
            version="2.0.9",
            release_tag="v2.0.9",
            channel="stable",
            assets={
                "windows_installer": AssetInfo(
                    url="https://example.invalid/BudgetManager_Setup_2.0.9.exe",
                    sha256="",
                    asset_type="installer",
                )
            },
        ),
    )
    monkeypatch.setattr(
        startup_check,
        "write_startup_check_result",
        lambda data: writes.append(dict(data)),
    )

    assert startup_check.main() == 0
    assert writes, "Startup-Check muss ein strukturiertes Ergebnis schreiben"
    assert writes[-1]["available"] is True
    assert writes[-1]["downloaded"] is False
    assert writes[-1]["staged"] is False
    assert writes[-1]["remote"] == "2.0.9"
    assert writes[-1]["asset_key"] == "windows_installer"


def test_startup_update_check_is_registered_and_non_blocking():
    main_src = (ROOT / "main.py").read_text(encoding="utf-8")
    mw_src = (ROOT / "views" / "main_window_update.py").read_text(encoding="utf-8")
    startup_src = (ROOT / "updater" / "startup_check.py").read_text(encoding="utf-8")
    common_src = (ROOT / "updater" / "common.py").read_text(encoding="utf-8")

    assert '"--startup-update-check"' in main_src
    assert "schedule_startup_update_check" in main_src
    assert "schedule_startup_update_check" in mw_src
    assert "QProcess" in mw_src
    assert "last_startup_check.json" in common_src
    assert "download_file" not in startup_src
    assert "safe_extract_zip" not in startup_src
    assert "write_check_result" not in startup_src
    assert "write_startup_check_result" in startup_src


def test_release_package_contains_no_private_databases_or_keys():
    """Keine privaten Nutzerdateien im Release-Baum.

    Hinweis: Einige Tests/Migrationen erzeugen während eines Testlaufs temporäre
    pre-migration-Backups unter data/backups/. Diese werden vor dem finalen
    Packen gelöscht; der dauerhafte Schutz gegen Committen ist .gitignore.
    """
    data_dir = ROOT / "data"
    forbidden = []
    forbidden.extend(data_dir.glob("*.db"))
    forbidden.extend(data_dir.glob("*.sqlite"))
    forbidden.extend(data_dir.glob("*.sqlite3"))
    forbidden.extend(data_dir.glob("*.enc"))
    forbidden.extend(data_dir.glob("users.json"))
    (
        forbidden.extend((data_dir / "exports").glob("*"))
        if (data_dir / "exports").exists()
        else None
    )
    assert [str(p.relative_to(ROOT)) for p in forbidden] == []


def test_public_release_docs_and_updater_examples_are_current():
    import app_info

    version = app_info.APP_VERSION
    public_docs = [
        ROOT / "FEATURES.md",
        ROOT / "VERSION_INFO.txt",
        ROOT / "docs" / "open-tasks.md",
        ROOT / "docs" / "themes.md",
        ROOT / "docs" / "architecture.md",
        ROOT / "docs" / "DAU_TEST_ERSTSTART.md",
        ROOT / "docs" / "migration-guide.md",
        ROOT / "updater" / "README.md",
        ROOT / "updater" / "generate_manifest.py",
    ]
    stale_patterns = [
        "BudgetManager-v2.0.28-portable.zip",
        "BudgetManager-v2.0.32-portable.zip",
        "BudgetManager-v2.1.0-portable.zip",
        "BudgetManager_Setup_2.0.28.exe",
        "BudgetManager_Setup_2.0.32.exe",
        "Open Tasks — BudgetManager v2.0.32",
        "BudgetManager v2.0.32",
        "v2.0.32 · 19. Juni 2026",
        "## Neu in v2.0.36",
        "## v2.0.36 — Feature-Übersicht",
    ]
    for path in public_docs:
        text = path.read_text(encoding="utf-8")
        assert version in text, f"{path} enthält nicht {version}"
        for pattern in stale_patterns:
            assert pattern not in text, f"{path} enthält stale Pattern {pattern!r}"


def test_version_info_starts_with_current_release_notes():
    import app_info

    text = (ROOT / "VERSION_INFO.txt").read_text(encoding="utf-8")
    assert text.startswith(f"Budgetmanager Version {app_info.APP_VERSION}")
    first_body = text.split("\n\n", 2)[1]
    assert app_info.APP_VERSION in first_body
    # v2.2.0: Sentinel generalisiert (war release-spezifisch "BUDGET-VORSCHLAG").
    # Der erste Block muss ein GROSSBUCHSTABEN-Titel mit Trennlinie sein, der
    # die aktuelle Version trägt – so bleibt der Check bei jedem Release gültig.
    title_line = first_body.splitlines()[0]
    assert app_info.APP_VERSION in title_line
    assert (
        title_line == title_line.upper()
    ), "Release-Titel muss in Grossbuchstaben stehen"
    assert "----" in first_body, "Release-Titel braucht eine Trennlinie"
