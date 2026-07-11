"""JSON reporter — the machine-readable form of a conformance report."""

from __future__ import annotations

import json

from agentfence import __version__
from agentfence.engine.models import ConformanceReport


def build_payload(report: ConformanceReport) -> dict[str, object]:
    """Build the JSON-serialisable payload for a report."""
    return {
        "tool": {"name": "agentfence", "version": __version__},
        "agent": report.agent,
        "adapter_version": report.adapter_version,
        "config_source": report.config_source,
        "mode": report.mode,
        "strict_ask": report.strict_ask,
        "summary": {
            "total": report.total,
            "ok": report.ok,
            **report.summary_counts(),
        },
        "results": [result.model_dump(mode="json") for result in report.results],
    }


def render_json(report: ConformanceReport) -> str:
    """Render a report as pretty-printed JSON."""
    return json.dumps(build_payload(report), indent=2, sort_keys=False)
