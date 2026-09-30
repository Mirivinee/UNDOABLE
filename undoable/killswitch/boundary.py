import os
from pathlib import Path
from typing import Any

# Claude Code always supplies these as absolute paths, so checking them is a
# reliable signal -- unlike trying to regex a path out of an arbitrary Bash
# command string, which is a known limit documented on find_out_of_bounds_path.
_FILE_PATH_TOOLS = {"Read", "Write", "Edit", "Glob", "Grep", "NotebookEdit"}
_PATH_KEYS = ("file_path", "path", "notebook_path")


def _tool_paths(tool_name: str, tool_input: dict[str, Any] | None) -> list[str]:
    if tool_name not in _FILE_PATH_TOOLS:
        return []
    tool_input = tool_input or {}
    return [tool_input[key] for key in _PATH_KEYS if isinstance(tool_input.get(key), str)]


def find_out_of_bounds_path(
    project_dir: str, tool_name: str, tool_input: dict[str, Any] | None
) -> str | None:
    """First path this call touches that resolves outside project_dir, or
    None. Only checks structured file-path tool inputs (Read/Write/Edit/
    Glob/Grep/NotebookEdit) -- Bash commands aren't scanned for path
    arguments (cd, relative traversal, etc.); a known, documented limit
    rather than a fragile guess at what looks like a path in free-form text.
    """
    root = os.path.normcase(str(Path(project_dir).resolve()))
    for raw_path in _tool_paths(tool_name, tool_input):
        try:
            resolved = os.path.normcase(str(Path(raw_path).resolve()))
        except OSError:
            continue
        if resolved != root and not resolved.startswith(root + os.sep):
            return raw_path
    return None
