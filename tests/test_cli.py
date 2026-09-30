from typer.testing import CliRunner

from undoable import __version__
from undoable.cli import app

runner = CliRunner()


def test_version_command_prints_version() -> None:
    # A Typer app with a single command collapses to no subcommand name.
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert __version__ in result.stdout
