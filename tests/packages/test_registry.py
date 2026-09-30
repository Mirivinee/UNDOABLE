from undoable.packages.registry import check_npm_exists, check_pypi_exists


def _fetch(status: int):
    def fetch(url: str, timeout: float) -> int:
        return status

    return fetch


def _raising_fetch(exc: Exception):
    def fetch(url: str, timeout: float):
        raise exc

    return fetch


def test_pypi_exists_true_on_200() -> None:
    assert check_pypi_exists("requests", fetch=_fetch(200)) is True


def test_pypi_exists_false_on_404() -> None:
    assert check_pypi_exists("definitely-not-a-real-package", fetch=_fetch(404)) is False


def test_pypi_exists_unknown_on_network_error() -> None:
    assert check_pypi_exists("requests", fetch=_raising_fetch(TimeoutError("timed out"))) is None


def test_pypi_exists_unknown_on_unexpected_status() -> None:
    assert check_pypi_exists("requests", fetch=_fetch(500)) is None


def test_npm_exists_true_on_200() -> None:
    assert check_npm_exists("lodash", fetch=_fetch(200)) is True


def test_npm_exists_false_on_404() -> None:
    assert check_npm_exists("definitely-not-a-real-package", fetch=_fetch(404)) is False


def test_pypi_url_uses_the_package_name() -> None:
    seen = {}

    def fetch(url: str, timeout: float) -> int:
        seen["url"] = url
        return 200

    check_pypi_exists("requests", fetch=fetch)
    assert seen["url"] == "https://pypi.org/pypi/requests/json"


def test_npm_url_uses_the_package_name() -> None:
    seen = {}

    def fetch(url: str, timeout: float) -> int:
        seen["url"] = url
        return 200

    check_npm_exists("lodash", fetch=fetch)
    assert seen["url"] == "https://registry.npmjs.org/lodash"
