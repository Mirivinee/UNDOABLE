import sqlite3

from undoable.store.file_backups import get_file_backup, insert_file_backup, list_file_backups


def test_insert_and_get_roundtrip(conn: sqlite3.Connection) -> None:
    backup_id = insert_file_backup(
        conn,
        kind="lockfile",
        original_path="/project/requirements.txt",
        backup_path=".undoable/backups/1_requirements.txt",
        label="before pip install",
    )

    record = get_file_backup(conn, backup_id)
    assert record.id == backup_id
    assert record.kind == "lockfile"
    assert record.original_path == "/project/requirements.txt"
    assert record.backup_path == ".undoable/backups/1_requirements.txt"
    assert record.label == "before pip install"
    assert record.created_at


def test_label_is_optional(conn: sqlite3.Connection) -> None:
    backup_id = insert_file_backup(
        conn, kind="database", original_path="db.sqlite", backup_path="backup.sqlite"
    )
    assert get_file_backup(conn, backup_id).label is None


def test_get_returns_none_when_missing(conn: sqlite3.Connection) -> None:
    assert get_file_backup(conn, 999) is None


def test_list_newest_first(conn: sqlite3.Connection) -> None:
    first = insert_file_backup(conn, kind="lockfile", original_path="a", backup_path="a.bak")
    second = insert_file_backup(conn, kind="lockfile", original_path="b", backup_path="b.bak")

    assert [r.id for r in list_file_backups(conn)] == [second, first]


def test_list_filters_by_kind(conn: sqlite3.Connection) -> None:
    insert_file_backup(conn, kind="lockfile", original_path="a", backup_path="a.bak")
    db_id = insert_file_backup(conn, kind="database", original_path="b", backup_path="b.bak")

    assert [r.id for r in list_file_backups(conn, kind="database")] == [db_id]
