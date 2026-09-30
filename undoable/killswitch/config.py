import json
from dataclasses import dataclass
from pathlib import Path

DEFAULT_LOOP_THRESHOLD = 3


@dataclass(frozen=True)
class KillSwitchConfig:
    max_actions: int | None = None  # None: no budget limit (off by default)
    loop_threshold: int = DEFAULT_LOOP_THRESHOLD


def _config_path(project_dir: str | Path) -> Path:
    return Path(project_dir) / ".undoable" / "config.json"


def load_config(project_dir: str | Path) -> KillSwitchConfig:
    """Reads .undoable/config.json ({"max_actions": int, "loop_threshold": int}),
    both optional. Missing file, unreadable file, or malformed JSON all fall
    back to defaults rather than raising -- a broken config file must never
    itself become a reason tool calls stop working."""
    path = _config_path(project_dir)
    try:
        data = json.loads(path.read_text())
    except (OSError, ValueError):
        return KillSwitchConfig()
    if not isinstance(data, dict):
        return KillSwitchConfig()
    return KillSwitchConfig(
        max_actions=data.get("max_actions"),
        loop_threshold=data.get("loop_threshold", DEFAULT_LOOP_THRESHOLD),
    )
