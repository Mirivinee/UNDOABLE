# UNDOABLE

Safety net for autonomous AI coding agents: prevent dangerous actions, undo mistakes, check packages, stop runaway sessions, and report what happened.

Full spec: `docs/PROJECT.md`. Progress: `PROGRESS.md` (read it first, update it after finishing a task).

## Stack
- Python 3.11+, CLI with `typer`, storage in SQLite
- Tests: `pytest` | Lint/format: `ruff`
- Integrates with Claude Code through hooks (PreToolUse, PostToolUse, SessionStart, Stop, SessionEnd)

## Layout
```
undoable/
  interceptor/   # hook entry points, allow/block/ask decisions
  firewall/      # command rules, risk scoring, injection + secret detection
  snapshot/      # snapshot + rollback (git, files, sqlite/postgres, lockfiles)
  packages/      # npm/PyPI existence, age, typo-squat checks
  killswitch/    # loop detection, budget, folder boundary
  report/        # morning report from event log
  store/         # SQLite event log
tests/
  attacks/       # attack + mistake scenarios (the evaluation suite)
sandbox/         # disposable test projects; the ONLY place destructive tests run
```

## Commands
- Install: `pip install -e ".[dev]"`
- Test: `pytest -q` (single file: `pytest tests/path_test.py -q`)
- Attack suite: `pytest tests/attacks -q`
- Lint/format: `ruff check . --fix && ruff format .`

## Rules
- Never run destructive commands (rm, DROP, force push, resets) outside `sandbox/`.
- Never read or print `.env` or real credentials. Tests use fake secrets from `tests/fixtures/`.
- Every firewall rule and every rollback path needs a test in `tests/`.
- Hook scripts must be fast (<200 ms for allow decisions) and fail safe: on internal error, choose `ask`, never silent `allow`.
- Keep modules independent; they communicate only through `store/` and the interceptor.
- Prefer small, focused changes. Run tests before saying a task is done.

## Working style
- For codebase-wide searches, test runs with long output, or research, use a subagent and return only the summary.
- Ask before adding new dependencies.
- After each finished task, tick it in `PROGRESS.md` and note any key decision in one line.

## Autonomous mode
- Work on exactly ONE unchecked task from `PROGRESS.md` per run, top to bottom.
- Finish it with passing tests, tick it in `PROGRESS.md`, then commit:
  `git add -A && git commit -m "<phase>: <short description>"`
- Do NOT push; the runner script pushes only after tests pass.
- If stuck after 3 attempts, add a line under `## Blocked` in `PROGRESS.md` explaining why, commit, and stop.
- The repo is public: never commit secrets, tokens, or real personal data.
