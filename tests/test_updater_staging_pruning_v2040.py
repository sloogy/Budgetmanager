"""Regressionen v2.0.40 – Updater-Haertung.

Abgedeckt:
1. ``prune_other_staging`` entfernt veraltete Staging-Ordner, behaelt aber den
   aktuellen.
2. ``prune_other_staging`` entfernt nur eigene ``update_*``-Cache-Dateien und
   schont fremde Dateien.
3. ``check_update`` raeumt nach erfolgreichem Staging einen alten, hoeher
   nummerierten Staging-Ordner ab. Dadurch ist der sichere Fallback in
   ``apply_update`` (``latest_staged_version``) auch ohne ``last_check.json``
   korrekt – das war das Race, wenn der GUI-Dialog die Datei vor dem
   Apply-Prozess loescht.
4. Statischer Schutz: Der Update-Dialog darf ``last_check.json`` nicht mehr
   direkt nach dem Start des Apply-Prozesses loeschen.

Laeuft ohne Qt/PySide6 (reine Daten-/Dateischicht + Quelltextpruefung).
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def test_prune_other_staging_keeps_target_removes_siblings(tmp_path):
    from updater.common import prune_other_staging

    staging_root = tmp_path / "staging"
    keep = staging_root / "2.0.40"
    for v in ("2.0.38", "2.0.39", "2.0.40", "2.1.0"):
        d = staging_root / v
        d.mkdir(parents=True, exist_ok=True)
        (d / "dummy.txt").write_text("x", encoding="utf-8")

    prune_other_staging(keep)

    remaining = sorted(p.name for p in staging_root.iterdir() if p.is_dir())
    assert remaining == ["2.0.40"], f"nur die Zielversion darf bleiben: {remaining}"
    assert (keep / "dummy.txt").exists()


def test_prune_other_staging_cache_only_touches_own_artifacts(tmp_path):
    from updater.common import prune_other_staging

    staging_root = tmp_path / "staging"
    keep = staging_root / "2.0.40"
    keep.mkdir(parents=True, exist_ok=True)

    cache_root = tmp_path / "cache"
    cache_root.mkdir(parents=True, exist_ok=True)
    keep_zip = cache_root / "update_2.0.40.zip"
    keep_zip.write_bytes(b"keep")
    (cache_root / "update_2.0.39.zip").write_bytes(b"old")
    (cache_root / "update_2.1.0.exe").write_bytes(b"stale-beta")
    foreign = cache_root / "user_backup.zip"
    foreign.write_bytes(b"foreign")

    prune_other_staging(keep, keep_zip)

    names = sorted(p.name for p in cache_root.iterdir())
    assert "update_2.0.40.zip" in names, "aktuelle Cache-Datei muss bleiben"
    assert "update_2.0.39.zip" not in names
    assert "update_2.1.0.exe" not in names
    assert "user_backup.zip" in names, "fremde Dateien duerfen nicht geloescht werden"


def test_check_update_prunes_stale_higher_staging_so_fallback_is_safe(
    monkeypatch, tmp_path
):
    import hashlib
    import zipfile

    import updater.check_update as check_update
    import updater.common as common
    import updater.apply_update as apply_update
    from updater.common import AssetInfo, Manifest

    updates = tmp_path / "updates"
    staging_root = updates / "staging"
    cache_root = updates / "cache"
    staging_root.mkdir(parents=True, exist_ok=True)
    cache_root.mkdir(parents=True, exist_ok=True)

    # Alter, hoeher nummerierter Staging-Rest (Beta), der NICHT angewendet werden darf.
    stale = staging_root / "2.1.0"
    stale.mkdir(parents=True, exist_ok=True)
    (stale / "BudgetManager").write_text("old-beta", encoding="utf-8")

    source_zip = tmp_path / "asset.zip"
    with zipfile.ZipFile(source_zip, "w") as zf:
        zf.writestr("BudgetManager-v2.0.40-portable/BudgetManager", "binary")
    expected_sha = hashlib.sha256(source_zip.read_bytes()).hexdigest()

    monkeypatch.setattr(check_update, "read_current_version", lambda: "2.0.39")
    monkeypatch.setattr(check_update, "detect_platform_key", lambda: "linux")
    monkeypatch.setattr(
        check_update,
        "fetch_manifest",
        lambda *_a, **_k: Manifest(
            version="2.0.40",
            release_tag="v2.0.40",
            channel="stable",
            assets={
                "linux": AssetInfo(
                    url="https://example.invalid/BudgetManager-v2.0.40-portable.zip",
                    sha256=expected_sha,
                    asset_type="portable-zip",
                )
            },
        ),
    )
    monkeypatch.setattr(
        check_update,
        "cache_zip_path",
        lambda remote: cache_root / f"update_{remote}.zip",
    )
    monkeypatch.setattr(
        check_update,
        "download_file",
        lambda url, dest: dest.write_bytes(source_zip.read_bytes()),
    )
    monkeypatch.setattr(
        check_update, "staging_dir_for", lambda remote: staging_root / remote
    )

    # updates_dir in beiden Namensraeumen auf tmp biegen (fuer write_staged_marker
    # und apply_update.latest_staged_version).
    monkeypatch.setattr(common, "updates_dir", lambda: updates)
    monkeypatch.setattr(apply_update, "updates_dir", lambda: updates)
    monkeypatch.setattr(apply_update, "staging_dir_for", lambda v: staging_root / v)

    rc = check_update.main()
    assert rc == 0

    remaining = sorted(p.name for p in staging_root.iterdir() if p.is_dir())
    assert remaining == [
        "2.0.40"
    ], f"alter Beta-Staging-Ordner muss weg sein: {remaining}"

    # Race-Sicherheitsnetz: ohne last_check.json faellt apply auf die hoechste
    # vorhandene Staging-Version zurueck – die ist jetzt die gerade gepruefte.
    common.clear_check_result()
    assert apply_update.latest_staged_version() == "2.0.40"
    assert apply_update.target_staged_version() == "2.0.40"


def test_update_dialog_apply_does_not_clear_check_result_before_apply():
    """Statischer Schutz gegen Regression des Race-Fixes.

    ``_apply`` darf ``clear_check_result()`` nicht aufrufen, sonst loescht der
    sterbende GUI-Prozess ``last_check.json`` bevor der abgekoppelte
    apply_update-Prozess sie lesen kann.
    """
    src = (ROOT / "views" / "update_dialog.py").read_text(encoding="utf-8")
    marker = "def _apply(self)"
    idx = src.index(marker)
    apply_src = src[idx:]
    # bis zur naechsten Methodendefinition schneiden
    next_def = apply_src.find("\n    def ", len(marker))
    if next_def != -1:
        apply_src = apply_src[:next_def]
    assert (
        "clear_check_result()" not in apply_src
    ), "_apply darf last_check.json nicht loeschen (Race mit apply_update)"
