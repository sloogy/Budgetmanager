import sqlite3

from model.crypto import (
    AutosaveConnection,
    coalesced_commits,
    suspend_after_commit_autosave,
)


def test_autosave_connection_notifies_after_commit():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))

    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value TEXT)")
    conn.commit()

    assert calls == ["commit"]


def test_autosave_connection_notifies_after_execute_commit():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))

    conn.execute("BEGIN")
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, value TEXT)")
    conn.execute("COMMIT")

    assert calls == ["execute_commit"]


def test_autosave_connection_suspends_and_coalesces():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))

    conn.suspend_after_commit()
    conn.commit()
    conn.commit()
    assert calls == []

    conn.resume_after_commit()
    assert calls == ["resume"]


def test_coalesced_commits_collapses_many_commits_to_one_save():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY, v TEXT)")
    conn.commit()  # Einzelaktion bleibt sofort persistent.

    with coalesced_commits(conn):
        for i in range(50):
            conn.execute("INSERT INTO t(v) VALUES (?)", (str(i),))
            conn.commit()

    assert calls == ["commit", "resume"]


def test_coalesced_commits_nested_yields_single_save():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")

    with coalesced_commits(conn):
        conn.commit()
        with coalesced_commits(conn):
            conn.commit()
            conn.commit()
        assert calls == []  # äußerer Block ist noch aktiv
        conn.commit()

    assert calls == ["resume"]


def test_coalesced_commits_is_noop_for_plain_connection():
    plain = sqlite3.connect(":memory:")
    plain.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")

    with coalesced_commits(plain):
        plain.execute("INSERT INTO t DEFAULT VALUES")
        plain.commit()

    assert plain.execute("SELECT COUNT(*) FROM t").fetchone()[0] == 1


def test_coalesced_commits_resumes_on_exception():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")

    try:
        with coalesced_commits(conn):
            conn.commit()
            raise RuntimeError("boom")
    except RuntimeError:
        pass

    assert conn._after_commit_suspended == 0
    assert calls == ["resume"]


def test_suspend_after_commit_autosave_alias_uses_coalescing():
    calls = []
    conn = sqlite3.connect(":memory:", factory=AutosaveConnection)
    conn.set_after_commit_callback(lambda reason: calls.append(reason))
    conn.execute("CREATE TABLE t(id INTEGER PRIMARY KEY)")

    with suspend_after_commit_autosave(conn):
        conn.commit()
        conn.commit()

    assert calls == ["resume"]
