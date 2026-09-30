"""Package-registry existence checks for PyPI and npm.

Network access is injected via a `fetch` callable (url, timeout) -> status
code, so callers/tests never need a real network connection: the default
implementation is the only thing that actually calls out.
"""

import urllib.error
import urllib.request
from collections.abc import Callable

Fetcher = Callable[[str, float], int]

DEFAULT_TIMEOUT = 3.0


def default_fetch(url: str, timeout: float) -> int:
    """Real HTTP HEAD-ish check: returns the response status code, or the
    error's status code for an HTTP error (e.g. 404)."""
    request = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code


def _exists(url: str, fetch: Fetcher, timeout: float) -> bool | None:
    """True/False if we got a clear answer, None if the check itself failed
    (network error, timeout, unexpected status) -- callers should treat
    "couldn't verify" as its own signal, not silently as either answer."""
    try:
        status = fetch(url, timeout)
    except Exception:
        return None
    if status == 200:
        return True
    if status == 404:
        return False
    return None


def check_pypi_exists(
    name: str, *, fetch: Fetcher = default_fetch, timeout: float = DEFAULT_TIMEOUT
) -> bool | None:
    return _exists(f"https://pypi.org/pypi/{name}/json", fetch, timeout)


def check_npm_exists(
    name: str, *, fetch: Fetcher = default_fetch, timeout: float = DEFAULT_TIMEOUT
) -> bool | None:
    return _exists(f"https://registry.npmjs.org/{name}", fetch, timeout)
