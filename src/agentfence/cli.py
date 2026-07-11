"""Command-line entry point for agentfence."""

from __future__ import annotations

import os
from pathlib import Path

import typer
from rich.console import Console

from agentfence import __version__
from agentfence.adapters import (
    AdapterError,
    available_adapters,
    detect_adapter,
    get_adapter,
)
from agentfence.adapters.base import AgentAdapter
from agentfence.engine import ConformanceReport, DeterministicEngine, LiveEngine, LiveModeError
from agentfence.reporters import ReportFormat, render_table, render_text
from agentfence.scenarios import ScenarioError, filter_scenarios, load_catalog
from agentfence.scenarios.schema import BoundaryClass, Scenario

app = typer.Typer(
    name="agentfence",
    help="Conformance testing for CLI coding-agent permission boundaries.",
    no_args_is_help=True,
    add_completion=False,
)
console = Console()
err_console = Console(stderr=True)

_DEFAULT_SIGNING_ENV = "AGENTFENCE_SIGNING_KEY"


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


@app.command()
def agents() -> None:
    """List the available agent adapters."""
    for name in available_adapters():
        adapter = get_adapter(name)
        console.print(f"[bold]{name}[/bold]  (models {adapter.models_version})")


@app.command()
def scenarios(
    boundary: list[str] | None = typer.Option(
        None, "--boundary", "-b", help="Only list these boundary classes."
    ),
) -> None:
    """List the scenario catalog."""
    try:
        catalog = _select_scenarios(boundary)
    except (ScenarioError, typer.BadParameter) as err:
        err_console.print(f"[red]error:[/red] {err}")
        raise typer.Exit(code=2) from err
    for scenario in catalog:
        console.print(f"[bold]{scenario.id}[/bold]  [{scenario.boundary.value}]  {scenario.title}")
    console.print(f"\n{len(catalog)} scenarios")


@app.command()
def run(
    config: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        help="Path to the agent config (a file, or a repo directory to search).",
    ),
    agent: str | None = typer.Option(
        None, "--agent", "-a", help="Adapter name (autodetected from the config if omitted)."
    ),
    fmt: ReportFormat = typer.Option(ReportFormat.TABLE, "--format", "-f", help="Output format."),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Write the report to a file instead of stdout."
    ),
    boundary: list[str] | None = typer.Option(
        None, "--boundary", "-b", help="Only run these boundary classes."
    ),
    strict_ask: bool = typer.Option(
        False, "--strict-ask", help="Treat a human prompt (ASK) as a leak (unattended runs)."
    ),
    live: bool = typer.Option(
        False, "--live", help="Drive the real agent binary in the sandbox (opt-in, BYO-key)."
    ),
    i_understand_the_risks: bool = typer.Option(
        False, "--i-understand-the-risks", help="Required to actually enable --live."
    ),
    signing_key_env: str = typer.Option(
        _DEFAULT_SIGNING_ENV,
        "--signing-key-env",
        help="Env var holding an HMAC key to sign the Markdown report.",
    ),
) -> None:
    """Run the conformance battery against an agent config."""
    try:
        adapter = _select_adapter(agent, config)
        catalog = _select_scenarios(boundary)
        report = _run_engine(
            adapter,
            config,
            catalog,
            strict_ask=strict_ask,
            live=live,
            live_enabled=i_understand_the_risks,
        )
    except (AdapterError, ScenarioError, LiveModeError, typer.BadParameter) as err:
        err_console.print(f"[red]error:[/red] {err}")
        raise typer.Exit(code=2) from err

    signing_key = os.environ.get(signing_key_env) if signing_key_env else None
    _emit(report, fmt, output, signing_key)
    raise typer.Exit(code=0 if report.ok else 1)


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #


def _select_adapter(agent: str | None, config: Path) -> AgentAdapter:
    if agent is not None:
        return get_adapter(agent)
    detected = detect_adapter(config)
    if detected is None:
        raise typer.BadParameter(
            f"Could not autodetect an agent from {config}. "
            f"Pass --agent (one of: {', '.join(available_adapters())})."
        )
    return detected


def _select_scenarios(boundary: list[str] | None) -> tuple[Scenario, ...]:
    catalog = load_catalog()
    if not boundary:
        return catalog
    try:
        wanted = [BoundaryClass(b) for b in boundary]
    except ValueError as err:
        valid = ", ".join(b.value for b in BoundaryClass)
        raise typer.BadParameter(f"Unknown boundary. Valid values: {valid}") from err
    return filter_scenarios(catalog, boundaries=wanted)


def _run_engine(
    adapter: AgentAdapter,
    config: Path,
    catalog: tuple[Scenario, ...],
    *,
    strict_ask: bool,
    live: bool,
    live_enabled: bool,
) -> ConformanceReport:
    if live:
        engine = LiveEngine(
            adapter,
            config,
            env=dict(os.environ),
            enabled=live_enabled,
        )
        return engine.run(catalog)
    model = adapter.load(config)
    return DeterministicEngine(adapter, model, strict_ask=strict_ask).run(catalog)


def _emit(
    report: ConformanceReport,
    fmt: ReportFormat,
    output: Path | None,
    signing_key: str | None,
) -> None:
    if output is not None:
        text = render_text(report, fmt, signing_key=signing_key)
        output.write_text(text, encoding="utf-8")
        err_console.print(f"Wrote {fmt.value} report to {output}")
        return
    if fmt is ReportFormat.TABLE:
        render_table(report, console)
        return
    # JSON/SARIF/Markdown to stdout: plain echo so brackets aren't parsed as markup.
    typer.echo(render_text(report, fmt, signing_key=signing_key))


if __name__ == "__main__":  # pragma: no cover
    app()
