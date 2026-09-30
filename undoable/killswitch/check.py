from dataclasses import dataclass
from typing import Any

from undoable.killswitch.boundary import find_out_of_bounds_path
from undoable.killswitch.budget import check_budget
from undoable.killswitch.config import KillSwitchConfig, load_config
from undoable.killswitch.loop import detect_loop
from undoable.store.db import connect, default_db_path

ASK = "ask"


@dataclass(frozen=True)
class KillSwitchDecision:
    decision: str  # always "ask" -- see evaluate()'s docstring
    reason: str
    check: str  # "loop" | "boundary" | "budget"


def evaluate(
    project_dir: str,
    session_id: str,
    tool_name: str,
    tool_input: dict[str, Any] | None,
    config: KillSwitchConfig | None = None,
) -> KillSwitchDecision | None:
    """None if nothing tripped. All three checks resolve to "ask", not
    "deny": a stuck loop, an out-of-bounds path, or a budget limit are each
    reasons for a human to look, not proof the action itself is malicious
    (unlike the firewall's dangerous tier) -- the goal is stopping runaway
    behavior, not refusing a possibly-legitimate one-off.
    """
    config = config or load_config(project_dir)
    conn = connect(default_db_path(project_dir))
    try:
        loop = detect_loop(conn, session_id, tool_name, tool_input, config.loop_threshold)
        if loop is not None:
            return KillSwitchDecision(
                decision=ASK,
                reason=(
                    f"The same {loop.tool_name} call has been attempted "
                    f"{loop.repeats} times in a row -- this looks stuck in a loop."
                ),
                check="loop",
            )

        out_of_bounds = find_out_of_bounds_path(project_dir, tool_name, tool_input)
        if out_of_bounds is not None:
            return KillSwitchDecision(
                decision=ASK,
                reason=f"'{out_of_bounds}' is outside the project folder ({project_dir}).",
                check="boundary",
            )

        budget = check_budget(conn, session_id, config.max_actions)
        if budget is not None:
            return KillSwitchDecision(
                decision=ASK,
                reason=(
                    f"This session has used {budget.used} actions, at or over the "
                    f"configured limit of {budget.limit}."
                ),
                check="budget",
            )
    finally:
        conn.close()

    return None
