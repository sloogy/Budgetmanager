from pathlib import Path

import main


def test_single_instance_guard_blocks_alive_pid(tmp_path):
    lock_dir = tmp_path / "budgetmanager.instance.lock"

    first = main._SingleInstanceGuard(lock_dir)
    ok, reason = first.acquire()
    assert ok is True
    assert reason == ""

    second = main._SingleInstanceGuard(lock_dir)
    ok, reason = second.acquire()
    assert ok is False
    assert "läuft bereits" in reason

    first.release()
    assert not lock_dir.exists()


def test_single_instance_guard_recovers_stale_lock(tmp_path):
    lock_dir = tmp_path / "budgetmanager.instance.lock"
    lock_dir.mkdir()
    # PID 0/invalid wird als stale behandelt.
    (lock_dir / "pid").write_text("0", encoding="utf-8")

    guard = main._SingleInstanceGuard(lock_dir)
    ok, reason = guard.acquire()
    assert ok is True
    assert reason == ""
    assert (lock_dir / "pid").read_text(encoding="utf-8").strip().isdigit()

    guard.release()


def test_single_instance_guard_allows_other_apps_or_data_dirs(tmp_path):
    """Parallel laufende andere Apps dürfen nicht blockiert werden.

    Der Schutz ist absichtlich an den Lock-Pfad/Datenordner gebunden, nicht an
    den Prozessnamen ``python main.py``. Das schützt BudgetManager-Daten, ohne
    andere Python-Programme wie einen Füller-/Sammelmanager zu sperren.
    """
    budget_lock = tmp_path / "budgetmanager" / "data" / "budgetmanager.instance.lock"
    other_lock = tmp_path / "fpm" / "data" / "fpm.instance.lock"

    budget = main._SingleInstanceGuard(budget_lock, app_id="budgetmanager")
    other = main._SingleInstanceGuard(other_lock, app_id="fountainpen-manager")

    ok, reason = budget.acquire()
    assert ok is True
    assert reason == ""

    ok, reason = other.acquire()
    assert ok is True
    assert reason == ""

    budget.release()
    other.release()
