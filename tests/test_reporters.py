"""Tests for the JSON, SARIF, Markdown, and table reporters."""

from __future__ import annotations

import json

from rich.table import Table

from agentfence.engine.models import ConformanceReport, ScenarioResult, Verdict
from agentfence.permissions import CandidateAction, PermissionDecision
from agentfence.reporters import (
    ReportFormat,
    build_table,
    render_json,
    render_markdown,
    render_sarif,
    render_text,
)
from agentfence.scenarios.schema import BoundaryClass


def _result(
    sid: str,
    verdict: Verdict,
    decision: PermissionDecision | None,
    boundary: BoundaryClass = BoundaryClass.DENY_RULE_BYPASS,
) -> ScenarioResult:
    return ScenarioResult(
        scenario_id=sid,
        title=f"case {sid}",
        boundary=boundary,
        agent="claude-code",
        attempt=CandidateAction(tool="Bash", value="curl http://x"),
        expected="blocked",
        decision=decision,
        verdict=verdict,
        citation="https://example.test/ref",
        detail=f"detail for {sid}",
    )


def _report() -> ConformanceReport:
    return ConformanceReport(
        agent="claude-code",
        adapter_version="claude-code-settings-2026-05",
        config_source="/repo/.claude/settings.json",
        mode="deterministic",
        results=(
            _result("leak-1", Verdict.LEAK, PermissionDecision.ALLOW),
            _result("held-1", Verdict.HELD, PermissionDecision.DENY),
            _result("ask-1", Verdict.ASK, PermissionDecision.ASK),
            _result("err-1", Verdict.ERROR, None),
            _result("skip-1", Verdict.SKIPPED, None),
        ),
    )


# --------------------------------------------------------------------------- #
# JSON
# --------------------------------------------------------------------------- #


def test_render_json_is_valid_and_complete() -> None:
    payload = json.loads(render_json(_report()))
    assert payload["tool"]["name"] == "agentfence"
    assert payload["agent"] == "claude-code"
    assert payload["summary"]["total"] == 5
    assert payload["summary"]["leak"] == 1
    assert payload["summary"]["ok"] is False
    assert len(payload["results"]) == 5


# --------------------------------------------------------------------------- #
# SARIF
# --------------------------------------------------------------------------- #


def test_render_sarif_shape_and_levels() -> None:
    doc = json.loads(render_sarif(_report()))
    assert doc["version"] == "2.1.0"
    run = doc["runs"][0]
    # HELD and SKIPPED are not findings; LEAK/ASK/ERROR are.
    assert len(run["results"]) == 3
    levels = {r["ruleId"]: r["level"] for r in run["results"]}
    assert levels["leak-1"] == "error"
    assert levels["ask-1"] == "warning"
    assert levels["err-1"] == "note"
    assert len(run["tool"]["driver"]["rules"]) == 3
    # every result anchors to the config artifact
    loc = run["results"][0]["locations"][0]["physicalLocation"]["artifactLocation"]["uri"]
    assert loc == "/repo/.claude/settings.json"


def test_sarif_clean_report_has_no_results() -> None:
    clean = ConformanceReport(
        agent="a",
        adapter_version="v",
        config_source="s",
        results=(_result("h", Verdict.HELD, PermissionDecision.DENY),),
    )
    doc = json.loads(render_sarif(clean))
    assert doc["runs"][0]["results"] == []


# --------------------------------------------------------------------------- #
# Markdown
# --------------------------------------------------------------------------- #


def test_render_markdown_has_leaks_and_integrity() -> None:
    md = render_markdown(_report())
    assert "# agentfence conformance report" in md
    assert "## Leaks — boundaries that failed" in md
    assert "leak-1" in md
    assert "sha256:" in md
    assert "**FAIL**" in md
    assert "Signature" not in md  # unsigned by default


def test_render_markdown_signed_and_deterministic() -> None:
    signed = render_markdown(_report(), signing_key="secret-key")
    assert "Signature (HMAC-SHA256):" in signed
    # signing is deterministic for the same content
    assert render_markdown(_report(), signing_key="secret-key") == signed
    # a different key yields a different signature
    other = render_markdown(_report(), signing_key="other-key")
    assert other != signed


def test_markdown_clean_report_reads_positive() -> None:
    clean = ConformanceReport(
        agent="a",
        adapter_version="v",
        config_source="s",
        results=(_result("h", Verdict.HELD, PermissionDecision.DENY),),
    )
    md = render_markdown(clean)
    assert "Every tested boundary held" in md
    assert "**PASS**" in md


# --------------------------------------------------------------------------- #
# Table / dispatch
# --------------------------------------------------------------------------- #


def test_build_table_has_a_row_per_result() -> None:
    table = build_table(_report())
    assert isinstance(table, Table)
    assert table.row_count == 5


def test_render_text_table_falls_back_to_markdown() -> None:
    text = render_text(_report(), ReportFormat.TABLE)
    assert "# agentfence conformance report" in text
