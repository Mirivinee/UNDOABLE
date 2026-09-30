"""PostToolUse: format and lint Python files after Claude edits them."""
import json
import subprocess
import sys

path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
if path.endswith(".py"):
    subprocess.run(["ruff", "format", path], capture_output=True)
    result = subprocess.run(["ruff", "check", "--fix", path], capture_output=True, text=True)
    if result.returncode != 0:
        print(result.stdout, file=sys.stderr)
        sys.exit(2)  # shows lint errors to Claude so it fixes them
sys.exit(0)
