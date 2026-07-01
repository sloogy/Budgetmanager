from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# 1) Updater-Test: direct_windows_exe ist ab onedir bewusst nicht mehr erlaubt.
test_installer = ROOT / "tests" / "test_installer_icon_workflow.py"
text = test_installer.read_text(encoding="utf-8")

old = 'assert common.preferred_asset_keys("windows")[:3] == ["direct_windows_exe", "windows", "portable_zip"]'
new = (
    'assert common.preferred_asset_keys("windows")[:2] == ["windows", "portable_zip"]\n'
    '    assert "direct_windows_exe" not in common.preferred_asset_keys("windows")'
)

if old not in text:
    raise SystemExit("Erwartete direct_windows_exe-Testzeile nicht gefunden.")

text = text.replace(old, new)
test_installer.write_text(text, encoding="utf-8")


# 2) Release-Asset-Builder: stabile Startnamen weiterhin explizit prüfen.
builder_path = ROOT / "tools" / "build_release_assets.py"
builder = builder_path.read_text(encoding="utf-8")

old_win = '_copy_bundle_contents(windows_exe.parent, work)\n\n    (work / "data" / "backups").mkdir'
new_win = (
    "_copy_bundle_contents(windows_exe.parent, work)\n\n"
    "    target_exe = work / WINDOWS_CANONICAL_EXE\n"
    "    if not target_exe.is_file():\n"
    '        _die(f"Windows-Bundle ohne stabilen Startnamen: {target_exe}")\n\n'
    '    (work / "data" / "backups").mkdir'
)

old_linux = '_copy_bundle_contents(linux_binary.parent, work)\n\n    (work / "data" / "backups").mkdir'
new_linux = (
    "_copy_bundle_contents(linux_binary.parent, work)\n\n"
    "    target_binary = work / LINUX_CANONICAL_BINARY\n"
    "    if not target_binary.is_file():\n"
    '        _die(f"Linux-Bundle ohne stabilen Startnamen: {target_binary}")\n'
    "    try:\n"
    "        mode = os.stat(target_binary).st_mode\n"
    "        os.chmod(target_binary, mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)\n"
    "    except OSError:\n"
    "        pass\n\n"
    '    (work / "data" / "backups").mkdir'
)

if old_win not in builder:
    raise SystemExit("Windows-onedir-Stelle im Builder nicht gefunden.")
if old_linux not in builder:
    raise SystemExit("Linux-onedir-Stelle im Builder nicht gefunden.")

builder = builder.replace(old_win, new_win)
builder = builder.replace(old_linux, new_linux)
builder_path.write_text(builder, encoding="utf-8")

print("Onedir-Testguards angepasst.")
