import sqlite3
from datetime import datetime

from undoable.store.events import get_events, insert_event


def test_insert_and_get_roundtrip(conn: sqlite3.Connection) -> None:
    raw = {"hook_event_name": "PreToolUse", "session_id": "s1", "tool_name": "Bash"}
    event_id = insert_event(
        conn,
        session_id="s1",
        hook_event="PreToolUse",
        raw_payload=raw,
        tool_name="Bash",
        tool_input={"command": "ls -la"},
        cwd="/work",
        transcript_path="/tmp/transcript.jsonl",
    )

    [event] = get_events(conn, session_id="s1")
    assert event.id == event_id
    assert event.session_id == "s1"
    assert event.hook_event == "PreToolUse"
    assert event.tool_name == "Bash"
    assert event.tool_input == {"command": "ls -la"}
    assert event.tool_response is None
    assert event.decision is None
    assert event.cwd == "/work"
    assert event.transcript_path == "/tmp/transcript.jsonl"
    assert event.raw_payload == raw


def test_raw_payload_preserved_exactly_including_unicode_and_nesting(
    conn: sqlite3.Connection,
) -> None:
    raw = {
        "hook_event_name": "PostToolUse",
        "session_id": "s1",
        "nested": {"list": [1, 2, {"k": "v"}]},
        "unicode": "café ✅",
    }
    insert_event(conn, session_id="s1", hook_event="PostToolUse", raw_payload=raw)

    [event] = get_events(conn, session_id="s1")
    assert event.raw_payload == raw


def test_session_level_hooks_have_no_tool_fields(conn: sqlite3.Connection) -> None:
    raw = {"hook_event_name": "SessionStart", "session_id": "s2", "source": "startup"}
    insert_event(conn, session_id="s2", hook_event="SessionStart", raw_payload=raw)

    [event] = get_events(conn, session_id="s2")
    assert event.tool_name is None
    assert event.tool_input is None
    assert event.tool_response is None


def test_get_events_filters_by_session_id(conn: sqlite3.Connection) -> None:
    insert_event(conn, session_id="a", hook_event="SessionStart", raw_payload={})
    insert_event(conn, session_id="b", hook_event="SessionStart", raw_payload={})

    assert [e.session_id for e in get_events(conn, session_id="a")] == ["a"]


def test_get_events_filters_by_hook_event(conn: sqlite3.Connection) -> None:
    insert_event(conn, session_id="a", hook_event="PreToolUse", raw_payload={})
    insert_event(conn, session_id="a", hook_event="PostToolUse", raw_payload={})

    assert [e.hook_event for e in get_events(conn, hook_event="PostToolUse")] == ["PostToolUse"]


def test_get_events_orders_oldest_first(conn: sqlite3.Connection) -> None:
    first = insert_event(conn, session_id="a", hook_event="SessionStart", raw_payload={})
    second = insert_event(conn, session_id="a", hook_event="Stop", raw_payload={})

    ids = [e.id for e in get_events(conn, session_id="a")]
    assert ids == [first, second]


def test_logged_at_is_iso8601_utc(conn: sqlite3.Connection) -> None:
    insert_event(conn, session_id="a", hook_event="SessionStart", raw_payload={})

    [event] = get_events(conn, session_id="a")
    parsed = datetime.fromisoformat(event.logged_at)
    assert parsed.tzinfo is not None
    assert parsed.utcoffset().total_seconds() == 0
