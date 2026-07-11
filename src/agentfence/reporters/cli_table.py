"""Rich CLI table reporter."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from agentfence.engine.models import ConformanceReport, Verdict

_VERDICT_STYLE = {
    Verdict.LEAK: ("LEAK", "bold red"),
    Verdict.HELD: ("HELD", "green"),
    Verdict.ASK: ("ASK", "yellow"),
    Verdict.ERROR: ("ERROR", "bold yellow"),
    Verdict.SKIPPED: ("SKIP", "dim"),
}


def build_table(report: ConformanceReport) -> Table:
    """Build a Rich table of scenario results."""
    table = Table(
        title=f"agentfence · {report.agent} · {report.mode}",
        title_style="bold",
        header_style="bold",
        expand=True,
    )
    table.add_column("Scenario", overflow="fold")
    table.add_column("Boundary")
    table.add_column("Verdict", justify="center")
    table.add_column("Decision", justify="center")
    for result in report.results:
        label, style = _VERDICT_STYLE[result.verdict]
        decision = result.decision.value.upper() if result.decision else "—"
        table.add_row(
            result.scenario_id,
            result.boundary.value,
            f"[{style}]{label}[/{style}]",
            decision,
        )
    return table


def render_table(report: ConformanceReport, console: Console | None = None) -> None:
    """Print the results table and a one-line summary to the console."""
    console = console or Console()
    console.print(build_table(report))
    counts = report.summary_counts()
    parts = [f"{counts[v.value]} {v.value}" for v in Verdict if counts[v.value]]
    status = "[bold green]PASS[/bold green]" if report.ok else "[bold red]FAIL[/bold red]"
    console.print(f"{status}  " + "  ".join(parts))
