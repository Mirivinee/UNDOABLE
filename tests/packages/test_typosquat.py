import pytest

from undoable.packages.typosquat import POPULAR_NPM, POPULAR_PYPI, find_typosquat_match

PYPI_TYPOS = [
    ("reqeusts", "requests"),
    ("numpi", "numpy"),
    ("djago", "django"),
    ("flsk", "flask"),
]


@pytest.mark.parametrize(("typo", "target"), PYPI_TYPOS)
def test_detects_pypi_typosquats(typo: str, target: str) -> None:
    assert find_typosquat_match(typo, POPULAR_PYPI) == target


NPM_TYPOS = [
    ("loadash", "lodash"),
    ("expres", "express"),
    ("reactt", "react"),
]


@pytest.mark.parametrize(("typo", "target"), NPM_TYPOS)
def test_detects_npm_typosquats(typo: str, target: str) -> None:
    assert find_typosquat_match(typo, POPULAR_NPM) == target


def test_exact_match_is_not_a_typosquat() -> None:
    assert find_typosquat_match("requests", POPULAR_PYPI) is None
    assert find_typosquat_match("REQUESTS", POPULAR_PYPI) is None  # case-insensitive


def test_unrelated_name_is_not_a_typosquat() -> None:
    assert find_typosquat_match("my-internal-company-lib", POPULAR_PYPI) is None


def test_short_names_are_skipped() -> None:
    assert find_typosquat_match("ab", POPULAR_PYPI) is None
    assert find_typosquat_match("six", POPULAR_PYPI) is None  # len 3, and it IS "six" anyway
