import sqlite3

from undoable.store.snapshots import get_snapshot, insert_snapshot, list_snapshots


def test_insert_and_get_roundtrip(conn: sqlite3.Connection) -> None:
    snapshot_id = insert_snapshot(
        conn,
        commit_sha="a" * 40,
        tree_sha="b" * 40,
        parent_sha="c" * 40,
        label="before rm -rf",
    )

    snapshot = get_snapshot(conn, snapshot_id)
    assert snapshot.id == snapshot_id
    assert snapshot.commit_sha == "a" * 40
    assert snapshot.tree_sha == "b" * 40
    assert snapshot.parent_sha == "c" * 40
    assert snapshot.label == "before rm -rf"
    assert snapshot.created_at


def test_parent_sha_and_label_are_optional(conn: sqlite3.Connection) -> None:
    snapshot_id = insert_snapshot(conn, commit_sha="a" * 40, tree_sha="b" * 40)

    snapshot = get_snapshot(conn, snapshot_id)
    assert snapshot.parent_sha is None
    assert snapshot.label is None


def test_get_snapshot_returns_none_when_missing(conn: sqlite3.Connection) -> None:
    assert get_snapshot(conn, 999) is None


def test_list_snapshots_newest_first(conn: sqlite3.Connection) -> None:
    first = insert_snapshot(conn, commit_sha="a" * 40, tree_sha="b" * 40)
    second = insert_snapshot(conn, commit_sha="c" * 40, tree_sha="d" * 40)

    ids = [s.id for s in list_snapshots(conn)]
    assert ids == [second, first]
