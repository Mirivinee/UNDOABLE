import sqlite3
from pathlib import Path

import pytest

from undoable.store.db import connect


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    connection = connect(tmp_path / "test.db")
    yield connection
    connection.close()
