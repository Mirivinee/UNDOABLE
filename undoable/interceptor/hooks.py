import json
import sys
from typing import Any, TextIO

from undoable.store.db import connect, default_db_path
from undoable.store.events import insert_event


def log_event(payload: dict[str, Any], project_dir: str | None = None) -> int:
    """Log one already-parsed hook payload. Returns the new row's id."""
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
            cwd=payload.get("cwd"),
            transcript_path=payload.get("transcript_path"),
        )
    finally:
        conn.close()


def run(stdin: TextIO = sys.stdin, project_dir: str | None = None) -> None:
    """Entry point for the `undoable hook` command.

    Phase 1 has no firewall yet, so there is no decision to enforce -- only
    logging. Never raises and never exits non-zero: an interceptor that
    crashes or blocks the agent is worse than one that misses a log line.
    """
    try:
        raw_text = stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
        log_event(payload, project_dir=project_dir)
    except Exception as exc:
        print(f"undoable: failed to log hook event: {exc}", file=sys.stderr)
