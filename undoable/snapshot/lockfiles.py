from pathlib import Path

from undoable.snapshot.file_backup import backup_file
from undoable.store.file_backups import FileBackupRecord

LOCKFILE_NAMES = [
    "requirements.txt",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Pipfile.lock",
    "poetry.lock",
    "Cargo.lock",
    "go.sum",
]


def backup_lockfiles(project_dir: str | Path) -> list[FileBackupRecord]:
    """Back up every lockfile present at project_dir's root. Only the root
    is checked (not every nested package.json's lock siblings) -- matching
    the scope of the pip/npm detection this is triggered from."""
    project_dir = Path(project_dir)
    records = []
    for name in LOCKFILE_NAMES:
        path = project_dir / name
        if path.is_file():
            records.append(backup_file(project_dir, path, kind="lockfile"))
    return records
