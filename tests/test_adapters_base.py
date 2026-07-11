"""Tests for permission primitives and the adapter registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfence.adapters import (
    AdapterError,
    AgentAdapter,
    ClaudeCodeAdapter,
    available_adapters,
    detect_adapter,
    get_adapter,
)
from agentfence.permissions import PermissionDecision, PermissionModel, Rule


def test_rule_parse_with_specifier() -> None:
    rule = Rule.parse("Bash(curl:*)")
    assert rule.tool == "Bash"
    assert rule.specifier == "curl:*"
    assert rule.raw == "Bash(curl:*)"


def test_rule_parse_bare_tool() -> None:
    rule = Rule.parse("WebFetch")
    assert rule.tool == "WebFetch"
    assert rule.specifier is None


def test_rule_parse_tolerates_whitespace() -> None:
    rule = Rule.parse("  Read( ./.env )  ")
    assert rule.tool == "Read"
    assert rule.specifier == " ./.env "


def test_permission_model_rule_count() -> None:
    model = PermissionModel(
        agent="x",
        allow=(Rule.parse("Bash(ls:*)"),),
        deny=(Rule.parse("Bash(curl:*)"), Rule.parse("WebFetch")),
    )
    assert model.rule_count == 3
    assert model.default_decision is PermissionDecision.ASK


def test_registry_exposes_claude_code() -> None:
    assert "claude-code" in available_adapters()
    adapter = get_adapter("claude-code")
    assert adapter.name == "claude-code"


def test_get_unknown_adapter_raises() -> None:
    with pytest.raises(AdapterError, match="Unknown agent adapter"):
        get_adapter("does-not-exist")


def test_claude_code_adapter_satisfies_protocol() -> None:
    assert isinstance(ClaudeCodeAdapter(), AgentAdapter)


def test_detect_adapter_on_directory(tmp_path: Path) -> None:
    settings_dir = tmp_path / ".claude"
    settings_dir.mkdir()
    (settings_dir / "settings.json").write_text('{"permissions": {"deny": ["WebFetch"]}}')
    adapter = detect_adapter(tmp_path)
    assert adapter is not None
    assert adapter.name == "claude-code"


def test_detect_adapter_returns_none_when_no_config(tmp_path: Path) -> None:
    assert detect_adapter(tmp_path) is None
