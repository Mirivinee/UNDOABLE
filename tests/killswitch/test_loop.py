import sqlite3

from undoable.killswitch.loop import detect_loop
from undoable.store.events import insert_event


def _log(conn: sqlite3.Connection, session_id: str, tool_name: str, tool_input: dict) -> None:
    insert_event(
        conn,
        session_id=session_id,
        hook_event="PreToolUse",
        raw_payload={},
        tool_name=tool_name,
        tool_input=tool_input,
    )


def test_no_loop_with_too_few_prior_calls(conn: sqlite3.Connection) -> None:
    _log(conn, "s1", "Bash", {"command": "ls"})
    assert detect_loop(conn, "s1", "Bash", {"command": "ls"}, threshold=3) is None


def test_detects_identical_repeats(conn: sqlite3.Connection) -> None:
    _log(conn, "s1", "Bash", {"command": "pytest"})
    _log(conn, "s1", "Bash", {"command": "pytest"})

    finding = detect_loop(conn, "s1", "Bash", {"command": "pytest"}, threshold=3)
    assert finding is not None
    assert finding.repeats == 3
    assert finding.tool_name == "Bash"


def test_no_loop_when_inputs_differ(conn: sqlite3.Connection) -> None:
    _log(conn, "s1", "Bash", {"command": "pytest"})
    _log(conn, "s1", "Bash", {"command": "pytest -k foo"})

    assert detect_loop(conn, "s1", "Bash", {"command": "pytest"}, threshold=3) is None


def test_only_considers_the_same_session(conn: sqlite3.Connection) -> None:
    _log(conn, "other-session", "Bash", {"command": "pytest"})
    _log(conn, "other-session", "Bash", {"command": "pytest"})

    assert detect_loop(conn, "s1", "Bash", {"command": "pytest"}, threshold=3) is None


def test_threshold_below_two_disables_check(conn: sqlite3.Connection) -> None:
    assert detect_loop(conn, "s1", "Bash", {"command": "pytest"}, threshold=1) is None


def test_streak_must_be_consecutive_and_recent(conn: sqlite3.Connection) -> None:
    _log(conn, "s1", "Bash", {"command": "pytest"})
    _log(conn, "s1", "Bash", {"command": "pytest"})
    _log(conn, "s1", "Bash", {"command": "ls"})  # breaks the streak

    assert detect_loop(conn, "s1", "Bash", {"command": "pytest"}, threshold=3) is None
