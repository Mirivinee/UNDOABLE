import pytest

from undoable.packages.check import (
    ASK,
    SAFE,
    evaluate_command,
    extract_npm_packages,
    extract_pip_packages,
)

PIP_EXTRACTION_CASES = [
    ("pip install requests", ["requests"]),
    ("pip install requests==2.31.0", ["requests"]),
    ("pip3 install flask[async]", ["flask"]),
    ("python -m pip install --upgrade numpy pandas", ["numpy", "pandas"]),
    ("pip install -r requirements.txt", []),
    ("pip install git+https://github.com/x/y.git", []),
    ("pip install ./local-package", []),
    ("ls -la", []),
]


@pytest.mark.parametrize(("command", "expected"), PIP_EXTRACTION_CASES)
def test_extract_pip_packages(command: str, expected: list[str]) -> None:
    assert extract_pip_packages(command) == expected


NPM_EXTRACTION_CASES = [
    ("npm install lodash", ["lodash"]),
    ("npm i express@4.18.0", ["express"]),
    ("npm install @babel/core@7.0.0", ["@babel/core"]),
    ("npm install -g typescript", ["typescript"]),
    ("npm install ./local-pkg", []),
    ("ls -la", []),
]


@pytest.mark.parametrize(("command", "expected"), NPM_EXTRACTION_CASES)
def test_extract_npm_packages(command: str, expected: list[str]) -> None:
    assert extract_npm_packages(command) == expected


def _always(status: int):
    def fetch(url: str, timeout: float) -> int:
        return status

    return fetch


def _never_call():
    def fetch(url: str, timeout: float) -> int:
        raise AssertionError("fetch should not have been called")

    return fetch


def test_non_install_command_returns_none() -> None:
    assert evaluate_command("ls -la") is None


def test_known_good_package_is_safe() -> None:
    result = evaluate_command("pip install requests", pypi_fetch=_always(200))
    assert result.decision == SAFE
    assert result.reason is None


def test_typosquat_is_flagged_even_if_the_name_exists() -> None:
    result = evaluate_command("pip install reqeusts", pypi_fetch=_always(200))
    assert result.decision == ASK
    assert "requests" in result.reason


def test_nonexistent_package_is_flagged() -> None:
    result = evaluate_command("pip install totally-made-up-pkg-xyz123", pypi_fetch=_always(404))
    assert result.decision == ASK
    assert "does not exist" in result.reason


def test_network_error_is_not_treated_as_nonexistent() -> None:
    def raising_fetch(url: str, timeout: float) -> int:
        raise TimeoutError

    result = evaluate_command("pip install requests", pypi_fetch=raising_fetch)
    assert result.decision == SAFE
    [finding] = result.findings
    assert finding.exists is None


def test_check_existence_false_skips_network_entirely() -> None:
    result = evaluate_command(
        "pip install reqeusts", pypi_fetch=_never_call(), check_existence=False
    )
    assert result.decision == ASK
    assert "requests" in result.reason


def test_npm_typosquat_is_flagged() -> None:
    result = evaluate_command("npm install loadash", npm_fetch=_always(200))
    assert result.decision == ASK
    assert "lodash" in result.reason


def test_multiple_packages_one_bad_flags_the_command() -> None:
    result = evaluate_command(
        "pip install requests reqeusts",
        pypi_fetch=_always(200),
    )
    assert result.decision == ASK
    assert len(result.findings) == 2
