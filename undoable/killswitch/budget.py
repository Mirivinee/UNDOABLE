import sqlite3
from dataclasses import dataclass

from undoable.store.events import get_events


@dataclass(frozen=True)
class BudgetFinding:
    used: int
    limit: int


def check_budget(
    conn: sqlite3.Connection, session_id: str, max_actions: int | None
) -> BudgetFinding | None:
    """None if unlimited (max_actions is None, the default) or under budget.

    Token/cost tracking isn't implemented: Claude Code's documented hook
    payloads don't carry usage or cost data, only a transcript_path whose
    per-message usage schema isn't part of any confirmed contract. Action
    count is used instead -- a real, always-available budget unit, not a
    stand-in for a number this module can't reliably get.
    """
    if max_actions is None:
        return None
    used = len(get_events(conn, session_id=session_id, hook_event="PreToolUse"))
    if used >= max_actions:
        return BudgetFinding(used=used, limit=max_actions)
    return None
