"""SARIF 2.1.0 reporter — for GitHub code scanning and other SARIF consumers.

Each non-passing scenario becomes a SARIF result anchored at the config file:
LEAK -> error, ASK -> warning, ERROR -> note. HELD/SKIPPED are omitted (they are
not findings). Each distinct scenario becomes a rule.
"""

from __future__ import annotations

import json

from agentfence import __version__
from agentfence.engine.models import ConformanceReport, ScenarioResult, Verdict

_INFO_URI = "https://github.com/Lonkins/agentfence"

_LEVEL = {
    Verdict.LEAK: "error",
    Verdict.ASK: "warning",
    Verdict.ERROR: "note",
}


def _rule(result: ScenarioResult) -> dict[str, object]:
    return {
        "id": result.scenario_id,
        "name": result.boundary.value,
        "shortDescription": {"text": result.title},
        "helpUri": result.citation or _INFO_URI,
        "properties": {"boundary": result.boundary.value},
    }


def _result(result: ScenarioResult, config_source: str) -> dict[str, object]:
    return {
        "ruleId": result.scenario_id,
        "level": _LEVEL[result.verdict],
        "message": {"text": result.detail or f"{result.boundary.value}: {result.title}"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": config_source or "agent-config"},
                }
            }
        ],
        "properties": {
            "verdict": result.verdict.value,
            "boundary": result.boundary.value,
            "agent": result.agent,
        },
    }


def render_sarif(report: ConformanceReport) -> str:
    """Render a report as a SARIF 2.1.0 document."""
    findings = [r for r in report.results if r.verdict in _LEVEL]
    # De-duplicate rules by scenario id, preserving first occurrence.
    rules: dict[str, dict[str, object]] = {}
    for finding in findings:
        rules.setdefault(finding.scenario_id, _rule(finding))

    document = {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "agentfence",
                        "version": __version__,
                        "informationUri": _INFO_URI,
                        "rules": list(rules.values()),
                    }
                },
                "results": [_result(f, report.config_source) for f in findings],
            }
        ],
    }
    return json.dumps(document, indent=2)
