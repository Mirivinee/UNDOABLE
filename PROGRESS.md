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

## Phase 9 — Smarter approvals (v1.5)
- [ ] Impact preview: before risky actions, show what will be affected (file count/names for bash rm/mv, row counts for SQL DELETE/UPDATE/DROP, packages changed for installs)
- [ ] Phone approvals: send risky-action approvals with impact preview via ntfy; approve/deny from phone; timeout = deny; off by default
- [ ] Learning approvals: remember actions the user always approves (per project, per pattern) and stop asking; never auto-learn "dangerous" tier; `undoable approvals list/forget`
- [ ] Local dashboard: `undoable dashboard` serves a localhost page with the timeline, blocked actions, snapshots, and a restore button

## Phase 10 — Tamper-proof audit log ("flight recorder")
- [ ] Hash-chain every event (each row stores hash of previous row + its own content)
- [ ] `undoable verify` detects any altered, deleted, or inserted event and reports where
- [ ] Record who approved each action (user, learned rule, phone) and why it was allowed/blocked
- [ ] `undoable export --audit` produces a signed JSON + readable HTML audit report for a session or date range

## Phase 11 — Beyond the laptop: undo for external services (v2)
- [ ] MCP proxy: sits between the agent and MCP servers, logs every MCP tool call into the same event log
- [ ] Action classifier: label each tool as reversible / compensatable / irreversible (config file with defaults + override)
- [ ] Reversible: snapshot "before" state and restore on undo
- [ ] Compensatable: record the inverse action (e.g. close issue ↔ reopen issue, create event ↔ delete event) and run it on undo
- [ ] Irreversible: hold in a delay window ("undo send", default 60s) or require approval with impact preview
- [ ] Reference integration 1: GitHub (issues, PRs, branches, comments)
- [ ] Reference integration 2: Slack or Gmail
- [ ] Unified timeline: files, DB, packages, git, and external actions undoable from one `undoable rewind`

## Phase 12 — Collective security ("immune system")
- [ ] Attack fingerprints: when the firewall blocks something, create an anonymized fingerprint (hash of pattern, no code or personal data)
- [ ] Opt-in sharing: `undoable intel share` sends fingerprints to a feed; off by default, clearly documented
- [ ] Feed sync: `undoable intel update` downloads the latest known-bad packages, injection patterns, and malicious MCP servers
- [ ] Simple feed server (can be a static JSON file in a GitHub repo for the demo)

## Phase 13 — Safety score & reports
- [ ] Safety score per session/project: attempted dangerous actions, blocked, undone, approvals, near-misses
- [ ] Trend report over time (weekly)
- [ ] Compliance-style report: what was logged, blocked, approved, and verified (uses Phase 10 audit data)

## Phase 14 — Pre-install scanners
- [ ] MCP server scanner: before installing, inspect tool list and descriptions for risky capabilities and hidden instructions; show a risk rating
- [ ] Plugin scanner: same for Claude Code plugins (hooks, commands, bundled MCP servers)
- [ ] Source trust info: publisher, repo age, stars, last update, official vs community

## Phase 15 — Teams & multi-agent
- [ ] Team policies: shared policy file (blocked commands, protected paths, approval rules) loaded from repo or URL
- [ ] Policy enforcement report: which rules fired, per developer
- [ ] Adapter layer so the core works beyond Claude Code
- [ ] Second agent adapter (e.g. Cursor, Codex, or Gemini CLI — whichever exposes pre/post action hooks)

## Phase 16 — Launch
- [ ] README with install, 60-second quickstart, and GIF demo
- [ ] Landing page (single HTML page: problem, how it works, demo video, install command)
- [ ] Demo script: attack suite run with and without UNDOABLE, plus a full-timeline rewind across files, DB, git, and GitHub
- [ ] Publish package to PyPI
- [ ] Final metrics: block rate, rollback success rate, false positives, approval prompts per session, added latency

## Decisions
- Flat layout: package `undoable/` lives at repo root beside `tests/`; hatchling build backend, console script `undoable = undoable.cli:app`.
- CLI: single Typer app in `undoable/cli.py`; future hook entry point will be one dispatching command (e.g. `undoable hook`) used for all PreToolUse/PostToolUse/SessionStart/Stop/SessionEnd wiring, not one subcommand per hook event.
- Event log DB lives per-project at `.undoable/undoable.db`, WAL mode, single `events` table generic enough for all five hook types (nullable tool_* columns) plus a verbatim `raw_payload` column so nothing is lost if Claude Code's hook JSON grows new fields.
- Interceptor is one dispatching command, `undoable hook`, used for every hook event; it reads stdin, dispatches on `hook_event_name`, and always exits 0. Phase 1 has no firewall, so there's no decision to enforce -- on malformed input it logs the error to stderr and does nothing else, rather than inventing a fail-safe "ask" that has no decision engine behind it yet.

## Blocked
- (none)
