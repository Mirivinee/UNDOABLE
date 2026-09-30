from pathlib import Path

from typer.testing import CliRunner

from undoable import __version__
from undoable.cli import app

runner = CliRunner()


def test_version_command_prints_version() -> None:
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.stdout


def test_report_command_runs_against_the_current_directory(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["report"])
    assert result.exit_code == 0
    assert "UNDOABLE Morning Report" in result.stdout


def test_report_command_accepts_since_option(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["report", "--since", "2020-01-01T00:00:00+00:00"])
    assert result.exit_code == 0
    assert "Since 2020-01-01" in result.stdout
