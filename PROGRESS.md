# Progress

## Current phase: 1 — Interceptor + event log

- [x] Project skeleton (pyproject, package folders, ruff, pytest)
- [x] SQLite event log (`store/`)
- [x] Interceptor reads hook JSON from stdin, logs every action
- [x] Firewall: rule-based blocking of dangerous commands
- [x] Snapshot engine: git-based snapshot + rollback
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
- Firewall (`firewall/rules.py`) scores Bash commands as safe/risky/dangerous by regex over shell-separator-delimited segments (so chained commands like `a && rm -rf /` are still caught); dangerous is blocked, risky is allowed but logged with a reason. Rule set matches the spec's named examples (rm -rf, git push --force, git reset --hard, curl|bash, DROP TABLE/DATABASE) plus a few directly analogous risky ones (plain git push, DELETE/UPDATE without WHERE, chmod -R, partial rm flags). It does not catch aliases, command substitution, or destructive logic written in another language -- documented as a known limit, not silently assumed away.
- Added an `events.risk_tier` column alongside `decision`/`reason` so safe/risky/dangerous is recorded even when the decision itself is "allow".
- Superseded below: exit-code blocking (exit 2) was replaced with Claude Code's documented `hookSpecificOutput.permissionDecision` JSON, which has a real "ask" -- see the next entry.
- Confirmed against the Claude Code hooks docs: PreToolUse can return `{"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "allow"|"deny"|"ask"|"defer", "permissionDecisionReason": "..."}}` on stdout with exit 0. Exit 2 always forces a hard block regardless of any JSON printed, which would make "ask" impossible, so `undoable hook` now always exits 0 and expresses the decision purely through this JSON. `Decision.decision` in `firewall/rules.py` now takes the values `allow`/`ask`/`deny` directly (dangerous->deny, risky->ask, safe->allow) so no translation is needed at the interceptor boundary. For "allow" nothing is printed at all (matching Claude Code's own convention), so Claude Code's normal permission flow still applies instead of us force-approving every safe command.
- Fail-safe on internal error is now literally "ask" (not a stand-in block): if a PreToolUse decision can't be parsed or evaluated, `undoable hook` emits `permissionDecision: "ask"` with the error as the reason. Logging is now a separate try/except from evaluating, so a failure writing to the event log (e.g. DB locked) can never downgrade an already-computed deny/ask back to something weaker -- a security review caught this as a real deny->ask escalation path (see below).
- Added more dangerous/risky rules: `find -delete`, `git clean -f`, `git checkout -- <path>` / bare `git checkout .` / `git checkout <ref> -- <path>`, `git restore <path>` (unless `--staged` without `--worktree`), `git branch -D`, `dd` (requires its real `key=value` syntax to avoid flagging the bare word), `mkfs`, and a risky check for a `>` redirect that would overwrite a file that already exists (only checked when a cwd is available -- skipped rather than guessed at otherwise).
- Ran a security review (this project's `security-reviewer` role, via a general-purpose subagent since it isn't registered as a named subagent type in this session) against `firewall/rules.py` and `interceptor/hooks.py`. Fixed everything it found: a path-qualified shell (`| /bin/bash`) bypassed curl-pipe-shell; bash line-continuation (`cmd \<newline>`) defeated segment/flag scanning for rm, git reset --hard, git clean -f, find -delete, chmod -R, and git branch -D (fixed once, at the top of `evaluate_command`, by normalizing `\<newline>` away before any matching); `git checkout <ref> -- <path>` wasn't recognized as a discard; `UPDATE ... SET` missed multi-line SQL because `.` doesn't cross `\n` without `re.DOTALL`; unparseable stdin used to silently allow (now asks, since we can't rule out a mangled PreToolUse call); a `log_event` failure could downgrade an already-correct deny to ask (fixed by separating evaluate/log into their own try blocks); a quoted redirect target containing a space was truncated at the first space, missing real overwrites. Also added a risky "download then exec" rule (`curl -o x.sh ... && bash x.sh`) since it's the same threat as curl-pipe-shell one step removed. Left one low-priority finding unfixed on purpose: bare `\brm\b` also matches non-shell `rm` subcommands like `docker rm -f <container>` (spurious "ask", not a missed "deny") -- tightening it to a command position would risk a real `rm -rf` inside a subshell slipping through silently, and for a safety net a false positive is far cheaper than a false negative.
- Snapshot engine (`snapshot/git_snapshot.py`) is git-only for this task (file copies for non-git folders are out of scope here). `create_snapshot` captures the whole working tree -- tracked, modified, and untracked-but-not-ignored files -- as a commit on a hidden `refs/undoable/snapshots/<id>` ref, built via a throwaway `GIT_INDEX_FILE` so the repo's real index/HEAD/branch are never touched; the commit gets its own fixed author/committer identity so it never fails on a missing `user.name`/`user.email`. `.undoable/` (our own store) is explicitly excluded from every snapshot via a pathspec, not just gitignore-dependent, so the DB never gets embedded in its own history. `rollback` restores snapshot-tracked files via `git read-tree --reset -u` on the real index, then separately deletes anything present now that wasn't in the snapshot (a tree-diff against a freshly captured "current" tree) -- known limit: files still untracked and gitignored at rollback time are left alone entirely, by design, so the tool never touches build output/node_modules/etc.
- Found and fixed a real safety bug while testing the above, not just a flaky test: `_require_git_repo` originally only checked "is this inside *some* git work tree" (`git rev-parse --is-inside-work-tree`), which is true for any subdirectory of any ancestor repo. On the dev machine this surfaced for real -- pytest's `tmp_path` lives under the user's home directory, which itself turned out to be a (empty, thankfully) git repo, so `_require_git_repo` didn't reject it. Since `read-tree --reset -u` operates on the whole index with no path scoping, this could have reset an unrelated ancestor repo's real working tree instead of the intended one. Now requires exact equality with `git rev-parse --show-toplevel`, i.e. project_dir must be a repo's root, not merely inside one; added a portable regression test (subdirectory of a fresh test repo, not dependent on any machine's real home directory) so this doesn't need a lucky environment to catch again.

## Blocked
- (none)
