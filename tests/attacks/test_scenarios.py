from pathlib import Path

from undoable.attacks.scenarios import (
    ScenarioResult,
    run_all,
    scenario_destructive_mistake_then_rollback,
    scenario_injected_readme,
    scenario_loop_detected,
    scenario_normal_task_is_not_interrupted,
    scenario_secret_exfiltration,
    scenario_typosquat_install,
    summarize,
)


def test_injected_readme_is_flagged(tmp_path: Path) -> None:
    assert scenario_injected_readme(tmp_path).status == "pass"


def test_typosquat_install_is_flagged(tmp_path: Path) -> None:
    assert scenario_typosquat_install(tmp_path).status == "pass"


def test_secret_exfiltration_is_marked_not_implemented(tmp_path: Path) -> None:
    result = scenario_secret_exfiltration(tmp_path)
    assert result.status == "not_implemented"
    assert result.detail


def test_destructive_mistake_is_rolled_back(tmp_path: Path) -> None:
    result = scenario_destructive_mistake_then_rollback(tmp_path)
    assert result.status == "pass"
    assert (tmp_path / "important.txt").read_text() == "original content"


def test_loop_is_detected(tmp_path: Path) -> None:
    assert scenario_loop_detected(tmp_path).status == "pass"


def test_normal_task_runs_uninterrupted(tmp_path: Path) -> None:
    assert scenario_normal_task_is_not_interrupted(tmp_path).status == "pass"


def test_run_all_returns_one_result_per_scenario(tmp_path: Path) -> None:
    results = run_all(tmp_path)
    assert len(results) == 6
    assert {r.name for r in results} == {
        "injected_readme",
        "typosquat_install",
        "secret_exfiltration",
        "destructive_mistake_then_rollback",
        "loop_detected",
        "normal_task_is_not_interrupted",
    }


def test_summarize_computes_block_rate_excluding_not_implemented() -> None:
    results = [
        ScenarioResult("a", "attack", "pass", "x", 10.0),
        ScenarioResult("b", "attack", "fail", "x", 10.0),
        ScenarioResult("c", "attack", "not_implemented", "x", 0.0),
    ]
    report = summarize(results)
    assert "Attack block/flag rate: 1/2 (50%)" in report


def test_summarize_computes_rollback_rate() -> None:
    results = [
        ScenarioResult("r1", "rollback", "pass", "x", 5.0),
        ScenarioResult("r2", "rollback", "pass", "x", 5.0),
    ]
    report = summarize(results)
    assert "Rollback success rate: 2/2 (100%)" in report


def test_summarize_counts_false_positives() -> None:
    results = [
        ScenarioResult("s1", "safe", "fail", "unexpectedly flagged", 1.0),
    ]
    report = summarize(results)
    assert "False positives on safe tasks: 1" in report


def test_summarize_lists_every_scenario_with_its_status() -> None:
    results = [ScenarioResult("my_scenario", "attack", "pass", "detail text", 1.5)]
    report = summarize(results)
    assert "[PASS] my_scenario (attack): detail text" in report


def test_summarize_handles_no_scenarios_without_crashing() -> None:
    report = summarize([])
    assert "Attack block/flag rate: 0/0 (0%)" in report
