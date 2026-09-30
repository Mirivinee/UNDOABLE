import typer

from undoable import __version__

app = typer.Typer(help="UNDOABLE: a safety net for autonomous AI coding agents.")


@app.command()
def version() -> None:
    """Print the installed UNDOABLE version."""
    typer.echo(__version__)


if __name__ == "__main__":
    app()
