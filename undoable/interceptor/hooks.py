import json
import sys
from typing import Any, TextIO

from undoable.firewall.rules import ALLOW, ASK, DENY, Decision, evaluate_tool_use
from undoable.killswitch import check as killswitch_check
from undoable.packages import check as packages_check
from undoable.packages import registry as packages_registry
from undoable.snapshot.lockfiles import backup_lockfiles
from undoable.snapshot.sqlite_backup import backup_sqlite_databases_for_command
from undoable.store.db import connect, default_db_path
from undoable.store.events import insert_event

_INTERNAL_ERROR_TIER = "error"
_PACKAGE_TIER = "package"
_KILLSWITCH_TIER = "killswitch"


def evaluate(payload: dict[str, Any], project_dir: str | None = None) -> Decision | None:
    """Combined firewall + kill-switch + package-check decision for a hook
    payload, or None where none applies.

    Only PreToolUse can still be prevented -- by the time PostToolUse or a
    session-level hook fires, the action already happened. A firewall deny
    always wins outright (no reason to also spend time on the other two).
    Kill switch (loop/budget/boundary) runs next, for every tool -- it's a
    session-health concern, not specific to Bash. Package findings are
    local-first: typosquat detection never touches the network, so it's
    reliable even offline; "package doesn't exist" is network-backed and
    silently contributes nothing if the check itself fails, rather than
    turning a network hiccup into an approval-fatigue source for an
    otherwise ordinary `pip install`.
    """
    if payload.get("hook_event_name") != "PreToolUse":
        return None

    tool_name = payload.get("tool_name", "")
    tool_input = payload.get("tool_input")
    firewall_decision = evaluate_tool_use(tool_name, tool_input, cwd=payload.get("cwd"))
    if firewall_decision.decision == DENY:
        return firewall_decision

    resolved_dir = project_dir or payload.get("cwd") or "."
    kill_decision = killswitch_check.evaluate(
        resolved_dir, payload.get("session_id", "unknown"), tool_name, tool_input
    )
    if kill_decision is not None:
        return Decision(
            tier=_KILLSWITCH_TIER,
            decision=ASK,
            reason=kill_decision.reason,
            rule=f"killswitch-{kill_decision.check}",
        )

    if tool_name == "Bash":
        command = (tool_input or {}).get("command") or ""

        package_result = packages_check.evaluate_command(
            command,
            pypi_fetch=packages_registry.default_fetch,
            npm_fetch=packages_registry.default_fetch,
        )
        if package_result is not None:
            _try(lambda: backup_lockfiles(resolved_dir), "back up lockfiles")
        _try(
            lambda: backup_sqlite_databases_for_command(resolved_dir, command),
            "back up sqlite database",
        )

        if package_result is not None and package_result.decision == packages_check.ASK:
            reason = package_result.reason
            if firewall_decision.decision == ASK:
                reason = f"{firewall_decision.reason} Also: {reason}"
            return Decision(tier=_PACKAGE_TIER, decision=ASK, reason=reason, rule="package-check")

    return firewall_decision


def _try(action, description: str) -> None:
    """Best-effort side effect (a file backup): report failure, never raise
    it -- a backup that couldn't be taken is a reason to log, not a reason
    to turn a normal tool call into an internal-error "ask"."""
    try:
        action()
    except Exception as exc:
        print(f"undoable: failed to {description}: {exc}", file=sys.stderr)


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


def _permission_output(decision: Decision) -> dict[str, Any]:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision.decision,
            "permissionDecisionReason": decision.reason,
        }
    }


def run(stdin: TextIO = sys.stdin, project_dir: str | None = None) -> int:
    """Entry point for the `undoable hook` command.

    Always exits 0: exit code 2 would force a hard block regardless of any
    JSON printed, which would make "ask" impossible. A real PreToolUse
    decision is instead communicated via the documented
    hookSpecificOutput.permissionDecision JSON on stdout (allow/ask/deny).
    For "allow" nothing is printed at all, matching Claude Code's own
    convention, so the normal permission flow still applies rather than us
    force-approving every safe command.

    Never raises, and never silently allows an unidentifiable action either.
    If stdin can't even be parsed, this could still have been a mangled
    PreToolUse call, so it fails safe as "ask" rather than assuming it
    wasn't (Claude Code ignores this JSON for hook types it doesn't apply
    to, so there's no cost to raising it when we're unsure). If parsing
    succeeds but evaluating a PreToolUse payload breaks, that's the same
    "ask" fallback. Logging is a separate concern from deciding: a failure
    writing to the event log is reported but never downgrades an
    already-computed deny/ask decision back to something weaker.
    """
    try:
        raw_text = stdin.read()
        payload = json.loads(raw_text) if raw_text.strip() else {}
    except Exception as exc:
        print(f"undoable: failed to parse hook input: {exc}", file=sys.stderr)
        unparseable = Decision(
            tier=_INTERNAL_ERROR_TIER,
            decision=ASK,
            reason=f"undoable: could not parse hook input ({exc}); review manually.",
            rule="internal-error",
        )
        print(json.dumps(_permission_output(unparseable)))
        return 0

    is_pre_tool_use = payload.get("hook_event_name") == "PreToolUse"
    decision: Decision | None = None
    try:
        decision = evaluate(payload, project_dir=project_dir)
    except Exception as exc:
        print(f"undoable: internal error evaluating hook event: {exc}", file=sys.stderr)
        if is_pre_tool_use:
            decision = Decision(
                tier=_INTERNAL_ERROR_TIER,
                decision=ASK,
                reason=f"undoable: internal error evaluating this action ({exc}); review manually.",
                rule="internal-error",
            )

    try:
        log_event(payload, project_dir=project_dir, decision=decision)
    except Exception as exc:
        print(f"undoable: failed to log hook event: {exc}", file=sys.stderr)

    if decision is not None and decision.decision != ALLOW:
        print(json.dumps(_permission_output(decision)))
    return 0
