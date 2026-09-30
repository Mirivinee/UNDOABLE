import re
from dataclasses import dataclass
from typing import Any

SAFE = "safe"
RISKY = "risky"
DANGEROUS = "dangerous"

ALLOW = "allow"
BLOCK = "block"


@dataclass(frozen=True)
class Decision:
    tier: str  # "safe" | "risky" | "dangerous"
    decision: str  # "allow" | "block"
    reason: str | None
    rule: str | None


_ALLOW_SAFE = Decision(tier=SAFE, decision=ALLOW, reason=None, rule=None)

# A chained command ("a && b", "a; b", "a | b") is split on these separators
# so a rule only sees the piece of the line it's meant to judge, not
# whatever else was chained around it.
_SEGMENT_BREAK = re.compile(r"[|;&\n]")


def _segments_starting_with(command: str, keyword: re.Pattern[str]) -> list[str]:
    segments = []
    for match in keyword.finditer(command):
        rest = command[match.start() :]
        end = _SEGMENT_BREAK.search(rest)
        segments.append(rest[: end.start()] if end else rest)
    return segments


_RM = re.compile(r"\brm\b")
# Any hyphen flag token containing the letter, combined or not: -f, -rf, -fr, -vf, --force.
_FORCE_FLAG = re.compile(r"--force\b|(?<!\S)-[a-zA-Z]*f[a-zA-Z]*(?!\S)")
_RECURSIVE_FLAG = re.compile(r"--recursive\b|(?<!\S)-[a-zA-Z]*[rR][a-zA-Z]*(?!\S)")


def _rm_flags(segment: str) -> tuple[bool, bool]:
    return bool(_FORCE_FLAG.search(segment)), bool(_RECURSIVE_FLAG.search(segment))


_GIT_PUSH = re.compile(r"\bgit\s+push\b")
_FORCE_PUSH_FLAG = re.compile(r"--force(-with-lease)?\b|(?<!\S)-f(?!\S)")
_GIT_RESET_HARD = re.compile(r"\bgit\s+reset\b[^|;&\n]*--hard\b")
_PIPE_TO_SHELL = re.compile(r"\b(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(bash|sh|zsh)\b")
_DROP = re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE)
_CHMOD_RECURSIVE = re.compile(r"\bchmod\b[^|;&\n]*(-R\b|--recursive\b)")

_DELETE_FROM = re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)
_UPDATE_SET = re.compile(r"\bUPDATE\b.*\bSET\b", re.IGNORECASE)
_WHERE = re.compile(r"\bWHERE\b", re.IGNORECASE)


def _sql_statements(command: str) -> list[str]:
    return [s for s in command.split(";") if s.strip()]


def _decision(tier: str, rule: str, reason: str) -> Decision:
    decision = BLOCK if tier == DANGEROUS else ALLOW
    return Decision(tier=tier, decision=decision, reason=reason, rule=rule)


def evaluate_command(command: str) -> Decision:
    """Rule-based risk scoring for a shell command.

    Dangerous commands are blocked; risky ones are allowed but flagged with a
    reason; everything else is safe. This is a known-pattern firewall, not an
    adversarial sandbox -- it catches the documented cases (rm -rf, forced
    pushes, curl-pipe-shell, destructive SQL), not every way to phrase them
    (aliases, encoded payloads, or destructive code written in another
    language are out of scope for this rule set).
    """
    if not command:
        return _ALLOW_SAFE

    for segment in _segments_starting_with(command, _RM):
        force, recursive = _rm_flags(segment)
        if force and recursive:
            return _decision(
                DANGEROUS,
                "rm-recursive-force",
                "rm with both --recursive and --force can permanently delete an "
                "entire directory tree.",
            )

    if _GIT_RESET_HARD.search(command):
        return _decision(
            DANGEROUS,
            "git-reset-hard",
            "git reset --hard discards uncommitted work with no way back.",
        )

    for segment in _segments_starting_with(command, _GIT_PUSH):
        if _FORCE_PUSH_FLAG.search(segment):
            return _decision(
                DANGEROUS,
                "git-push-force",
                "A force push can overwrite remote history other people depend on.",
            )

    if _PIPE_TO_SHELL.search(command):
        return _decision(
            DANGEROUS,
            "curl-pipe-shell",
            "Piping a downloaded script straight into a shell runs unreviewed code.",
        )

    if _DROP.search(command):
        return _decision(
            DANGEROUS,
            "sql-drop",
            "DROP TABLE/DATABASE permanently deletes data and schema.",
        )

    for segment in _segments_starting_with(command, _GIT_PUSH):
        return _decision(RISKY, "git-push", "git push changes shared remote state.")

    for statement in _sql_statements(command):
        if (_DELETE_FROM.search(statement) or _UPDATE_SET.search(statement)) and not (
            _WHERE.search(statement)
        ):
            return _decision(
                RISKY,
                "sql-mutation-no-where",
                "DELETE/UPDATE without a WHERE clause affects every row in the table.",
            )

    for segment in _segments_starting_with(command, _RM):
        force, recursive = _rm_flags(segment)
        if force or recursive:
            return _decision(
                RISKY,
                "rm-partial-flag",
                "rm with -f or -r alone can still delete more than intended.",
            )

    if _CHMOD_RECURSIVE.search(command):
        return _decision(
            RISKY,
            "chmod-recursive",
            "Recursive permission changes can expose or lock out an entire directory tree.",
        )

    return _ALLOW_SAFE


def evaluate_tool_use(tool_name: str, tool_input: dict[str, Any] | None) -> Decision:
    """Firewall decision for one tool call. Only Bash is rule-checked so far."""
    if tool_name == "Bash":
        return evaluate_command((tool_input or {}).get("command") or "")
    return _ALLOW_SAFE
