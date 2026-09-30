from collections import Counter

from undoable.store.db import connect, default_db_path
from undoable.store.events import Event, get_events
from undoable.store.snapshots import SnapshotRecord, list_snapshots


def generate_report(project_dir: str, since: str | None = None) -> str:
    """Markdown summary of everything logged for a project: actions taken,
    blocked attempts, items flagged for review, and snapshots created.

    `since`, if given, is an ISO 8601 timestamp (as stored in `logged_at`/
    `created_at`); only events/snapshots at or after it are included --
    comparing as strings works because both columns are always written in
    ISO 8601 UTC, which sorts lexicographically the same as chronologically.
    """
    conn = connect(default_db_path(project_dir))
    try:
        events = get_events(conn)
        snapshots = list_snapshots(conn)
    finally:
        conn.close()

    if since is not None:
        events = [e for e in events if e.logged_at >= since]
        snapshots = [s for s in snapshots if s.created_at >= since]

    return _render(events, snapshots, since)


def _render(events: list[Event], snapshots: list[SnapshotRecord], since: str | None) -> str:
    lines = ["# UNDOABLE Morning Report", ""]
    lines.append(f"_Since {since}_" if since else "_All time_")
    lines.append("")

    denied = [e for e in events if e.decision == "deny"]
    asked = [e for e in events if e.decision == "ask"]

    lines.append("## Summary")
    lines.append(f"- {len(events)} action(s) logged")
    for hook_event, count in sorted(Counter(e.hook_event for e in events).items()):
        lines.append(f"  - {hook_event}: {count}")
    lines.append(f"- {len(denied)} blocked (denied)")
    lines.append(f"- {len(asked)} flagged for review (asked)")
    lines.append(f"- {len(snapshots)} snapshot(s) created")
    lines.append(
        "- Total cost: not available -- Claude Code doesn't expose token/cost "
        "data through hooks, only a transcript file with no documented usage schema"
    )
    lines.append("")

    if denied:
        lines.append("## Blocked")
        lines.extend(_event_lines(denied))
        lines.append("")

    if asked:
        lines.append("## Needs review")
        lines.extend(_event_lines(asked))
        lines.append("")

    if snapshots:
        lines.append("## Snapshots")
        for s in snapshots:
            label = s.label or "(no label)"
            lines.append(f"- #{s.id} {label} at {s.created_at} ({s.commit_sha[:8]})")
        lines.append("")

    return "\n".join(lines)


def _event_lines(events: list[Event]) -> list[str]:
    lines = []
    for e in events:
        lines.append(f"- `{e.tool_name or e.hook_event}` at {e.logged_at}: {e.reason}")
        command = (e.tool_input or {}).get("command") if e.tool_input else None
        if command:
            lines.append(f"  - command: `{command}`")
    return lines
