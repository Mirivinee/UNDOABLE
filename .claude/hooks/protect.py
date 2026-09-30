"""PreToolUse guard for developing UNDOABLE.
Blocks .env access and destructive shell commands outside sandbox/.
Exit code 2 blocks the tool call and shows stderr to Claude."""
import json
import re
import sys

data = json.load(sys.stdin)
tool = data.get("tool_name", "")
inp = data.get("tool_input", {})

def block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)

path = inp.get("file_path", "")
if re.search(r"(^|/)\.env(\.|$)", path):
    block("Blocked: .env files are off-limits. Use fake secrets in tests/fixtures/.")

if tool == "Bash":
    cmd = inp.get("command", "")
    if re.search(r"\.env\b", cmd):
        block("Blocked: shell access to .env files.")
    destructive = re.search(
        r"\brm\s+-[a-z]*r|\bgit\s+push\s+.*--force|\bgit\s+reset\s+--hard|\bDROP\s+(TABLE|DATABASE)",
        cmd, re.IGNORECASE,
    )
    if re.search(r"\bgit\s+push\b", cmd):
        block("Blocked: pushing is done by the runner script after tests pass.")
    if destructive and "sandbox/" not in cmd:
        block("Blocked: destructive commands are only allowed inside sandbox/.")

sys.exit(0)
