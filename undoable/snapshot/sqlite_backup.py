import shlex
from pathlib import Path

from undoable.snapshot.file_backup import backup_file
from undoable.store.file_backups import FileBackupRecord

# Standalone shell-operator tokens. shlex.split respects quoting, so a ";"
# inside a quoted SQL string ("DROP TABLE x;") stays merged into that
# token and is never mistaken for one of these -- unlike a naive regex
# split on the raw command string, which cuts a quoted "...;" in half.
_SHELL_OPERATORS = {"&&", "||", ";", "|"}


def extract_sqlite_targets(command: str) -> list[str]:
    """Database file path argument of each `sqlite3 ...` invocation in the
    command. Only the first non-flag token after `sqlite3` is treated as
    the database path, matching typical CLI usage -- a flag that itself
    takes a value (e.g. `-cmd "..."`) can be misread as the database path,
    a known limit in the same category as the firewall's rule set.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []

    targets = []
    i = 0
    while i < len(tokens):
        if tokens[i] != "sqlite3":
            i += 1
            continue
        i += 1
        found_target = False
        while i < len(tokens) and tokens[i] not in _SHELL_OPERATORS:
            tok = tokens[i]
            if not found_target:
                if tok.startswith("-"):
                    i += 1
                    continue
                if tok != ":memory:":
                    targets.append(tok)
                found_target = True
            i += 1
    return targets


def backup_sqlite_databases_for_command(
    project_dir: str | Path, command: str
) -> list[FileBackupRecord]:
    """Back up every existing SQLite database file a `sqlite3` invocation in
    this command targets. A target that doesn't exist yet is skipped --
    e.g. a fresh `sqlite3 new.db` that's about to create it has nothing to
    back up."""
    project_dir = Path(project_dir)
    records = []
    for target in extract_sqlite_targets(command):
        path = Path(target)
        if not path.is_absolute():
            path = project_dir / path
        if path.is_file():
            records.append(backup_file(project_dir, path, kind="database"))
    return records
