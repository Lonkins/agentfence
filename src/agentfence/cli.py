"""Command-line entry point for agentfence.

This module wires the top-level Typer application. Subcommands are added by
later feature modules; the bootstrap surface exposes ``version`` and a
top-level ``--version`` flag so packaging and installation can be verified
end to end before any engine code exists.
"""

from __future__ import annotations

import typer
from rich.console import Console

from agentfence import __version__

app = typer.Typer(
    name="agentfence",
    help="Conformance testing for CLI coding-agent permission boundaries.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()


def _version_callback(value: bool) -> None:
    if value:
        console.print(f"agentfence {__version__}")
        raise typer.Exit(code=0)


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-V",
        help="Show the agentfence version and exit.",
        callback=_version_callback,
        is_eager=True,
    ),
) -> None:
    """agentfence: prove your coding agent's permission boundary actually holds."""


@app.command()
def version() -> None:
    """Print the installed agentfence version."""
    console.print(f"agentfence {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
