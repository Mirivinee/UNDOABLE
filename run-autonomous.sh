#!/usr/bin/env bash
# Runs Claude Code task-by-task through PROGRESS.md.
# Claude builds + commits; this script runs tests and pushes only if they pass.
set -uo pipefail

MAX_RUNS="${MAX_RUNS:-20}"
BRANCH="${BRANCH:-main}"

if [ ! -f /.dockerenv ]; then
  echo "Refusing to run outside a container. See README-AUTONOMOUS.md." >&2
  exit 1
fi
if [ -z "${GH_TOKEN:-}" ]; then
  echo "GH_TOKEN is not set (fine-grained token for this repo only)." >&2
  exit 1
fi

git config user.name  "${GIT_NAME:-undoable-bot}"
git config user.email "${GIT_EMAIL:-undoable-bot@users.noreply.github.com}"
REMOTE="https://x-access-token:${GH_TOKEN}@github.com/Mirivinee/UNDOABLE.git"

remaining() { grep -c '^- \[ \]' PROGRESS.md || true; }

PROMPT='Read CLAUDE.md and PROGRESS.md. Complete the FIRST unchecked task only, following the Autonomous mode rules. Use the test-runner subagent to run tests. When tests pass, tick the task and commit. Then stop.'

mkdir -p logs
for i in $(seq 1 "$MAX_RUNS"); do
  before=$(remaining)
  [ "$before" -eq 0 ] && { echo "All tasks done."; break; }
  echo "=== Run $i — $before tasks left ==="

  claude -p "$PROMPT" --dangerously-skip-permissions --max-turns 60 | tee -a logs/run.log

  pytest -q; code=$?
  if [ "$code" -ne 0 ] && [ "$code" -ne 5 ]; then   # 5 = no tests collected yet
    echo "Tests failing after run $i. Not pushing. Stopping for human review." >&2
    exit 1
  fi
  git push "$REMOTE" "HEAD:$BRANCH" 2>&1 | sed "s/${GH_TOKEN}/***/g"

  after=$(remaining)
  if grep -q '^## Blocked' PROGRESS.md && ! grep -A1 '^## Blocked' PROGRESS.md | grep -q '(none)'; then
    echo "Claude reported a blocker. Stopping." >&2; exit 1
  fi
  if [ "$after" -ge "$before" ]; then
    echo "No progress in run $i. Stopping to avoid a loop." >&2; exit 1
  fi
done
