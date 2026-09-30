import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class SnapshotRecord:
    id: int
    label: str | None
    commit_sha: str
    tree_sha: str
    parent_sha: str | None
    created_at: str


def insert_snapshot(
    conn: sqlite3.Connection,
    *,
    commit_sha: str,
    tree_sha: str,
    parent_sha: str | None = None,
    label: str | None = None,
) -> int:
    """Record one snapshot. Returns the new row's id."""
    created_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO snapshots (label, commit_sha, tree_sha, parent_sha, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (label, commit_sha, tree_sha, parent_sha, created_at),
    )
    conn.commit()
    return cursor.lastrowid


def _row_to_snapshot(row: sqlite3.Row) -> SnapshotRecord:
    return SnapshotRecord(
        id=row["id"],
        label=row["label"],
        commit_sha=row["commit_sha"],
        tree_sha=row["tree_sha"],
        parent_sha=row["parent_sha"],
        created_at=row["created_at"],
    )


def get_snapshot(conn: sqlite3.Connection, snapshot_id: int) -> SnapshotRecord | None:
    row = conn.execute("SELECT * FROM snapshots WHERE id = ?", (snapshot_id,)).fetchone()
    return _row_to_snapshot(row) if row is not None else None


def list_snapshots(conn: sqlite3.Connection) -> list[SnapshotRecord]:
    """All snapshots, newest first."""
    rows = conn.execute("SELECT * FROM snapshots ORDER BY id DESC").fetchall()
    return [_row_to_snapshot(row) for row in rows]
