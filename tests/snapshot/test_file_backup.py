from pathlib import Path

import pytest

from undoable.snapshot.file_backup import (
    BackupNotFoundError,
    SourceNotFoundError,
    backup_file,
    list_backups,
    restore_file,
)


def test_backup_file_copies_content(tmp_path: Path) -> None:
    source = tmp_path / "requirements.txt"
    source.write_text("requests==2.31.0\n")

    record = backup_file(tmp_path, source, kind="lockfile", label="before install")
    assert record.kind == "lockfile"
    assert record.original_path == str(source)
    assert record.label == "before install"

    backup_path = tmp_path / ".undoable" / record.backup_path
    assert backup_path.read_text() == "requests==2.31.0\n"


def test_backup_file_missing_source_raises(tmp_path: Path) -> None:
    with pytest.raises(SourceNotFoundError):
        backup_file(tmp_path, tmp_path / "does_not_exist.txt", kind="lockfile")


def test_restore_file_writes_back_original_content(tmp_path: Path) -> None:
    source = tmp_path / "db.sqlite"
    source.write_bytes(b"original-bytes")
    record = backup_file(tmp_path, source, kind="database")

    source.write_bytes(b"corrupted-by-agent")
    restored_path = restore_file(tmp_path, record.id)

    assert restored_path == source
    assert source.read_bytes() == b"original-bytes"


def test_restore_file_recreates_a_deleted_file(tmp_path: Path) -> None:
    source = tmp_path / "package-lock.json"
    source.write_text('{"lockfileVersion": 1}')
    record = backup_file(tmp_path, source, kind="lockfile")

    source.unlink()
    restore_file(tmp_path, record.id)

    assert source.read_text() == '{"lockfileVersion": 1}'


def test_restore_unknown_backup_raises(tmp_path: Path) -> None:
    with pytest.raises(BackupNotFoundError):
        restore_file(tmp_path, 999)


def test_backups_of_same_basename_do_not_collide(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    source_a = tmp_path / "a" / "requirements.txt"
    source_b = tmp_path / "b" / "requirements.txt"
    source_a.write_text("first")
    source_b.write_text("second")

    record_a = backup_file(tmp_path, source_a, kind="lockfile")
    record_b = backup_file(tmp_path, source_b, kind="lockfile")

    assert (tmp_path / ".undoable" / record_a.backup_path).read_text() == "first"
    assert (tmp_path / ".undoable" / record_b.backup_path).read_text() == "second"


def test_list_backups_filters_by_kind(tmp_path: Path) -> None:
    lockfile = tmp_path / "requirements.txt"
    lockfile.write_text("x")
    db = tmp_path / "db.sqlite"
    db.write_bytes(b"x")

    backup_file(tmp_path, lockfile, kind="lockfile")
    backup_file(tmp_path, db, kind="database")

    assert len(list_backups(tmp_path)) == 2
    assert len(list_backups(tmp_path, kind="lockfile")) == 1
    assert len(list_backups(tmp_path, kind="database")) == 1
