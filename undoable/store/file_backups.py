import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True)
class FileBackupRecord:
    id: int
    kind: str  # "database" | "lockfile"
    original_path: str
    backup_path: str
    label: str | None
    created_at: str


def insert_file_backup(
    conn: sqlite3.Connection,
    *,
    kind: str,
    original_path: str,
    backup_path: str,
    label: str | None = None,
) -> int:
    """Record one file backup. Returns the new row's id."""
    created_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO file_backups (kind, original_path, backup_path, label, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (kind, original_path, backup_path, label, created_at),
    )
    conn.commit()
    return cursor.lastrowid


def _row_to_record(row: sqlite3.Row) -> FileBackupRecord:
    return FileBackupRecord(
        id=row["id"],
        kind=row["kind"],
        original_path=row["original_path"],
        backup_path=row["backup_path"],
        label=row["label"],
        created_at=row["created_at"],
    )


def get_file_backup(conn: sqlite3.Connection, backup_id: int) -> FileBackupRecord | None:
    row = conn.execute("SELECT * FROM file_backups WHERE id = ?", (backup_id,)).fetchone()
    return _row_to_record(row) if row is not None else None


def list_file_backups(conn: sqlite3.Connection, kind: str | None = None) -> list[FileBackupRecord]:
    """All backups, newest first, optionally filtered by kind."""
    if kind is not None:
        rows = conn.execute(
            "SELECT * FROM file_backups WHERE kind = ? ORDER BY id DESC", (kind,)
        ).fetchall()
    else:
        rows = conn.execute("SELECT * FROM file_backups ORDER BY id DESC").fetchall()
    return [_row_to_record(row) for row in rows]
