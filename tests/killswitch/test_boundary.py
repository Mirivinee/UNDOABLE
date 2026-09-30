from pathlib import Path

from undoable.killswitch.boundary import find_out_of_bounds_path


def test_path_inside_project_is_fine(tmp_path: Path) -> None:
    target = tmp_path / "src" / "app.py"
    assert find_out_of_bounds_path(str(tmp_path), "Read", {"file_path": str(target)}) is None


def test_path_outside_project_is_flagged(tmp_path: Path) -> None:
    outside = tmp_path.parent / "some_other_file.txt"
    result = find_out_of_bounds_path(str(tmp_path), "Read", {"file_path": str(outside)})
    assert result == str(outside)


def test_project_dir_itself_is_fine(tmp_path: Path) -> None:
    assert find_out_of_bounds_path(str(tmp_path), "Read", {"file_path": str(tmp_path)}) is None


def test_non_file_tools_are_not_checked(tmp_path: Path) -> None:
    outside = tmp_path.parent / "x.txt"
    result = find_out_of_bounds_path(str(tmp_path), "Bash", {"command": f"cat {outside}"})
    assert result is None


def test_missing_file_path_is_fine(tmp_path: Path) -> None:
    assert find_out_of_bounds_path(str(tmp_path), "Read", {}) is None
    assert find_out_of_bounds_path(str(tmp_path), "Read", None) is None


def test_checks_write_and_edit_and_glob_and_grep(tmp_path: Path) -> None:
    outside = str(tmp_path.parent / "x.txt")
    assert find_out_of_bounds_path(str(tmp_path), "Write", {"file_path": outside}) == outside
    assert find_out_of_bounds_path(str(tmp_path), "Edit", {"file_path": outside}) == outside
    assert find_out_of_bounds_path(str(tmp_path), "Glob", {"path": outside}) == outside
