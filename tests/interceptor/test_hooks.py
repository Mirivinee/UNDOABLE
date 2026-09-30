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

TYPOSQUAT_INSTALL = {
    "session_id": "sess-1",
    "hook_event_name": "PreToolUse",
    "cwd": "/work/project",
    "tool_name": "Bash",
    "tool_input": {"command": "pip install reqeusts"},
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


def _permission_decision(stdout: str) -> dict:
    return json.loads(stdout)["hookSpecificOutput"]


def test_run_denies_dangerous_command_via_json_output(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO(json.dumps(DANGEROUS_BASH))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0  # exit 2 would force a hard block regardless of the JSON
    output = _permission_decision(capsys.readouterr().out)
    assert output["hookEventName"] == "PreToolUse"
    assert output["permissionDecision"] == "deny"
    assert output["permissionDecisionReason"]

    [event] = _events(tmp_path)
    assert event.decision == "deny"
    assert event.risk_tier == "dangerous"
    assert event.reason


def test_run_asks_about_risky_command_via_json_output(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO(json.dumps(RISKY_BASH))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    output = _permission_decision(capsys.readouterr().out)
    assert output["permissionDecision"] == "ask"
    assert output["permissionDecisionReason"]

    [event] = _events(tmp_path)
    assert event.decision == "ask"
    assert event.risk_tier == "risky"
    assert event.reason


def test_run_asks_about_typosquat_package_install(tmp_path: Path, capsys, monkeypatch) -> None:
    import undoable.packages.registry as packages_registry

    monkeypatch.setattr(packages_registry, "default_fetch", lambda url, timeout: 200)

    stdin = io.StringIO(json.dumps(TYPOSQUAT_INSTALL))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    output = _permission_decision(capsys.readouterr().out)
    assert output["permissionDecision"] == "ask"
    assert "requests" in output["permissionDecisionReason"]

    [event] = _events(tmp_path)
    assert event.decision == "ask"
    assert event.risk_tier == "package"


def test_run_does_not_ask_when_package_registry_is_unreachable(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    import undoable.packages.registry as packages_registry

    def raising_fetch(url, timeout):
        raise TimeoutError

    monkeypatch.setattr(packages_registry, "default_fetch", raising_fetch)

    payload = {**PRE_TOOL_USE, "tool_input": {"command": "pip install requests"}}
    exit_code = run(io.StringIO(json.dumps(payload)), project_dir=str(tmp_path))

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""  # unreachable registry != a reason to ask

    [event] = _events(tmp_path)
    assert event.decision == "allow"


def test_run_combines_firewall_and_package_reasons_in_one_chained_command(
    tmp_path: Path, capsys, monkeypatch
) -> None:
    import undoable.packages.registry as packages_registry

    monkeypatch.setattr(packages_registry, "default_fetch", lambda url, timeout: 200)

    payload = {
        **RISKY_BASH,
        "tool_input": {"command": "git push origin main && pip install reqeusts"},
    }
    exit_code = run(io.StringIO(json.dumps(payload)), project_dir=str(tmp_path))

    assert exit_code == 0
    output = _permission_decision(capsys.readouterr().out)
    assert output["permissionDecision"] == "ask"
    assert "git push" in output["permissionDecisionReason"]
    assert "requests" in output["permissionDecisionReason"]


def test_run_prints_nothing_for_safe_command(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO(json.dumps(PRE_TOOL_USE))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    # No JSON at all for "allow" -- Claude Code's own normal permission flow
    # applies rather than us force-approving every safe command.
    assert capsys.readouterr().out.strip() == ""

    [event] = _events(tmp_path)
    assert event.decision == "allow"
    assert event.risk_tier == "safe"


def test_run_does_not_evaluate_firewall_for_posttooluse(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO(json.dumps(POST_TOOL_USE))
    exit_code = run(stdin, project_dir=str(tmp_path))

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""
    [event] = _events(tmp_path)
    assert event.decision is None
    assert event.risk_tier is None


def test_run_asks_on_malformed_json_rather_than_silently_allowing(tmp_path: Path, capsys) -> None:
    stdin = io.StringIO("{not valid json")
    exit_code = run(stdin, project_dir=str(tmp_path))  # must not raise

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "undoable" in captured.err
    output = _permission_decision(captured.out)
    assert output["permissionDecision"] == "ask"
    assert not (tmp_path / ".undoable" / "undoable.db").exists()


def test_run_asks_on_internal_error_during_pretooluse(monkeypatch, tmp_path: Path, capsys) -> None:
    import undoable.interceptor.hooks as hooks_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(hooks_module, "evaluate", boom)
    exit_code = hooks_module.run(io.StringIO(json.dumps(PRE_TOOL_USE)), project_dir=str(tmp_path))

    assert exit_code == 0
    output = _permission_decision(capsys.readouterr().out)
    assert output["permissionDecision"] == "ask"
    assert "boom" in output["permissionDecisionReason"]


def test_run_allows_non_pretooluse_hook_on_internal_error(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    import undoable.interceptor.hooks as hooks_module

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(hooks_module, "evaluate", boom)
    exit_code = hooks_module.run(io.StringIO(json.dumps(SESSION_START)), project_dir=str(tmp_path))

    assert exit_code == 0
    assert capsys.readouterr().out.strip() == ""


def test_run_does_not_downgrade_a_dangerous_decision_when_logging_fails(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    """Regression test: a log_event failure must never downgrade an
    already-computed deny/ask decision back to something weaker."""
    import undoable.interceptor.hooks as hooks_module

    def boom(*args, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(hooks_module, "log_event", boom)
    exit_code = hooks_module.run(io.StringIO(json.dumps(DANGEROUS_BASH)), project_dir=str(tmp_path))

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "disk full" in captured.err
    output = _permission_decision(captured.out)
    assert output["permissionDecision"] == "deny"


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


def test_hook_command_via_subprocess_denies_dangerous_command(tmp_path: Path) -> None:
    import subprocess

    result = subprocess.run(
        [sys.executable, "-m", "undoable.cli", "hook"],
        input=json.dumps(DANGEROUS_BASH),
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=10,
    )

    assert result.returncode == 0
    output = _permission_decision(result.stdout)
    assert output["permissionDecision"] == "deny"
