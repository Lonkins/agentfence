"""Tests for the scenario catalog and loader.

Includes the definition-of-done check: every hardened fixture is clean and every
loose fixture leaks, across all three adapters, over the whole catalog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from agentfence.adapters import get_adapter
from agentfence.engine import DeterministicEngine, Verdict
from agentfence.scenarios import filter_scenarios, load_catalog
from agentfence.scenarios.loader import ScenarioError, _load_file
from agentfence.scenarios.schema import BoundaryClass

FIXTURES = Path(__file__).parent / "fixtures"

CONFIGS = {
    "claude-code": (
        FIXTURES / "claude_code/loose.settings.json",
        FIXTURES / "claude_code/hardened.settings.json",
    ),
    "codex": (
        FIXTURES / "codex/loose.config.toml",
        FIXTURES / "codex/hardened.config.toml",
    ),
    "opencode": (
        FIXTURES / "opencode/loose.opencode.json",
        FIXTURES / "opencode/hardened.opencode.json",
    ),
}


# --------------------------------------------------------------------------- #
# Catalog integrity
# --------------------------------------------------------------------------- #


def test_catalog_loads_and_is_non_empty() -> None:
    catalog = load_catalog()
    assert len(catalog) >= 20


def test_every_boundary_class_is_covered() -> None:
    covered = {s.boundary for s in load_catalog()}
    assert covered == set(BoundaryClass), f"missing: {set(BoundaryClass) - covered}"


def test_every_scenario_has_a_citation() -> None:
    uncited = [s.id for s in load_catalog() if not s.citation]
    assert uncited == [], f"scenarios without a citation: {uncited}"


def test_scenario_ids_are_unique() -> None:
    ids = [s.id for s in load_catalog()]
    assert len(ids) == len(set(ids))


def test_filter_by_boundary() -> None:
    bypasses = filter_scenarios(load_catalog(), boundaries=[BoundaryClass.DENY_RULE_BYPASS])
    assert len(bypasses) >= 4
    assert all(s.boundary is BoundaryClass.DENY_RULE_BYPASS for s in bypasses)


def test_filter_by_agent_respects_applies_to() -> None:
    catalog = load_catalog()
    # No scenario currently restricts itself, so filtering keeps them all.
    assert len(filter_scenarios(catalog, agent="claude-code")) == len(catalog)


# --------------------------------------------------------------------------- #
# Definition of done
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("agent", list(CONFIGS))
def test_hardened_config_is_clean(agent: str) -> None:
    adapter = get_adapter(agent)
    _loose, hardened = CONFIGS[agent]
    report = DeterministicEngine(adapter, adapter.load(hardened)).run(load_catalog())
    assert report.ok, f"{agent} hardened leaked: {[r.scenario_id for r in report.leaks]}"
    assert report.count(Verdict.LEAK) == 0


@pytest.mark.parametrize("agent", list(CONFIGS))
def test_loose_config_leaks(agent: str) -> None:
    adapter = get_adapter(agent)
    loose, _hardened = CONFIGS[agent]
    report = DeterministicEngine(adapter, adapter.load(loose)).run(load_catalog())
    assert report.has_leak, f"{agent} loose config produced no leaks"


def test_deny_rule_bypass_leaks_on_loose_claude_code() -> None:
    """The headline: the bypass class is auto-allowed under a loose Claude config."""
    adapter = get_adapter("claude-code")
    loose, _ = CONFIGS["claude-code"]
    report = DeterministicEngine(adapter, adapter.load(loose)).run(load_catalog())
    bypass_leaks = [r for r in report.leaks if r.boundary is BoundaryClass.DENY_RULE_BYPASS]
    assert bypass_leaks, "expected the deny-rule bypass class to leak on a loose config"
    # and the same battery is clean when hardened
    _, hardened = CONFIGS["claude-code"]
    hardened_report = DeterministicEngine(adapter, adapter.load(hardened)).run(load_catalog())
    assert not hardened_report.has_leak


# --------------------------------------------------------------------------- #
# Loader error handling
# --------------------------------------------------------------------------- #


class _StubEntry:
    def __init__(self, name: str, text: str) -> None:
        self.name = name
        self._text = text

    def read_text(self, encoding: str = "utf-8") -> str:
        return self._text


def test_loader_rejects_non_list() -> None:
    with pytest.raises(ScenarioError, match="must contain a list"):
        _load_file(_StubEntry("bad.yaml", "key: value"))  # type: ignore[arg-type]


def test_loader_rejects_invalid_scenario() -> None:
    with pytest.raises(ScenarioError, match="Invalid scenario"):
        _load_file(_StubEntry("bad.yaml", "- title: no id or boundary"))  # type: ignore[arg-type]


def test_loader_rejects_bad_yaml() -> None:
    with pytest.raises(ScenarioError, match="Invalid YAML"):
        _load_file(_StubEntry("bad.yaml", "- [unbalanced"))  # type: ignore[arg-type]


def test_loader_empty_file_is_ok() -> None:
    assert _load_file(_StubEntry("empty.yaml", "")) == []  # type: ignore[arg-type]
