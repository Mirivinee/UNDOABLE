"""Ties together typo-squat detection and registry existence checks for
`pip install` / `npm install` commands found in a Bash tool call.

Deliberately narrow in scope, matching the checklist item this implements:
only pip/npm install invocations are recognized (not yarn/pnpm/poetry), and
only simple registry package specs (name, name==version, name[extra],
@scope/name@version) -- VCS URLs, local paths, and requirements-file
contents are out of scope here.
"""

import re
import shlex
from dataclasses import dataclass

from undoable.packages.registry import Fetcher, check_npm_exists, check_pypi_exists, default_fetch
from undoable.packages.typosquat import POPULAR_NPM, POPULAR_PYPI, find_typosquat_match

SAFE = "safe"
ASK = "ask"

_SEGMENT_BREAK = re.compile(r"[|;&\n]")


def _segments_starting_with(command: str, keyword: re.Pattern[str]) -> list[str]:
    segments = []
    for match in keyword.finditer(command):
        rest = command[match.start() :]
        end = _SEGMENT_BREAK.search(rest)
        segments.append(rest[: end.start()] if end else rest)
    return segments


@dataclass(frozen=True)
class PackageFinding:
    package: str
    ecosystem: str  # "pypi" | "npm"
    exists: bool | None  # None: couldn't be determined
    typosquat_of: str | None


@dataclass(frozen=True)
class PackageCheckResult:
    decision: str  # "safe" | "ask"
    reason: str | None
    findings: list[PackageFinding]


_PIP_INSTALL = re.compile(r"\b(?:python3?\s+-m\s+)?pip3?\s+install\b")
_PIP_VALUE_FLAGS = {
    "-r", "--requirement", "-c", "--constraint", "-e", "--editable",
    "-i", "--index-url", "--extra-index-url", "-t", "--target",
}  # fmt: skip
_PIP_VERSION_SPLIT = re.compile(r"[<>=!~\[]")


def extract_pip_packages(command: str) -> list[str]:
    names = []
    for segment in _segments_starting_with(command, _PIP_INSTALL):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        # Skip the leading "python -m pip install" / "pip install" words.
        start = 0
        for i, tok in enumerate(tokens):
            if tok in ("install",):
                start = i + 1
                break
        skip_next = False
        for tok in tokens[start:]:
            if skip_next:
                skip_next = False
                continue
            if tok.startswith("-"):
                flag = tok.split("=", 1)[0]
                if flag in _PIP_VALUE_FLAGS and "=" not in tok:
                    skip_next = True
                continue
            name = _PIP_VERSION_SPLIT.split(tok, 1)[0].strip()
            if not name or "/" in name or name.startswith(("git+", "http:", "https:")):
                continue
            names.append(name)
    return names


_NPM_INSTALL = re.compile(r"\bnpm\s+(?:install|i)\b")
_NPM_FLAG_RE = re.compile(r"^-")


def _npm_package_name(token: str) -> str | None:
    if token.startswith("@"):
        second_at = token.find("@", 1)
        name = token[:second_at] if second_at != -1 else token
        # A scoped package is exactly "@scope/name" -- one slash, not zero
        # (malformed) or more (that's a path, e.g. "@babel/core/lib/x").
        return name if name.count("/") == 1 else None
    name = token.split("@", 1)[0]
    if not name or "/" in name:
        return None
    return name


def extract_npm_packages(command: str) -> list[str]:
    names = []
    for segment in _segments_starting_with(command, _NPM_INSTALL):
        try:
            tokens = shlex.split(segment)
        except ValueError:
            continue
        start = 0
        for i, tok in enumerate(tokens):
            if tok in ("install", "i"):
                start = i + 1
                break
        for tok in tokens[start:]:
            if _NPM_FLAG_RE.match(tok):
                continue
            name = _npm_package_name(tok)
            if name:
                names.append(name)
    return names


def _check_one(name: str, ecosystem: str, fetch: Fetcher, check_existence: bool) -> PackageFinding:
    popular = POPULAR_PYPI if ecosystem == "pypi" else POPULAR_NPM
    typosquat_of = find_typosquat_match(name, popular)
    exists = None
    if check_existence:
        checker = check_pypi_exists if ecosystem == "pypi" else check_npm_exists
        exists = checker(name, fetch=fetch)
    return PackageFinding(
        package=name, ecosystem=ecosystem, exists=exists, typosquat_of=typosquat_of
    )


def evaluate_command(
    command: str,
    *,
    pypi_fetch: Fetcher = default_fetch,
    npm_fetch: Fetcher = default_fetch,
    check_existence: bool = True,
) -> PackageCheckResult | None:
    """None if the command isn't a recognized pip/npm install at all."""
    findings = [
        _check_one(name, "pypi", pypi_fetch, check_existence)
        for name in extract_pip_packages(command)
    ]
    findings += [
        _check_one(name, "npm", npm_fetch, check_existence)
        for name in extract_npm_packages(command)
    ]
    if not findings:
        return None

    concerning = [f for f in findings if f.typosquat_of or f.exists is False]
    if not concerning:
        return PackageCheckResult(decision=SAFE, reason=None, findings=findings)

    reasons = []
    for f in concerning:
        if f.typosquat_of:
            reasons.append(
                f"'{f.package}' ({f.ecosystem}) closely resembles the popular package "
                f"'{f.typosquat_of}' -- possible typosquat."
            )
        elif f.exists is False:
            reasons.append(
                f"'{f.package}' ({f.ecosystem}) does not exist on the registry -- "
                "possibly a hallucinated package name."
            )
    return PackageCheckResult(decision=ASK, reason=" ".join(reasons), findings=findings)
