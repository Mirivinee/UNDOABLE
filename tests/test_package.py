import importlib

import undoable

SUBPACKAGES = [
    "undoable.interceptor",
    "undoable.firewall",
    "undoable.snapshot",
    "undoable.packages",
    "undoable.killswitch",
    "undoable.report",
    "undoable.store",
]


def test_version_is_set() -> None:
    assert undoable.__version__ == "0.1.0"


def test_all_subpackages_import() -> None:
    for name in SUBPACKAGES:
        importlib.import_module(name)
