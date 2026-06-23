from __future__ import annotations

import os

from model import process_utils


def test_windows_pid_check_does_not_call_os_kill(monkeypatch) -> None:
    def _forbidden(*_args, **_kwargs):
        raise AssertionError("os.kill must not be used for Windows PID checks")

    monkeypatch.setattr(process_utils.os, "name", "nt", raising=False)
    monkeypatch.setattr(os, "kill", _forbidden)
    monkeypatch.setattr(process_utils, "_pid_alive_windows", lambda pid: True)

    assert process_utils.is_pid_alive(12345) is True


def test_posix_pid_check_still_uses_safe_signal_zero(monkeypatch) -> None:
    calls = []

    def _fake_kill(pid, sig):
        calls.append((pid, sig))

    monkeypatch.setattr(process_utils.os, "name", "posix", raising=False)
    monkeypatch.setattr(os, "kill", _fake_kill)

    assert process_utils.is_pid_alive(12345) is True
    assert calls == [(12345, 0)]
