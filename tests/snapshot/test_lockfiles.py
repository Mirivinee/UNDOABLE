from pathlib import Path

from undoable.snapshot.lockfiles import backup_lockfiles


def test_backs_up_present_lockfiles(tmp_path: Path) -> None:
    (tmp_path / "requirements.txt").write_text("requests==2.31.0\n")
    (tmp_path / "package-lock.json").write_text('{"lockfileVersion": 1}')
    (tmp_path / "not-a-lockfile.txt").write_text("irrelevant")

    records = backup_lockfiles(tmp_path)

    kinds = {r.original_path for r in records}
    assert str(tmp_path / "requirements.txt") in kinds
    assert str(tmp_path / "package-lock.json") in kinds
    assert len(records) == 2


def test_no_lockfiles_present_returns_empty(tmp_path: Path) -> None:
    assert backup_lockfiles(tmp_path) == []


def test_only_root_level_lockfiles_are_backed_up(tmp_path: Path) -> None:
    nested = tmp_path / "subdir"
    nested.mkdir()
    (nested / "requirements.txt").write_text("ignored")

    assert backup_lockfiles(tmp_path) == []
