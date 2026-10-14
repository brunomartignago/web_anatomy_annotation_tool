"""Command-line entry point: `annotool capture | serve | migrate | export | stats`.

Commands are added by later roadmap items; for now only `--version` exists.
"""

import typer

from annotool import __version__

app = typer.Typer(
    name="annotool",
    help="Annotate web page screenshots with a multi-axis UI taxonomy.",
    no_args_is_help=True,
)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"annotool {__version__}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        help="Show the version and exit.",
        callback=_print_version,
        is_eager=True,
    ),
) -> None:
    """Annotate web page screenshots with a multi-axis UI taxonomy."""
