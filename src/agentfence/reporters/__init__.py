"""Report renderers: CLI table, JSON, SARIF, and signed Markdown."""

from __future__ import annotations

from enum import StrEnum

from agentfence.engine.models import ConformanceReport
from agentfence.reporters.cli_table import build_table, render_table
from agentfence.reporters.json_report import build_payload, render_json
from agentfence.reporters.markdown import render_markdown
from agentfence.reporters.sarif import render_sarif


class ReportFormat(StrEnum):
    """Output formats supported by the CLI."""

    TABLE = "table"
    JSON = "json"
    SARIF = "sarif"
    MARKDOWN = "markdown"


def render_text(
    report: ConformanceReport,
    fmt: ReportFormat,
    *,
    signing_key: str | None = None,
) -> str:
    """Render a report to a string for a non-interactive (file/stdout) format.

    ``TABLE`` is interactive-only (use :func:`render_table`); requesting it here
    falls back to Markdown, which is the closest text equivalent.
    """
    if fmt is ReportFormat.JSON:
        return render_json(report)
    if fmt is ReportFormat.SARIF:
        return render_sarif(report)
    return render_markdown(report, signing_key=signing_key)


__all__ = [
    "ReportFormat",
    "build_payload",
    "build_table",
    "render_json",
    "render_markdown",
    "render_sarif",
    "render_table",
    "render_text",
]
