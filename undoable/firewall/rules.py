import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SAFE = "safe"
RISKY = "risky"
DANGEROUS = "dangerous"

# These match Claude Code's PreToolUse hookSpecificOutput.permissionDecision
# values exactly, so a Decision can be turned into that JSON with no translation.
ALLOW = "allow"
ASK = "ask"
DENY = "deny"


@dataclass(frozen=True)
class Decision:
    tier: str  # "safe" | "risky" | "dangerous"
    decision: str  # "allow" | "ask" | "deny"
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


# Bash line-continuation ("cmd \<newline>continues") is a no-op that joins two
# physical lines into one logical command; normalizing it away up front keeps
# every segment/flag check below from being defeated by a backslash-newline
# split between e.g. "rm -rf" and "-rf" ending up on separate "lines".
_LINE_CONTINUATION = re.compile(r"\\\r?\n")

# Known limitation, not fixed: this matches "rm" as a bare word anywhere, so
# "docker rm -f <container>" also gets scored by rm's flag logic (a spurious
# "ask", not a missed "deny"). Requiring rm to be at a command position would
# also let a real `rm -rf` inside e.g. a subshell slip through unnoticed --
# for a safety net, an extra prompt is a far smaller cost than a silent miss.
_RM = re.compile(r"\brm\b")
# Any hyphen flag token containing the letter, combined or not: -f, -rf, -fr, -vf, --force.
_FORCE_FLAG = re.compile(r"--force\b|(?<!\S)-[a-zA-Z]*f[a-zA-Z]*(?!\S)")
_RECURSIVE_FLAG = re.compile(r"--recursive\b|(?<!\S)-[a-zA-Z]*[rR][a-zA-Z]*(?!\S)")


def _rm_flags(segment: str) -> tuple[bool, bool]:
    return bool(_FORCE_FLAG.search(segment)), bool(_RECURSIVE_FLAG.search(segment))


_GIT_PUSH = re.compile(r"\bgit\s+push\b")
_FORCE_PUSH_FLAG = re.compile(r"--force(-with-lease)?\b|(?<!\S)-f(?!\S)")
_GIT_RESET_HARD = re.compile(r"\bgit\s+reset\b[^|;&\n]*--hard\b")
_PIPE_TO_SHELL = re.compile(r"\b(curl|wget)\b[^\n]*\|\s*(sudo\s+)?(\S*/)?(bash|sh|zsh)\b")
_DOWNLOAD_THEN_EXEC = re.compile(
    r"\b(curl|wget)\b[^\n]*(?:&&|;|\n)\s*(sudo\s+)?(bash|sh|zsh|python3?|perl|ruby|node)\b"
)
_DROP = re.compile(r"\bDROP\s+(TABLE|DATABASE)\b", re.IGNORECASE)
_CHMOD_RECURSIVE = re.compile(r"\bchmod\b[^|;&\n]*(-R\b|--recursive\b)")

_FIND_DELETE = re.compile(r"\bfind\b[^|;&\n]*-delete\b")
_GIT_CLEAN = re.compile(r"\bgit\s+clean\b")
# "git checkout [<ref>] -- <path>" or bare "git checkout ." discard uncommitted
# changes; "git checkout <branch>" (no "--", no ".") is an ordinary,
# non-destructive branch switch.
_GIT_CHECKOUT_DISCARD = re.compile(
    r"\bgit\s+checkout\s+(?:\S+\s+)?--\s+\S+|\bgit\s+checkout\s+\.(?=\s|$|[|;&])"
)
_GIT_RESTORE = re.compile(r"\bgit\s+restore\b")
_GIT_BRANCH = re.compile(r"\bgit\s+branch\b")
_BRANCH_FORCE_DELETE = re.compile(r"-D\b|--delete\b[^|;&\n]*--force\b|--force\b[^|;&\n]*--delete\b")
# dd's real syntax is "dd if=... of=... [opt=val ...]"; requiring at least one
# key=value token avoids flagging the word "dd" used as an ordinary argument.
_DD = re.compile(r"\bdd\s+(?:[a-zA-Z]+=\S+\s*)+")
_MKFS = re.compile(r"\bmkfs(\.[a-zA-Z0-9]+)?\b")

_DELETE_FROM = re.compile(r"\bDELETE\s+FROM\b", re.IGNORECASE)
_UPDATE_SET = re.compile(r"\bUPDATE\b.*\bSET\b", re.IGNORECASE | re.DOTALL)
_WHERE = re.compile(r"\bWHERE\b", re.IGNORECASE)

# A single ">" (not ">>", which appends) redirects and truncates its target.
# Matching "&" is excluded from the bare-token alternative so "2>&1"
# (duplicating a file descriptor, not writing a file) doesn't produce a
# spurious target. The quoted alternatives come first so a target containing
# spaces ("existing file.txt") isn't truncated at the first space.
_REDIRECT_TARGET = re.compile(r"""(?<!>)>(?!>)\s*(?:"([^"]+)"|'([^']+)'|([^\s|;&<>]+))""")


def _sql_statements(command: str) -> list[str]:
    return [s for s in command.split(";") if s.strip()]


def _redirect_overwrite_target(command: str, cwd: str | None) -> str | None:
    """First ">" redirect target that already exists as a file, or None.

    Requires a cwd to resolve relative paths against; without one, this
    check is skipped rather than guessed at.
    """
    if not cwd:
        return None
    for match in _REDIRECT_TARGET.finditer(command):
        target = next(g for g in match.groups() if g is not None)
        path = Path(target)
        if not path.is_absolute():
            path = Path(cwd) / path
        try:
            if path.is_file():
                return target
        except OSError:
            continue
    return None


def _decision(tier: str, rule: str, reason: str) -> Decision:
    decision = DENY if tier == DANGEROUS else ASK
    return Decision(tier=tier, decision=decision, reason=reason, rule=rule)


def evaluate_command(command: str, cwd: str | None = None) -> Decision:
    """Rule-based risk scoring for a shell command.

    Dangerous commands are denied; risky ones are flagged for the user to
    approve (ask); everything else is safe. This is a known-pattern
    firewall, not an adversarial sandbox -- it catches the documented cases
    (rm -rf, forced pushes, curl-pipe-shell, destructive SQL/git/disk
    commands), not every way to phrase them (aliases, encoded payloads, or
    destructive code written in another language are out of scope for this
    rule set).
    """
    if not command:
        return _ALLOW_SAFE
    command = _LINE_CONTINUATION.sub(" ", command)

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

    if _FIND_DELETE.search(command):
        return _decision(
            DANGEROUS,
            "find-delete",
            "find -delete can remove every file matching its criteria with no undo.",
        )

    for segment in _segments_starting_with(command, _GIT_CLEAN):
        if _FORCE_FLAG.search(segment):
            return _decision(
                DANGEROUS,
                "git-clean-force",
                "git clean -f permanently deletes untracked files with no way back.",
            )

    if _GIT_CHECKOUT_DISCARD.search(command):
        return _decision(
            DANGEROUS,
            "git-checkout-discard",
            "This discards uncommitted changes with no way to get them back.",
        )

    for segment in _segments_starting_with(command, _GIT_RESTORE):
        if "--staged" in segment and "--worktree" not in segment:
            continue  # only touches the index, working tree files are untouched
        return _decision(
            DANGEROUS,
            "git-restore-worktree",
            "git restore overwrites working tree files, discarding uncommitted changes.",
        )

    for segment in _segments_starting_with(command, _GIT_BRANCH):
        if _BRANCH_FORCE_DELETE.search(segment):
            return _decision(
                DANGEROUS,
                "git-branch-force-delete",
                "git branch -D force-deletes a branch even if it has unmerged commits.",
            )

    if _DD.search(command):
        return _decision(
            DANGEROUS,
            "dd",
            "dd can overwrite an entire disk or file with no confirmation and no undo.",
        )

    if _MKFS.search(command):
        return _decision(
            DANGEROUS,
            "mkfs",
            "mkfs formats a filesystem, erasing everything on it.",
        )

    if _DOWNLOAD_THEN_EXEC.search(command):
        return _decision(
            RISKY,
            "download-then-exec",
            "Downloading a script and then running it separately still runs "
            "unreviewed code, same as piping it straight into a shell.",
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

    overwrite_target = _redirect_overwrite_target(command, cwd)
    if overwrite_target:
        return _decision(
            RISKY,
            "redirect-overwrite",
            f"'{overwrite_target}' already exists and would be overwritten.",
        )

    return _ALLOW_SAFE


def evaluate_tool_use(
    tool_name: str, tool_input: dict[str, Any] | None, cwd: str | None = None
) -> Decision:
    """Firewall decision for one tool call. Only Bash is rule-checked so far."""
    if tool_name == "Bash":
        return evaluate_command((tool_input or {}).get("command") or "", cwd=cwd)
    return _ALLOW_SAFE
