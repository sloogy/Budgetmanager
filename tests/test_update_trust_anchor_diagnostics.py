from __future__ import annotations


def test_missing_trust_anchor_is_reported_as_security_error(monkeypatch, capsys):
    import updater.check_update as check_update
    from updater.manifest_signing import ManifestSignatureError

    writes = []
    monkeypatch.setattr(check_update, "read_current_version", lambda: "2.2.61")
    monkeypatch.setattr(
        check_update,
        "fetch_manifest",
        lambda *_a, **_k: (_ for _ in ()).throw(
            ManifestSignatureError(
                "Kein eingebetteter Update-Public-Key gefunden; Update wird abgelehnt"
            )
        ),
    )
    monkeypatch.setattr(
        check_update, "write_check_result", lambda data: writes.append(dict(data))
    )

    assert check_update.main() == 2
    out = capsys.readouterr().out
    assert "Update-Sicherheitsprüfung fehlgeschlagen" in out
    assert "Manifest nicht erreichbar" not in out
    assert "einmalig" in out.lower()
    assert writes[-1]["error_type"] == "manifest_signature"


def test_network_manifest_failure_stays_separate(monkeypatch, capsys):
    import updater.check_update as check_update

    writes = []
    monkeypatch.setattr(check_update, "read_current_version", lambda: "2.2.61")
    monkeypatch.setattr(
        check_update,
        "fetch_manifest",
        lambda *_a, **_k: (_ for _ in ()).throw(ConnectionError("offline")),
    )
    monkeypatch.setattr(
        check_update, "write_check_result", lambda data: writes.append(dict(data))
    )

    assert check_update.main() == 2
    out = capsys.readouterr().out
    assert "Update-Manifest konnte nicht geladen werden" in out
    assert writes[-1]["error_type"] == "manifest_fetch"
