# Progress

## Current phase: 1 — Interceptor + event log

- [x] Project skeleton (pyproject, package folders, ruff, pytest)
- [x] SQLite event log (`store/`)
- [x] Interceptor reads hook JSON from stdin, logs every action
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
- Event log DB lives per-project at `.undoable/undoable.db`, WAL mode, single `events` table generic enough for all five hook types (nullable tool_* columns) plus a verbatim `raw_payload` column so nothing is lost if Claude Code's hook JSON grows new fields.
- Interceptor is one dispatching command, `undoable hook`, used for every hook event; it reads stdin, dispatches on `hook_event_name`, and always exits 0. Phase 1 has no firewall, so there's no decision to enforce -- on malformed input it logs the error to stderr and does nothing else, rather than inventing a fail-safe "ask" that has no decision engine behind it yet.

## Blocked
- (none)
