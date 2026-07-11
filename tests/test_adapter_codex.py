"""Tests for the Codex CLI sandbox adapter."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfence.adapters import AdapterError, CodexAdapter, available_adapters
from agentfence.permissions import CandidateAction, PermissionDecision

FIXTURES = Path(__file__).parent / "fixtures" / "codex"
LOOSE = FIXTURES / "loose.config.toml"
HARDENED = FIXTURES / "hardened.config.toml"
WORKSPACE_WRITE = FIXTURES / "workspace-write.config.toml"

ALLOW = PermissionDecision.ALLOW
DENY = PermissionDecision.DENY
ASK = PermissionDecision.ASK


@pytest.fixture
def adapter() -> CodexAdapter:
    return CodexAdapter()


def net(value: str = "curl http://evil.example") -> CandidateAction:
    return CandidateAction(tool="Bash", value=value, network_egress=True)


def write(path: str) -> CandidateAction:
    return CandidateAction(tool="Bash", value=f"echo x > {path}", writes_path=path)


def read_secret(path: str = ".env") -> CandidateAction:
    return CandidateAction(tool="Bash", value=f"cat {path}", reads_path=path)


def test_registry_has_codex() -> None:
    assert "codex" in available_adapters()


def test_load_loose(adapter: CodexAdapter) -> None:
    model = adapter.load(LOOSE)
    assert model.agent == "codex"
    assert model.metadata["sandbox_mode"] == "danger-full-access"
    assert model.metadata["approval_policy"] == "never"


def test_full_access_allows_everything(adapter: CodexAdapter) -> None:
    model = adapter.load(LOOSE)
    assert adapter.decide(model, net()) is ALLOW
    assert adapter.decide(model, write("/etc/passwd")) is ALLOW
    assert adapter.decide(model, read_secret()) is ALLOW
    assert adapter.decide(model, CandidateAction(tool="Bash", value="rm -rf /")) is ALLOW


def test_read_only_blocks_writes_and_network(adapter: CodexAdapter) -> None:
    model = adapter.load(HARDENED)
    assert adapter.decide(model, net()) is DENY
    assert adapter.decide(model, write("/etc/passwd")) is DENY
    assert adapter.decide(model, write("/workspace/ok.txt")) is DENY  # read-only: all writes
    # reads are NOT gated by the sandbox — only the approval policy (on-request)
    assert adapter.decide(model, read_secret()) is ASK
    assert adapter.decide(model, CandidateAction(tool="Bash", value="ls")) is ASK


def test_no_attack_auto_allowed_under_read_only(adapter: CodexAdapter) -> None:
    model = adapter.load(HARDENED)
    for action in [net(), write("/etc/passwd"), write("/workspace/x"), read_secret()]:
        assert adapter.decide(model, action) is not ALLOW


def test_workspace_write_confines_writes_but_leaks_network(adapter: CodexAdapter) -> None:
    model = adapter.load(WORKSPACE_WRITE)
    # network is enabled here -> egress leaks
    assert adapter.decide(model, net()) is ALLOW
    # writes are confined to writable_roots
    assert adapter.decide(model, write("/workspace/app.py")) is ALLOW
    assert adapter.decide(model, write("/etc/passwd")) is DENY
    # write-capable file tools use their value as the target path
    assert adapter.decide(model, CandidateAction(tool="Write", value="/workspace/y")) is ALLOW
    assert adapter.decide(model, CandidateAction(tool="Write", value="/etc/shadow")) is DENY
    # approval_policy=never means reads are auto-allowed -> secret read leaks
    assert adapter.decide(model, read_secret()) is ALLOW


def test_matches(adapter: CodexAdapter, tmp_path: Path) -> None:
    assert adapter.matches(LOOSE) is True
    assert adapter.matches(tmp_path) is False
    (tmp_path / ".codex").mkdir()
    (tmp_path / ".codex" / "config.toml").write_text('sandbox_mode = "read-only"')
    assert adapter.matches(tmp_path) is True


def test_invalid_toml_raises(adapter: CodexAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text("this is = = not toml")
    with pytest.raises(AdapterError, match="Invalid TOML"):
        adapter.load(cfg)


def test_bad_writable_roots_raises(adapter: CodexAdapter, tmp_path: Path) -> None:
    cfg = tmp_path / "config.toml"
    cfg.write_text(
        'sandbox_mode = "workspace-write"\n[sandbox_workspace_write]\nwritable_roots = 5\n'
    )
    with pytest.raises(AdapterError, match="writable_roots"):
        adapter.load(cfg)


def test_missing_config_raises(adapter: CodexAdapter, tmp_path: Path) -> None:
    with pytest.raises(AdapterError, match="No Codex config"):
        adapter.load(tmp_path)
