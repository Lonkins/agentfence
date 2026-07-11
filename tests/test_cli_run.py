"""Tests for the `agentfence run` CLI and its exit codes."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from agentfence.cli import app

runner = CliRunner()

FIXTURES = Path(__file__).parent / "fixtures"
LOOSE = str(FIXTURES / "claude_code/loose.settings.json")
HARDENED = str(FIXTURES / "claude_code/hardened.settings.json")


def test_run_loose_fails_with_exit_1() -> None:
    result = runner.invoke(app, ["run", LOOSE, "--agent", "claude-code"])
    assert result.exit_code == 1
    assert "FAIL" in result.stdout


def test_run_hardened_passes_with_exit_0() -> None:
    result = runner.invoke(app, ["run", HARDENED, "--agent", "claude-code"])
    assert result.exit_code == 0
    assert "PASS" in result.stdout


def test_run_json_output() -> None:
    result = runner.invoke(app, ["run", LOOSE, "--agent", "claude-code", "-f", "json"])
    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["summary"]["ok"] is False
    assert payload["summary"]["leak"] >= 1


def test_run_sarif_output() -> None:
    result = runner.invoke(app, ["run", LOOSE, "--agent", "claude-code", "-f", "sarif"])
    doc = json.loads(result.stdout)
    assert doc["version"] == "2.1.0"


def test_run_unknown_agent_exits_2() -> None:
    result = runner.invoke(app, ["run", LOOSE, "--agent", "nope"])
    assert result.exit_code == 2


def test_run_autodetects_from_directory(tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(Path(LOOSE).read_text())
    result = runner.invoke(app, ["run", str(tmp_path)])
    assert result.exit_code == 1  # loose config leaks


def test_run_boundary_filter() -> None:
    result = runner.invoke(
        app,
        ["run", LOOSE, "--agent", "claude-code", "-b", "deny-rule-bypass", "-f", "json"],
    )
    payload = json.loads(result.stdout)
    boundaries = {r["boundary"] for r in payload["results"]}
    assert boundaries == {"deny-rule-bypass"}


def test_run_invalid_boundary_exits_2() -> None:
    result = runner.invoke(app, ["run", LOOSE, "--agent", "claude-code", "-b", "not-a-boundary"])
    assert result.exit_code == 2


def test_run_strict_ask_fails_hardened() -> None:
    # Hardened passes normally, but under strict-ask the ASK cases count as leaks.
    normal = runner.invoke(app, ["run", HARDENED, "--agent", "claude-code"])
    strict = runner.invoke(app, ["run", HARDENED, "--agent", "claude-code", "--strict-ask"])
    assert normal.exit_code == 0
    assert strict.exit_code == 1


def test_run_writes_output_file(tmp_path: Path) -> None:
    out = tmp_path / "report.md"
    result = runner.invoke(
        app, ["run", LOOSE, "--agent", "claude-code", "-f", "markdown", "-o", str(out)]
    )
    assert result.exit_code == 1
    assert out.is_file()
    assert "conformance report" in out.read_text()


def test_run_live_without_optin_exits_2() -> None:
    result = runner.invoke(app, ["run", LOOSE, "--agent", "claude-code", "--live"])
    assert result.exit_code == 2


def test_agents_command_lists_all() -> None:
    result = runner.invoke(app, ["agents"])
    assert result.exit_code == 0
    for name in ("claude-code", "codex", "opencode"):
        assert name in result.stdout


def test_scenarios_command_lists() -> None:
    result = runner.invoke(app, ["scenarios"])
    assert result.exit_code == 0
    assert "scenarios" in result.stdout


def test_scenarios_invalid_boundary_exits_2() -> None:
    result = runner.invoke(app, ["scenarios", "-b", "bogus"])
    assert result.exit_code == 2
