# Progress

## Current phase: 1 — Interceptor + event log

- [x] Project skeleton (pyproject, package folders, ruff, pytest)
- [ ] SQLite event log (`store/`)
- [ ] Interceptor reads hook JSON from stdin, logs every action
- [ ] Firewall: rule-based blocking of dangerous commands
- [ ] Snapshot engine: git-based snapshot + rollback
- [ ] Package check: npm/PyPI existence + typo detection
- [ ] Kill switch: loop detection + budget + folder boundary
- [ ] Morning report
- [ ] Undo for databases and lockfiles
- [ ] Prompt-injection classifier
- [ ] Attack suite + metrics + demo

## Decisions
- Flat layout: package `undoable/` lives at repo root beside `tests/`; hatchling build backend, console script `undoable = undoable.cli:app`.
- CLI: single Typer app in `undoable/cli.py`; future hook entry point will be one dispatching command (e.g. `undoable hook`) used for all PreToolUse/PostToolUse/SessionStart/Stop/SessionEnd wiring, not one subcommand per hook event.
- Event log DB will live per-project at `.undoable/undoable.db` (decided ahead of the next task, "SQLite event log").

## Blocked
- (none)
