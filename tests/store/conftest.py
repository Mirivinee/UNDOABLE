import sqlite3
from pathlib import Path

import pytest

from undoable.store.db import connect


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    return tmp_path / "nested" / "undoable.db"


@pytest.fixture
def conn(db_path: Path) -> sqlite3.Connection:
    connection = connect(db_path)
    yield connection
    connection.close()
