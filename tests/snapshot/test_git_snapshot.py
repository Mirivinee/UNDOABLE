import subprocess
from pathlib import Path

import pytest

from undoable.snapshot.git_snapshot import (
    NotAGitRepoError,
    SnapshotNotFoundError,
    create_snapshot,
    rollback,
)
from undoable.store.db import connect, default_db_path
from undoable.store.snapshots import get_snapshot


def _git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def _commit_file(repo: Path, name: str, content: str) -> None:
    (repo / name).write_text(content)
    _git(["add", name], repo)
    _git(["commit", "-q", "-m", f"add {name}"], repo)


def test_create_snapshot_requires_git_repo(tmp_path: Path) -> None:
    with pytest.raises(NotAGitRepoError):
        create_snapshot(tmp_path)


def test_create_snapshot_works_with_no_commits_yet(git_repo: Path) -> None:
    (git_repo / "new.txt").write_text("hello")

    snapshot = create_snapshot(git_repo, label="first ever")
    assert snapshot.parent_sha is None
    assert snapshot.commit_sha
    assert snapshot.tree_sha


def test_create_snapshot_captures_tracked_and_untracked_files(git_repo: Path) -> None:
    _commit_file(git_repo, "tracked.txt", "v1")
    (git_repo / "untracked.txt").write_text("scratch")

    snapshot = create_snapshot(git_repo)
    tree_listing = _git(["ls-tree", "-r", "--name-only", snapshot.commit_sha], git_repo)
    assert "tracked.txt" in tree_listing
    assert "untracked.txt" in tree_listing


def test_create_snapshot_does_not_disturb_real_index_or_worktree(git_repo: Path) -> None:
    _commit_file(git_repo, "tracked.txt", "v1")
    (git_repo / "tracked.txt").write_text("v2 uncommitted")
    (git_repo / "scratch.txt").write_text("scratch")

    before = _git(["status", "--porcelain"], git_repo)
    create_snapshot(git_repo)
    after = _git(["status", "--porcelain"], git_repo)

    # ".undoable/" (our own store) appearing as new untracked content is an
    # expected side effect of persisting the snapshot record -- what must
    # NOT change is the status of files that were already there.
    assert "tracked.txt" in before and "tracked.txt" in after
    assert "scratch.txt" in before and "scratch.txt" in after
    assert (git_repo / "tracked.txt").read_text() == "v2 uncommitted"


def test_create_snapshot_persists_to_store(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    snapshot = create_snapshot(git_repo, label="checkpoint")

    conn = connect(default_db_path(git_repo))
    try:
        stored = get_snapshot(conn, snapshot.id)
    finally:
        conn.close()

    assert stored == snapshot


def test_create_snapshot_writes_a_hidden_ref(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    snapshot = create_snapshot(git_repo)

    ref_sha = _git(["rev-parse", f"refs/undoable/snapshots/{snapshot.id}"], git_repo)
    assert ref_sha == snapshot.commit_sha
    # Hidden from normal branch listing -- it lives outside refs/heads/.
    assert "undoable" not in _git(["branch", "--list"], git_repo)


def test_rollback_restores_a_modified_file(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    snapshot = create_snapshot(git_repo)
    (git_repo / "a.txt").write_text("v2 - agent broke it")

    result = rollback(git_repo, snapshot.id)

    assert (git_repo / "a.txt").read_text() == "v1"
    assert "a.txt" in result.restored


def test_rollback_restores_a_deleted_file(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    snapshot = create_snapshot(git_repo)
    (git_repo / "a.txt").unlink()

    rollback(git_repo, snapshot.id)

    assert (git_repo / "a.txt").read_text() == "v1"


def test_rollback_removes_files_created_after_the_snapshot(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    snapshot = create_snapshot(git_repo)
    (git_repo / "new_from_agent.txt").write_text("oops")

    result = rollback(git_repo, snapshot.id)

    assert not (git_repo / "new_from_agent.txt").exists()
    assert "new_from_agent.txt" in result.removed


def test_rollback_leaves_files_already_in_the_snapshot_alone(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    (git_repo / "untracked_before.txt").write_text("scratch")
    snapshot = create_snapshot(git_repo)  # captures untracked_before.txt too

    result = rollback(git_repo, snapshot.id)

    assert (git_repo / "untracked_before.txt").exists()
    assert "untracked_before.txt" not in result.removed


def test_rollback_ignores_gitignored_files_entirely(git_repo: Path) -> None:
    _commit_file(git_repo, ".gitignore", "ignored.log\n")
    snapshot = create_snapshot(git_repo)
    (git_repo / "ignored.log").write_text("build output")

    result = rollback(git_repo, snapshot.id)

    assert (git_repo / "ignored.log").exists()
    assert "ignored.log" not in result.removed


def test_rollback_unknown_snapshot_raises(git_repo: Path) -> None:
    with pytest.raises(SnapshotNotFoundError):
        rollback(git_repo, 999)


def test_rollback_requires_git_repo(tmp_path: Path) -> None:
    with pytest.raises(NotAGitRepoError):
        rollback(tmp_path, 1)


def test_create_snapshot_requires_repo_root_not_a_subdirectory(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    subdir = git_repo / "subdir"
    subdir.mkdir()

    with pytest.raises(NotAGitRepoError):
        create_snapshot(subdir)


def test_rollback_requires_repo_root_not_a_subdirectory(git_repo: Path) -> None:
    _commit_file(git_repo, "a.txt", "v1")
    snapshot = create_snapshot(git_repo)
    subdir = git_repo / "subdir"
    subdir.mkdir()

    with pytest.raises(NotAGitRepoError):
        rollback(subdir, snapshot.id)
