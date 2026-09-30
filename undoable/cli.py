import sys
from pathlib import Path

import typer

from undoable import __version__
from undoable.interceptor.hooks import run as run_hook
from undoable.report.report import generate_report

app = typer.Typer(help="UNDOABLE: a safety net for autonomous AI coding agents.")


@app.command()
def version() -> None:
    """Print the installed UNDOABLE version."""
    typer.echo(__version__)


@app.command()
def hook() -> None:
    """Read one Claude Code hook JSON payload from stdin and log it.

    Used for every hook event (PreToolUse, PostToolUse, SessionStart, Stop,
    SessionEnd) -- it dispatches on the payload's hook_event_name, so one
    settings.json command covers all of them.
    """
    exit_code = run_hook(sys.stdin)
    raise typer.Exit(code=exit_code)


@app.command()
def report(
    since: str = typer.Option(None, help="Only include events at/after this ISO 8601 timestamp."),
) -> None:
    """Print a Markdown summary: actions taken, blocked attempts, items
    flagged for review, and snapshots created, for the current directory's
    project."""
    typer.echo(generate_report(str(Path.cwd()), since=since))


if __name__ == "__main__":
    app()
