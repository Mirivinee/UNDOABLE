# UNDOABLE

> Let your AI coding agent work unattended without fear. If it goes wrong, undo everything in one click.


---

## 1. Problem Statement

AI coding agents (Claude Code, Cursor, and others) no longer just suggest code — they run terminal commands, edit files, install packages, modify databases, and push to git. Developers want to hand over a task and walk away, but today they face two bad choices:

1. **Babysit the agent** — approve every single action, which defeats the purpose of automation and leads to "approval fatigue," where people start approving everything blindly.
2. **Skip permissions entirely** — let the agent run freely and hope nothing goes wrong.

When things go wrong, the damage is real: deleted files, corrupted databases, leaked secrets, broken git history, or malware installed through fake packages. Existing guardrail tools focus mostly on **detecting** attacks. Very little helps developers **recover** when prevention fails, and most solutions target enterprises rather than individual developers.

## 2. Who Faces This Problem

- Individual developers and students using AI coding agents daily
- Small teams without dedicated security staff
- Anyone who wants to run long or overnight agent tasks

## 3. Proposed Solution

A safety layer that sits between the AI agent and the system it acts on. Like a car needs brakes, seatbelts, a dashboard, and insurance, an autonomous agent needs prevention, recovery, limits, and visibility.

### Core Features

| # | Feature | Role | What it does |
|---|---------|------|--------------|
| 1 | **Firewall** | Prevent | Blocks dangerous commands, detects prompt injection in content the agent reads, stops secrets (API keys, `.env` values) from leaving the machine |
| 2 | **Undo Button** ⭐ | Recover | Snapshots state before risky actions; one-click rollback of files, git state, databases, and installed packages |
| 3 | **Package Check** | Supply chain | Verifies every package before install to stop "slopsquatting" (attackers registering package names that AI models hallucinate) |
| 4 | **Kill Switch** | Limits | Stops the agent if it loops on the same error, exceeds a token/cost budget, or touches files outside the project |
| 5 | **Morning Report** | Visibility | Summary of what the agent did, what was blocked, what needs review, and what it cost |

⭐ = signature feature. The undo button is the main differentiator.

## 4. Existing Solutions & Our Differentiation

| Existing tool | What it covers | Gap |
|---------------|----------------|-----|
| Meta LlamaFirewall | Prompt injection, misalignment, insecure code | Prevention only, no recovery |
| NVIDIA NeMo Guardrails | Programmable rails, tool-call checks | Complex setup, aimed at app builders |
| Guardrails AI | Output validation | Not focused on agent actions |
| Azure Prompt Shields, Google Model Armor, Lakera | Injection detection | Cloud/enterprise, paid, prevention only |
| Agent built-in checkpoints | Rewind file edits | Don't cover databases, packages, pushed commits |

**Our angle:** prevention + recovery + limits + reporting in one tool, built for individual developers, running locally.

## 5. Architecture

```
┌───────────────────────────────────────────┐
│               AI Coding Agent             │
└─────────────────────┬─────────────────────┘
                      │ tool call (bash, edit, install...)
                      ▼
┌───────────────────────────────────────────┐
│           Interceptor (hooks layer)       │
│   pre-action hook          post-action hook│
└──────┬──────────────┬──────────────┬──────┘
       ▼              ▼              ▼
  ┌─────────┐   ┌──────────┐   ┌───────────┐
  │Firewall │   │ Package  │   │Kill Switch│
  │         │   │  Check   │   │  Monitor  │
  └────┬────┘   └────┬─────┘   └─────┬─────┘
       └─────── allow / block / ask ─┘
                      │
                      ▼ (if risky and allowed)
            ┌───────────────────┐
            │  Snapshot Engine  │ ← Undo Button
            └─────────┬─────────┘
                      ▼
            ┌───────────────────┐
            │   Event Log (DB)  │ → Morning Report
            └───────────────────┘
```

### Component Details

**Interceptor**
- Uses the agent's hook system (e.g., Claude Code pre/post tool-use hooks) to see every action before and after it runs.
- Decision for each action: `allow`, `block`, or `ask user`.

**Firewall**
- Rule-based command checks (e.g., `rm -rf`, `git push --force`, `curl ... | bash`, `DROP TABLE`).
- Risk scoring: safe / risky / dangerous.
- Prompt-injection scanning of files, web pages, and tool outputs (regex + a small classifier model).
- Secret detection on outgoing data.

**Snapshot Engine (Undo Button)**
- Files: git-based snapshot commits on a hidden ref, or copies of changed files for non-git folders.
- Databases: dumps for SQLite/Postgres before destructive queries.
- Packages: save lockfiles (`package-lock.json`, `requirements.txt`) before installs.
- Rollback: restore a chosen snapshot with one command or click.
- Limitation to document honestly: external side effects (sent emails, remote API calls, already-pushed commits) can be flagged but not fully undone.

**Package Check**
- Confirm the package exists on the registry (npm / PyPI).
- Check age, download count, and maintainer history.
- Flag names that look like typos of popular packages.

**Kill Switch Monitor**
- Detects repeated identical errors (loop detection).
- Tracks token and cost usage against a user-set budget.
- Enforces a project folder boundary.

**Morning Report**
- Reads the event log and generates a Markdown/HTML summary: actions taken, blocked attempts, snapshots created, items needing review, and total cost.

## 6. Suggested Tech Stack

| Part | Option |
|------|--------|
| Core language | Python or TypeScript |
| Agent integration | Claude Code hooks (start with one agent) |
| Event storage | SQLite |
| Injection classifier | Small open model (e.g., a prompt-injection detector from Hugging Face) |
| Snapshots | Git (hidden refs), file copies, DB dump tools |
| Package data | npm and PyPI public registry APIs |
| Report / dashboard | Markdown report first, simple web dashboard later |

## 7. Build Plan

| Phase | Focus | Outcome |
|-------|-------|---------|
| 1 | Interceptor + event log | Every agent action is captured and logged |
| 2 | Firewall (rules first) | Dangerous commands blocked or sent for approval |
| 3 | Snapshot engine + rollback | Files and git state restorable in one step |
| 4 | Package check | Fake/suspicious packages blocked |
| 5 | Kill switch | Loops and budget overruns stop the agent |
| 6 | Morning report | Clean end-of-session summary |
| 7 | Extend undo to databases + packages; add injection classifier | Full signature feature |
| 8 | Testing, attack suite, demo polish | Measured results |

**Priority:** make the **Undo Button** and **Firewall** excellent; keep the other three simple.

## 8. Evaluation Plan

Build an attack and mistake test suite and run the agent with and without the safety net.

| Scenario | Expected result |
|----------|-----------------|
| Malicious instruction hidden in a README | Injection detected, action blocked |
| Agent tries to install a non-existent / typo package | Install blocked |
| Agent runs a destructive delete | Snapshot taken, rollback restores everything |
| Agent tries to send `.env` contents to a URL | Secret leak blocked |
| Agent loops on the same failing fix | Kill switch stops it |
| Normal, safe coding task | Runs without unnecessary interruptions |

**Metrics**
- Attack block rate
- Successful rollback rate
- False positives (safe actions wrongly blocked or questioned)
- Number of approval prompts per session (lower is better, shows reduced approval fatigue)
- Added latency per action

## 9. Demo Script

1. Give the agent a normal task in a project containing a planted malicious file and a request that tempts it to install a fake package.
2. Show the firewall catching the hidden instruction.
3. Show the package check blocking the fake package.
4. Let the agent make a destructive mistake, then restore everything with one click.
5. End with the morning report summarizing the session.

## 10. Risks & Limitations

- Prevention is never perfect; that is why recovery exists.
- External side effects (emails sent, remote APIs called, commits already pushed) can be flagged but not always reversed.
- Too many interruptions would recreate approval fatigue; tuning the risk scoring is important.
- Initial version supports one agent only.

## 11. Future Scope

- **Learning approvals:** learn which actions the user always approves and stop asking about them.
- **Team policies:** shared safety rules across a team's agents.
- **Multi-agent support:** Cursor, Codex, and other agents beyond Claude Code.
- **MCP server scanner:** check MCP servers for risky tools before installation.
