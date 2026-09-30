import shutil
from pathlib import Path

from undoable.store.db import connect, default_db_path
from undoable.store.file_backups import (
    FileBackupRecord,
    get_file_backup,
    insert_file_backup,
    list_file_backups,
)

BACKUP_DIR = "backups"


class SourceNotFoundError(RuntimeError):
    """Raised when the file to back up doesn't exist."""


class BackupNotFoundError(RuntimeError):
    """Raised when a restore is requested for an unknown backup id."""


def backup_file(
    project_dir: str | Path, source_path: str | Path, kind: str, label: str | None = None
) -> FileBackupRecord:
    """Copy source_path's current bytes into .undoable/backups/ and record
    the backup. Returns the stored record.

    Raises SourceNotFoundError rather than silently skipping -- a caller
    asking to back up a file that turns out not to exist is a bug worth
    surfacing, not something to paper over.
    """
    project_dir = Path(project_dir)
    source_path = Path(source_path)
    if not source_path.is_file():
        raise SourceNotFoundError(f"{source_path} does not exist.")

    conn = connect(default_db_path(project_dir))
    try:
        # Reserve the id first so the on-disk backup filename can include it
        # and never collides with another backup of the same basename.
        backup_id = insert_file_backup(
            conn,
            kind=kind,
            original_path=str(source_path),
            backup_path="",
            label=label,
        )
        backup_rel = f"{BACKUP_DIR}/{backup_id}_{source_path.name}"
        backup_abs = project_dir / ".undoable" / backup_rel
        backup_abs.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, backup_abs)
        conn.execute(
            "UPDATE file_backups SET backup_path = ? WHERE id = ?", (backup_rel, backup_id)
        )
        conn.commit()
        return get_file_backup(conn, backup_id)
    finally:
        conn.close()


def restore_file(project_dir: str | Path, backup_id: int) -> Path:
    """Copy a backup's bytes back to its original path. Returns that path."""
    project_dir = Path(project_dir)
    conn = connect(default_db_path(project_dir))
    try:
        record = get_file_backup(conn, backup_id)
    finally:
        conn.close()
    if record is None:
        raise BackupNotFoundError(f"No file backup with id {backup_id}.")

    backup_abs = project_dir / ".undoable" / record.backup_path
    original = Path(record.original_path)
    original.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_abs, original)
    return original


def list_backups(project_dir: str | Path, kind: str | None = None) -> list[FileBackupRecord]:
    conn = connect(default_db_path(project_dir))
    try:
        return list_file_backups(conn, kind=kind)
    finally:
        conn.close()
