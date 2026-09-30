import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class Event:
    id: int
    session_id: str
    hook_event: str
    tool_name: str | None
    tool_input: dict[str, Any] | None
    tool_response: dict[str, Any] | None
    decision: str | None
    risk_tier: str | None
    reason: str | None
    cwd: str | None
    transcript_path: str | None
    raw_payload: dict[str, Any]
    logged_at: str


def insert_event(
    conn: sqlite3.Connection,
    *,
    session_id: str,
    hook_event: str,
    raw_payload: dict[str, Any],
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    tool_response: dict[str, Any] | None = None,
    decision: str | None = None,
    risk_tier: str | None = None,
    reason: str | None = None,
    cwd: str | None = None,
    transcript_path: str | None = None,
) -> int:
    """Log one hook invocation. Returns the new row's id."""
    logged_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO events (
            session_id, hook_event, tool_name, tool_input, tool_response,
            decision, risk_tier, reason, cwd, transcript_path, raw_payload, logged_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            session_id,
            hook_event,
            tool_name,
            json.dumps(tool_input) if tool_input is not None else None,
            json.dumps(tool_response) if tool_response is not None else None,
            decision,
            risk_tier,
            reason,
            cwd,
            transcript_path,
            json.dumps(raw_payload),
            logged_at,
        ),
    )
    conn.commit()
    return cursor.lastrowid


def _row_to_event(row: sqlite3.Row) -> Event:
    return Event(
        id=row["id"],
        session_id=row["session_id"],
        hook_event=row["hook_event"],
        tool_name=row["tool_name"],
        tool_input=json.loads(row["tool_input"]) if row["tool_input"] is not None else None,
        tool_response=(
            json.loads(row["tool_response"]) if row["tool_response"] is not None else None
        ),
        decision=row["decision"],
        risk_tier=row["risk_tier"],
        reason=row["reason"],
        cwd=row["cwd"],
        transcript_path=row["transcript_path"],
        raw_payload=json.loads(row["raw_payload"]),
        logged_at=row["logged_at"],
    )


def get_events(
    conn: sqlite3.Connection,
    *,
    session_id: str | None = None,
    hook_event: str | None = None,
) -> list[Event]:
    """Query logged events, oldest first, optionally filtered."""
    query = "SELECT * FROM events WHERE 1=1"
    params: list[Any] = []
    if session_id is not None:
        query += " AND session_id = ?"
        params.append(session_id)
    if hook_event is not None:
        query += " AND hook_event = ?"
        params.append(hook_event)
    query += " ORDER BY id"
    rows = conn.execute(query, params).fetchall()
    return [_row_to_event(row) for row in rows]
