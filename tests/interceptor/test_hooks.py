import io
import json
import sys
import time
from pathlib import Path

from undoable.interceptor.hooks import log_event, run
from undoable.store.db import connect, default_db_path
from undoable.store.events import get_events

PRE_TOOL_USE = {
    "session_id": "sess-1",
    "hook_event_name": "PreToolUse",
    "cwd": "/work/project",
    "transcript_path": "/tmp/transcript.jsonl",
    "tool_name": "Bash",
    "tool_input": {"command": "ls -la"},
}

POST_TOOL_USE = {
    "session_id": "sess-1",
    "hook_event_name": "PostToolUse",
    "cwd": "/work/project",
    "tool_name": "Bash",
    "tool_input": {"command": "ls -la"},
    "tool_response": {"stdout": "file.txt\n", "exit_code": 0},
}

SESSION_START = {
    "session_id": "sess-1",
    "hook_event_name": "SessionStart",
    "cwd": "/work/project",
    "source": "startup",
}

DANGEROUS_BASH = {
    "session_id": "sess-1",
    "hook_event_name": "PreToolUse",
    "cwd": "/work/project",
    "tool_name": "Bash",
    "tool_input": {"command": "rm -rf /tmp/data"},
}

RISKY_BASH = {
    "session_id": "sess-1",
    "hook_event_name": "PreToolUse",
    "cwd": "/work/project",
    "tool_name": "Bash",
    "tool_input": {"command": "git push origin main"},
}


def _events(tmp_path: Path):
    conn = connect(default_db_path(tmp_path))
    try:
        return get_events(conn)
    finally:
        conn.close()


def test_log_event_pretooluse_captures_tool_input(tmp_path: Path) -> None:
    log_event(PRE_TOOL_USE, project_dir=str(tmp_path))

    [event] = _events(tmp_path)
    assert event.hook_event == "PreToolUse"
    assert event.tool_name == "Bash"
    assert event.tool_input == {"command": "ls -la"}
    assert event.tool_response is None
    assert event.raw_payload == PRE_TOOL_USE


def test_log_event_posttooluse_captures_tool_response(tmp_path: Path) -> None:
    log_event(POST_TOOL_USE, project_dir=str(tmp_path))

    [event] = _events(tmp_path)
    assert event.tool_response == {"stdout": "file.txt\n", "exit_code": 0}


def test_log_event_session_level_hook_has_no_tool_fields(tmp_path: Path) -> None:
    log_event(SESSION_START, project_dir=str(tmp_path))

    [event] = _events(tmp_path)
    assert event.hook_event == "SessionStart"
    assert event.tool_name is None
    assert event.tool_input is None


def test_log_event_falls_back_to_payload_cwd_when_no_project_dir(tmp_path: Path) -> None:
    payload = {**SESSION_START, "cwd": str(tmp_path)}
    log_event(payload)

    [event] = _events(tmp_path)
    assert event.session_id == "sess-1"


def test_run_reads_stdin_and_logs(tmp_path: Path) -> None:
    stdin = io.StringIO('{"session_id": "sess-2", "hook_event_name": "Stop", "cwd": "x"}')
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    [event] = _events(tmp_path)
    assert event.session_id == "sess-2"
    assert event.hook_event == "Stop"


def test_run_blocks_dangerous_command_and_logs_the_block(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO(json.dumps(DANGEROUS_BASH))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 2
    assert capsys.readouterr().err.strip()
    [event] = _events(tmp_path)
    assert event.decision == "block"
    assert event.risk_tier == "dangerous"
    assert event.reason


def test_run_allows_risky_command_but_flags_it(tmp_path: Path) -> None:
    stdin = io.StringIO(json.dumps(RISKY_BASH))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    [event] = _events(tmp_path)
    assert event.decision == "allow"
    assert event.risk_tier == "risky"
    assert event.reason


def test_run_allows_safe_command(tmp_path: Path) -> None:
    stdin = io.StringIO(json.dumps(PRE_TOOL_USE))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    [event] = _events(tmp_path)
    assert event.decision == "allow"
    assert event.risk_tier == "safe"


def test_run_does_not_evaluate_firewall_for_posttooluse(tmp_path: Path) -> None:
    stdin = io.StringIO(json.dumps(POST_TOOL_USE))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    [event] = _events(tmp_path)
    assert event.decision is None
    assert event.risk_tier is None


def test_run_never_raises_on_malformed_json(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO("{not valid json")
    exit_code = run(stdin, project_dir=str(tmp_path))  # must not raise

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "undoable" in captured.err
    assert not (tmp_path / ".undoable" / "undoable.db").exists()


def test_run_blocks_pretooluse_on_internal_error(monkeypatch, tmp_path: Path) -> None:
    import undoable.interceptor.hooks as hooks_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(hooks_module, "log_event", boom)
    exit_code = hooks_module.run(io.StringIO(json.dumps(PRE_TOOL_USE)), project_dir=str(tmp_path))

    assert exit_code == 2


def test_run_allows_non_pretooluse_hook_on_internal_error(monkeypatch, tmp_path: Path) -> None:
    import undoable.interceptor.hooks as hooks_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(hooks_module, "log_event", boom)
    exit_code = hooks_module.run(io.StringIO(json.dumps(SESSION_START)), project_dir=str(tmp_path))

    assert exit_code == 0


def test_run_never_raises_on_empty_stdin(tmp_path: Path) -> None:
    run(io.StringIO(""), project_dir=str(tmp_path))  # must not raise

    [event] = _events(tmp_path)
    assert event.hook_event == "Unknown"
    assert event.session_id == "unknown"


def test_logging_latency_is_well_under_the_200ms_budget(tmp_path: Path) -> None:
    start = time.perf_counter()
    log_event(PRE_TOOL_USE, project_dir=str(tmp_path))
    elapsed = time.perf_counter() - start

    assert elapsed < 0.2


def test_hook_command_via_subprocess_always_exits_zero(tmp_path: Path) -> None:
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "undoable.cli", "hook"],
        input='{"session_id": "sess-3", "hook_event_name": "SessionEnd", "cwd": "."}',
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    [event] = _events(tmp_path)
    assert event.session_id == "sess-3"


def test_hook_command_via_subprocess_blocks_dangerous_command(tmp_path: Path) -> None:
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "undoable.cli", "hook"],
        input=json.dumps(DANGEROUS_BASH),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 2
    assert result.stderr.strip()
