from pathlib import Path

from undoable.report.report import generate_report
from undoable.store.db import connect, default_db_path
from undoable.store.events import insert_event
from undoable.store.snapshots import insert_snapshot


def _seed(project_dir: Path) -> None:
    conn = connect(default_db_path(project_dir))
    try:
        insert_event(
            conn,
            session_id="s1",
            hook_event="PreToolUse",
            raw_payload={},
            tool_name="Bash",
            tool_input={"command": "rm -rf /tmp/data"},
            decision="deny",
            risk_tier="dangerous",
            reason="rm with both --recursive and --force can permanently delete a whole tree.",
        )
        insert_event(
            conn,
            session_id="s1",
            hook_event="PreToolUse",
            raw_payload={},
            tool_name="Bash",
            tool_input={"command": "git push origin main"},
            decision="ask",
            risk_tier="risky",
            reason="git push changes shared remote state.",
        )
        insert_event(
            conn,
            session_id="s1",
            hook_event="PreToolUse",
            raw_payload={},
            tool_name="Bash",
            tool_input={"command": "ls -la"},
            decision="allow",
            risk_tier="safe",
        )
        insert_event(conn, session_id="s1", hook_event="SessionStart", raw_payload={})
        insert_snapshot(conn, commit_sha="a" * 40, tree_sha="b" * 40, label="before cleanup")
    finally:
        conn.close()


def test_report_on_empty_project_does_not_crash(tmp_path: Path) -> None:
    report = generate_report(str(tmp_path))
    assert "UNDOABLE Morning Report" in report
    assert "0 action(s) logged" in report


def test_report_counts_actions_by_hook_event(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = generate_report(str(tmp_path))
    assert "4 action(s) logged" in report
    assert "PreToolUse: 3" in report
    assert "SessionStart: 1" in report


def test_report_lists_blocked_actions(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = generate_report(str(tmp_path))
    assert "1 blocked (denied)" in report
    assert "## Blocked" in report
    assert "rm -rf /tmp/data" in report


def test_report_lists_items_needing_review(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = generate_report(str(tmp_path))
    assert "1 flagged for review (asked)" in report
    assert "## Needs review" in report
    assert "git push origin main" in report


def test_report_lists_snapshots(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = generate_report(str(tmp_path))
    assert "1 snapshot(s) created" in report
    assert "## Snapshots" in report
    assert "before cleanup" in report


def test_report_omits_empty_sections(tmp_path: Path) -> None:
    report = generate_report(str(tmp_path))
    assert "## Blocked" not in report
    assert "## Needs review" not in report
    assert "## Snapshots" not in report


def test_report_notes_cost_is_unavailable(tmp_path: Path) -> None:
    report = generate_report(str(tmp_path))
    assert "Total cost: not available" in report


def test_report_since_filters_out_earlier_events(tmp_path: Path) -> None:
    _seed(tmp_path)
    # Every seeded row has a real logged_at; a timestamp far in the future
    # should filter everything out.
    report = generate_report(str(tmp_path), since="9999-01-01T00:00:00+00:00")
    assert "0 action(s) logged" in report
    assert "0 snapshot(s) created" in report


def test_report_since_none_includes_everything(tmp_path: Path) -> None:
    _seed(tmp_path)
    report = generate_report(str(tmp_path), since="0001-01-01T00:00:00+00:00")
    assert "4 action(s) logged" in report
