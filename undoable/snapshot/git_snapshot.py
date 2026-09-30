import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from undoable.store.db import connect, default_db_path
from undoable.store.snapshots import SnapshotRecord, get_snapshot, insert_snapshot

# Snapshot commits get their own fixed identity so creating one never fails
# because the user (or CI environment) hasn't configured git user.name/email,
# and so these machine-made commits are never attributed to a human author.
_COMMIT_IDENTITY = {
    "GIT_AUTHOR_NAME": "undoable",
    "GIT_AUTHOR_EMAIL": "undoable@localhost",
    "GIT_COMMITTER_NAME": "undoable",
    "GIT_COMMITTER_EMAIL": "undoable@localhost",
}


class NotAGitRepoError(RuntimeError):
    """Raised when a snapshot/rollback is requested outside a git repository."""


class SnapshotNotFoundError(RuntimeError):
    """Raised when a rollback is requested for an unknown snapshot id."""


@dataclass(frozen=True)
class RollbackResult:
    restored: list[str]  # paths written to match the snapshot
    removed: list[str]  # paths deleted because they didn't exist in the snapshot


def _run_git(args: list[str], cwd: Path, env: dict[str, str] | None = None) -> str:
    # core.quotePath=false: filenames with spaces/non-ASCII come back as
    # plain UTF-8 in --name-only output instead of C-style quoted/escaped,
    # so paths can be joined straight onto project_dir without re-parsing.
    result = subprocess.run(
        ["git", "-c", "core.quotePath=false", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result.stdout.strip()


def _require_git_repo(project_dir: Path) -> None:
    """Require project_dir to be a git repo's *root*, not merely somewhere
    inside one.

    This matters beyond strictness: every path this module produces (tree
    listings, added-since-snapshot diffs) is repo-root-relative, and
    `git read-tree --reset -u` operates on the whole index with no path
    scoping. If project_dir were a subdirectory of a larger repo -- or, as
    happens on at least one real dev machine, an unrelated ancestor
    directory that itself happens to be a git repo -- a rollback would
    resolve paths against the wrong root and reset the wrong working tree.
    Requiring equality with `git rev-parse --show-toplevel` is what makes
    "operate on the whole index" safe to do at all.
    """
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise NotAGitRepoError(f"{project_dir} is not inside a git working tree.")
    toplevel = Path(result.stdout.strip()).resolve()
    if os.path.normcase(str(toplevel)) != os.path.normcase(str(project_dir.resolve())):
        raise NotAGitRepoError(
            f"{project_dir} is not the root of a git repository "
            f"(its repo root is {toplevel}); point undoable at the repo root."
        )


def _current_head(project_dir: Path) -> str | None:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=project_dir,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip() if result.returncode == 0 else None


def _write_tree_for_worktree(project_dir: Path) -> str:
    """Tree object matching the working tree right now (tracked, modified,
    and untracked-but-not-ignored files alike), without touching the repo's
    real index or HEAD. ".undoable/" (our own event log/snapshot store) is
    always excluded -- it's bookkeeping, not project content, and including
    it would mean every snapshot embeds a copy of the ever-growing DB file.

    Uses a throwaway index file so this is safe to call at any time,
    including mid-way through something else the agent is doing.
    """
    with tempfile.TemporaryDirectory() as tmp:
        temp_index = Path(tmp) / "index"
        env = {**os.environ, "GIT_INDEX_FILE": str(temp_index)}
        _run_git(["add", "-A", "--", ".", ":!.undoable"], cwd=project_dir, env=env)
        return _run_git(["write-tree"], cwd=project_dir, env=env)


def create_snapshot(project_dir: str | Path, label: str | None = None) -> SnapshotRecord:
    """Snapshot the current working tree (tracked, modified, and untracked
    files) as a commit on a hidden ref, without disturbing the real index,
    HEAD, or branch. Returns the stored SnapshotRecord."""
    project_dir = Path(project_dir)
    _require_git_repo(project_dir)

    tree_sha = _write_tree_for_worktree(project_dir)
    parent_sha = _current_head(project_dir)

    commit_args = ["commit-tree", tree_sha]
    if parent_sha:
        commit_args += ["-p", parent_sha]
    message = label or "undoable snapshot"
    commit_env = {**os.environ, **_COMMIT_IDENTITY}
    commit_sha = _run_git([*commit_args, "-m", message], cwd=project_dir, env=commit_env)

    conn = connect(default_db_path(project_dir))
    try:
        snapshot_id = insert_snapshot(
            conn,
            commit_sha=commit_sha,
            tree_sha=tree_sha,
            parent_sha=parent_sha,
            label=label,
        )
        snapshot = get_snapshot(conn, snapshot_id)
    finally:
        conn.close()

    _run_git(["update-ref", f"refs/undoable/snapshots/{snapshot_id}", commit_sha], cwd=project_dir)

    return snapshot


def rollback(project_dir: str | Path, snapshot_id: int) -> RollbackResult:
    """Restore the working tree to match a snapshot.

    Files present in the snapshot are written back to match it (git
    read-tree --reset -u, on the repo's real index). Files that exist now
    but weren't part of the snapshot -- created after it was taken -- are
    deleted, computed as the tree-diff between the snapshot and the current
    working tree, so unrelated pre-existing untracked files are never touched.
    """
    project_dir = Path(project_dir)
    _require_git_repo(project_dir)

    conn = connect(default_db_path(project_dir))
    try:
        snapshot = get_snapshot(conn, snapshot_id)
    finally:
        conn.close()
    if snapshot is None:
        raise SnapshotNotFoundError(f"No snapshot with id {snapshot_id}.")

    current_tree = _write_tree_for_worktree(project_dir)
    added_since_snapshot = _added_paths(project_dir, snapshot.tree_sha, current_tree)

    _run_git(["read-tree", "--reset", "-u", snapshot.commit_sha], cwd=project_dir)

    removed = []
    for path in added_since_snapshot:
        full_path = project_dir / path
        if full_path.exists():
            full_path.unlink()
            removed.append(path)

    restored = _run_git(["ls-tree", "-r", "--name-only", snapshot.commit_sha], cwd=project_dir)
    restored_paths = [p for p in restored.splitlines() if p]

    return RollbackResult(restored=restored_paths, removed=removed)


def _added_paths(project_dir: Path, before_tree: str, after_tree: str) -> list[str]:
    """Paths present in after_tree but not before_tree."""
    output = _run_git(
        ["diff", "--name-only", "--diff-filter=A", before_tree, after_tree],
        cwd=project_dir,
    )
    return [p for p in output.splitlines() if p]
