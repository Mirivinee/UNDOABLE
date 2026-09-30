import sqlite3

from undoable.killswitch.budget import check_budget
from undoable.store.events import insert_event


def _log(conn: sqlite3.Connection, session_id: str) -> None:
    insert_event(
        conn,
        session_id=session_id,
        hook_event="PreToolUse",
        raw_payload={},
        tool_name="Bash",
        tool_input={"command": "x"},
    )


def test_none_when_unlimited(conn: sqlite3.Connection) -> None:
    assert check_budget(conn, "s1", max_actions=None) is None


def test_under_budget_returns_none(conn: sqlite3.Connection) -> None:
    _log(conn, "s1")
    assert check_budget(conn, "s1", max_actions=5) is None


def test_at_budget_flags(conn: sqlite3.Connection) -> None:
    for _ in range(5):
        _log(conn, "s1")

    finding = check_budget(conn, "s1", max_actions=5)
    assert finding is not None
    assert finding.used == 5
    assert finding.limit == 5


def test_only_counts_the_same_session(conn: sqlite3.Connection) -> None:
    for _ in range(5):
        _log(conn, "other-session")

    assert check_budget(conn, "s1", max_actions=5) is None
