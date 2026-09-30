from pathlib import Path

from undoable.killswitch.check import evaluate
from undoable.killswitch.config import KillSwitchConfig
from undoable.store.db import connect, default_db_path
from undoable.store.events import insert_event


def _log(project_dir: Path, session_id: str, tool_name: str = "Bash", tool_input=None) -> None:
    conn = connect(default_db_path(project_dir))
    try:
        insert_event(
            conn,
            session_id=session_id,
            hook_event="PreToolUse",
            raw_payload={},
            tool_name=tool_name,
            tool_input=tool_input or {"command": "x"},
        )
    finally:
        conn.close()


def test_none_when_nothing_tripped(tmp_path: Path) -> None:
    assert evaluate(str(tmp_path), "s1", "Bash", {"command": "ls"}) is None


def test_loop_detected(tmp_path: Path) -> None:
    config = KillSwitchConfig(loop_threshold=3)
    _log(tmp_path, "s1", "Bash", {"command": "pytest"})
    _log(tmp_path, "s1", "Bash", {"command": "pytest"})

    result = evaluate(str(tmp_path), "s1", "Bash", {"command": "pytest"}, config=config)
    assert result.check == "loop"
    assert result.decision == "ask"


def test_boundary_detected(tmp_path: Path) -> None:
    outside = str(tmp_path.parent / "x.txt")
    result = evaluate(str(tmp_path), "s1", "Read", {"file_path": outside})
    assert result.check == "boundary"


def test_budget_detected(tmp_path: Path) -> None:
    config = KillSwitchConfig(max_actions=2)
    _log(tmp_path, "s1")
    _log(tmp_path, "s1")

    result = evaluate(str(tmp_path), "s1", "Bash", {"command": "ls"}, config=config)
    assert result.check == "budget"


def test_loop_takes_priority_over_budget(tmp_path: Path) -> None:
    config = KillSwitchConfig(max_actions=1, loop_threshold=3)
    _log(tmp_path, "s1", "Bash", {"command": "pytest"})
    _log(tmp_path, "s1", "Bash", {"command": "pytest"})

    result = evaluate(str(tmp_path), "s1", "Bash", {"command": "pytest"}, config=config)
    assert result.check == "loop"


def test_reads_config_from_disk_when_not_passed_explicitly(tmp_path: Path) -> None:
    (tmp_path / ".undoable").mkdir()
    (tmp_path / ".undoable" / "config.json").write_text('{"max_actions": 1}')
    _log(tmp_path, "s1")

    result = evaluate(str(tmp_path), "s1", "Bash", {"command": "ls"})
    assert result.check == "budget"
