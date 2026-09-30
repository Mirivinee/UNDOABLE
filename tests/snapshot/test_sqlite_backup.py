from pathlib import Path

import pytest

from undoable.snapshot.sqlite_backup import (
    backup_sqlite_databases_for_command,
    extract_sqlite_targets,
)

EXTRACTION_CASES = [
    ('sqlite3 mydb.db "DROP TABLE users;"', ["mydb.db"]),
    ("sqlite3 -header -csv mydb.db", ["mydb.db"]),
    ('sqlite3 :memory: "SELECT 1;"', []),
    ("ls -la", []),
    ('echo hi && sqlite3 data/app.db "SELECT 1;"', ["data/app.db"]),
]


@pytest.mark.parametrize(("command", "expected"), EXTRACTION_CASES)
def test_extract_sqlite_targets(command: str, expected: list[str]) -> None:
    assert extract_sqlite_targets(command) == expected


def test_backs_up_existing_database(tmp_path: Path) -> None:
    db = tmp_path / "mydb.db"
    db.write_bytes(b"sqlite-bytes")

    records = backup_sqlite_databases_for_command(tmp_path, 'sqlite3 mydb.db "DROP TABLE x;"')
    assert len(records) == 1
    assert records[0].kind == "database"
    assert records[0].original_path == str(db)


def test_skips_nonexistent_database(tmp_path: Path) -> None:
    records = backup_sqlite_databases_for_command(tmp_path, 'sqlite3 new.db "CREATE TABLE x;"')
    assert records == []


def test_skips_in_memory_database(tmp_path: Path) -> None:
    records = backup_sqlite_databases_for_command(tmp_path, 'sqlite3 :memory: "SELECT 1;"')
    assert records == []


def test_resolves_relative_path_against_project_dir(tmp_path: Path) -> None:
    subdir = tmp_path / "data"
    subdir.mkdir()
    db = subdir / "app.db"
    db.write_bytes(b"x")

    records = backup_sqlite_databases_for_command(tmp_path, 'sqlite3 data/app.db "SELECT 1;"')
    assert len(records) == 1
    assert records[0].original_path == str(db)
