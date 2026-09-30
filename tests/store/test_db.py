import sqlite3
from pathlib import Path

from undoable.store.db import DEFAULT_DB_DIR, DEFAULT_DB_NAME, connect, default_db_path


def test_default_db_path_is_per_project_dot_undoable() -> None:
    assert default_db_path("/some/project") == Path("/some/project") / ".undoable" / "undoable.db"
    assert DEFAULT_DB_DIR == ".undoable"
    assert DEFAULT_DB_NAME == "undoable.db"


def test_connect_creates_missing_parent_directories(db_path: Path) -> None:
    assert not db_path.parent.exists()
    connect(db_path).close()
    assert db_path.exists()


def test_connect_creates_events_table_with_expected_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(events)")}
    assert columns == {
        "id",
        "session_id",
        "hook_event",
        "tool_name",
        "tool_input",
        "tool_response",
        "decision",
        "risk_tier",
        "reason",
        "cwd",
        "transcript_path",
        "raw_payload",
        "logged_at",
    }


def test_connect_creates_snapshots_table_with_expected_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(snapshots)")}
    assert columns == {"id", "label", "commit_sha", "tree_sha", "parent_sha", "created_at"}


def test_connect_enables_wal_mode(conn: sqlite3.Connection) -> None:
    mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    assert mode.lower() == "wal"


def test_connect_is_idempotent(db_path: Path) -> None:
    connect(db_path).close()
    second = connect(db_path)
    tables = {row["name"] for row in second.execute("SELECT name FROM sqlite_master")}
    second.close()
    assert "events" in tables
