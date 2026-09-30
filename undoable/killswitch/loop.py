import sqlite3
from dataclasses import dataclass
from typing import Any

from undoable.store.events import get_events


@dataclass(frozen=True)
class LoopFinding:
    tool_name: str
    repeats: int


def detect_loop(
    conn: sqlite3.Connection,
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any] | None,
    threshold: int,
) -> LoopFinding | None:
    """Is the call about to run the Nth identical repeat in a row?

    Compares the current (not-yet-logged) tool_name/tool_input against the
    most recent (threshold - 1) already-logged PreToolUse calls in this
    session: if every one of them matches exactly, this would be the
    threshold-th consecutive identical attempt. Exact input equality is
    used rather than trying to interpret tool_response as "was this an
    error" -- that response schema isn't part of any confirmed contract,
    while "the agent keeps issuing the exact same call" is a reliable,
    schema-independent signal of being stuck on its own.
    """
    if threshold < 2:
        return None

    events = get_events(conn, session_id=session_id, hook_event="PreToolUse")
    recent = events[-(threshold - 1) :]
    if len(recent) < threshold - 1:
        return None

    if all(e.tool_name == tool_name and e.tool_input == tool_input for e in recent):
        return LoopFinding(tool_name=tool_name, repeats=threshold)
    return None
