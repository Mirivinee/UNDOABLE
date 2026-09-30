import json
import sys
from typing import Any, TextIO

from undoable.firewall.rules import BLOCK, Decision, evaluate_tool_use
from undoable.store.db import connect, default_db_path
from undoable.store.events import insert_event


def evaluate(payload: dict[str, Any]) -> Decision | None:
    """Firewall decision for a hook payload, or None where none applies.

    Only PreToolUse can still be prevented -- by the time PostToolUse or a
    session-level hook fires, the action already happened.
    """
    if payload.get("hook_event_name") != "PreToolUse":
        return None
    return evaluate_tool_use(payload.get("tool_name", ""), payload.get("tool_input"))


def log_event(
    payload: dict[str, Any],
    project_dir: str | None = None,
    decision: Decision | None = None,
) -> int:
    """Log one already-parsed hook payload, with an optional firewall decision
    to record alongside it. Returns the new row's id."""
    resolved_dir = project_dir or payload.get("cwd") or "."
    conn = connect(default_db_path(resolved_dir))
    try:
        return insert_event(
            conn,
            session_id=payload.get("session_id", "unknown"),
            hook_event=payload.get("hook_event_name", "Unknown"),
            raw_payload=payload,
            tool_name=payload.get("tool_name"),
            tool_input=payload.get("tool_input"),
            tool_response=payload.get("tool_response"),
            decision=decision.decision if decision else None,
            risk_tier=decision.tier if decision else None,
            reason=decision.reason if decision else None,
            cwd=payload.get("cwd"),
            transcript_path=payload.get("transcript_path"),
        )
    finally:
        conn.close()


def run(stdin: TextIO = sys.stdin, project_dir: str | None = None) -> int:
    """Entry point for the `undoable hook` command.

    Returns the process exit code Claude Code should see: 0 to allow the
    tool call, 2 to block it (stderr becomes the reason Claude is shown).
    Never raises, but never silently allows a tool call either: if stdin
    can't even be parsed, there's no identified tool call yet, so we just
    report it and allow. If parsing succeeded and the hook is PreToolUse but
    something in our own evaluation breaks, that's an internal error on a
    real decision, so we fail safe by blocking rather than allowing it
    through unnoticed (there is no distinct "ask" exit code available here).
    """
    try:
        raw_text = stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except Exception as exc:
        print(f"undoable: failed to parse hook input: {exc}", file=sys.stderr)
        return 0

    is_pre_tool_use = payload.get("hook_event_name") == "PreToolUse"
    try:
        decision = evaluate(payload)
        log_event(payload, project_dir=project_dir, decision=decision)
    except Exception as exc:
        print(f"undoable: internal error evaluating hook event: {exc}", file=sys.stderr)
        return 2 if is_pre_tool_use else 0

    if decision is not None and decision.decision == BLOCK:
        print(decision.reason, file=sys.stderr)
        return 2
    return 0
