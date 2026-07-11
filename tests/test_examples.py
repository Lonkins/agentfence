"""Guard the shipped demo configs so the Action self-test can't silently rot."""

from __future__ import annotations

from pathlib import Path

from agentfence.adapters import get_adapter
from agentfence.engine import DeterministicEngine
from agentfence.scenarios import load_catalog

EXAMPLES = Path(__file__).parent.parent / "examples"


def test_demo_weak_config_leaks() -> None:
    adapter = get_adapter("claude-code")
    model = adapter.load(EXAMPLES / "demo-weak-config")
    report = DeterministicEngine(adapter, model).run(load_catalog())
    assert report.has_leak, "the weak demo config must leak (the Action self-test depends on it)"


def test_demo_hardened_config_is_clean() -> None:
    adapter = get_adapter("claude-code")
    model = adapter.load(EXAMPLES / "demo-hardened-config")
    report = DeterministicEngine(adapter, model).run(load_catalog())
    assert (
        report.ok
    ), f"the hardened demo config must be clean; leaked: {[r.scenario_id for r in report.leaks]}"
