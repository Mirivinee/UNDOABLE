"""Prompt-injection scanning for text an agent reads (file contents, web
pages, command output).

This is a regex/keyword classifier, not the ML classifier PROJECT.md's
fuller spec mentions -- a real model needs training data, weights, and an
inference dependency this project doesn't have yet, and adding one wasn't
asked for. Like the firewall's command rules, this catches known
phrasings, not every way to phrase an injection attempt; documented as a
known limit rather than assumed away.
"""

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class InjectionFinding:
    pattern: str
    reason: str
    excerpt: str


_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "ignore-instructions",
        re.compile(
            r"\bignore\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions?|prompts?|rules?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "disregard-instructions",
        re.compile(
            r"\bdisregard\s+(all\s+|any\s+)?(previous|prior|above|earlier)\s+"
            r"(instructions?|prompts?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "new-instructions",
        re.compile(r"\b(new|updated|real|actual)\s+instructions?\s*:", re.IGNORECASE),
    ),
    (
        "system-prompt-leak",
        re.compile(
            r"\b(reveal|print|show|output|repeat)\s+(your|the)\s+"
            r"(system\s+prompt|initial\s+instructions?)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "persona-override",
        re.compile(r"\byou\s+are\s+now\s+(a|an)\s+\w", re.IGNORECASE),
    ),
    (
        "secret-action",
        re.compile(r"\b(do\s+not|don'?t|never)\s+tell\s+the\s+user\b", re.IGNORECASE),
    ),
    (
        "hidden-html-comment",
        re.compile(r"<!--.*?(ignore|instruction|system\s+prompt).*?-->", re.IGNORECASE | re.DOTALL),
    ),
]

_EXCERPT_MARGIN = 20


def scan_text(text: str | None) -> InjectionFinding | None:
    """First known prompt-injection phrasing found in `text`, or None."""
    if not text:
        return None
    for name, pattern in _PATTERNS:
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - _EXCERPT_MARGIN)
            end = match.end() + _EXCERPT_MARGIN
            excerpt = text[start:end].strip()
            return InjectionFinding(
                pattern=name,
                reason=f"text matches a known prompt-injection phrasing ('{name}')",
                excerpt=excerpt,
            )
    return None
