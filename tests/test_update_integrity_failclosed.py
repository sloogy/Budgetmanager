"""Sicherheits-Regression: Auto-Update ist fail-closed bei fehlender Integrität.

Härtung v2.0.36: Lädt der Update-Check ein Asset herunter, dessen Manifest
keinen SHA256 enthält, darf das Update NICHT installiert/gestaged werden.
Andernfalls könnte ein manipuliertes Manifest die Integritätsprüfung umgehen.

Ebenfalls geprüft: is_newer liefert bei nicht interpretierbaren Versionen
konservativ False (kein fälschlicher Update-Hinweis).
"""

from __future__ import annotations

import zipfile


def test_update_without_sha256_is_rejected(monkeypatch, tmp_path):
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
        lambda *_a, **_k: Manifest(
            version="2.0.9",
            release_tag="v2.0.9",
            channel="stable",
            assets={
                "linux": AssetInfo(
                    url="https://example.invalid/BudgetManager-v2.0.9-portable.zip",
                    sha256="",  # bewusst leer → muss abgelehnt werden
                    asset_type="portable-zip",
                )
            },
        ),
    )
    monkeypatch.setattr(
        check_update, "cache_zip_path", lambda remote: tmp_path / f"u_{remote}.zip"
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
        check_update, "write_check_result", lambda data: writes.append(dict(data))
    )

    rc = check_update.main()

    # Fail-closed: Rückgabecode != 0 und kein verfügbares/gestagtes Update.
    assert rc != 0, "Update ohne SHA256 darf nicht mit Erfolg enden"
    assert writes, "Es muss ein strukturiertes Ergebnis geschrieben werden"
    assert writes[-1]["available"] is False
    assert writes[-1].get("staged") is not True
    # Kein Staging-Verzeichnis angelegt
    assert not (tmp_path / "staging" / "2.0.9").exists()


def test_update_with_wrong_sha256_is_rejected(monkeypatch, tmp_path):
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
        lambda *_a, **_k: Manifest(
            version="2.0.9",
            release_tag="v2.0.9",
            channel="stable",
            assets={
                "linux": AssetInfo(
                    url="https://example.invalid/x.zip",
                    sha256="deadbeef" * 8,  # falscher Hash
                    asset_type="portable-zip",
                )
            },
        ),
    )
    monkeypatch.setattr(
        check_update, "cache_zip_path", lambda remote: tmp_path / f"u_{remote}.zip"
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
        check_update, "write_check_result", lambda data: writes.append(dict(data))
    )

    rc = check_update.main()
    assert rc != 0
    assert writes[-1]["available"] is False
    assert not (tmp_path / "staging" / "2.0.9").exists()


def test_is_newer_conservative_on_unparsable_version():
    from updater.common import is_newer

    # Korrekter SemVer-Vergleich
    assert is_newer("2.0.36", "2.0.35") is True
    assert is_newer("2.0.9", "2.0.10") is False  # nicht lexikografisch!
    assert is_newer("2.0.35", "2.0.35") is False
    # Unparsbar → konservativ kein Update
    assert is_newer("not-a-version", "2.0.35") is False
    assert is_newer("", "2.0.35") is False
