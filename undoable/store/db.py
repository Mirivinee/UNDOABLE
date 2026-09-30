import sqlite3
from pathlib import Path

DEFAULT_DB_DIR = ".undoable"
DEFAULT_DB_NAME = "undoable.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    hook_event TEXT NOT NULL,
    tool_name TEXT,
    tool_input TEXT,
    tool_response TEXT,
    decision TEXT,
    risk_tier TEXT,
    reason TEXT,
    cwd TEXT,
    transcript_path TEXT,
    raw_payload TEXT NOT NULL,
    logged_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_events_session_id ON events (session_id);
CREATE INDEX IF NOT EXISTS idx_events_hook_event ON events (hook_event);
CREATE INDEX IF NOT EXISTS idx_events_logged_at ON events (logged_at);

CREATE TABLE IF NOT EXISTS snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT,
    commit_sha TEXT NOT NULL,
    tree_sha TEXT NOT NULL,
    parent_sha TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_created_at ON snapshots (created_at);
"""


def default_db_path(project_dir: Path | str = ".") -> Path:
    """Per-project event log location: <project_dir>/.undoable/undoable.db."""
    return Path(project_dir) / DEFAULT_DB_DIR / DEFAULT_DB_NAME


def connect(db_path: Path | str) -> sqlite3.Connection:
    """Open (creating if needed) the event log and ensure its schema exists."""
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn
