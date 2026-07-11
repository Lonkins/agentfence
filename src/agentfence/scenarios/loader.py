"""Load the packaged scenario catalog from YAML.

The catalog ships as data with the wheel (``agentfence/scenarios/catalog/*.yaml``)
so it is versioned and reviewable independently of code. Loading validates every
entry against :class:`Scenario` and enforces unique ids.
"""

from __future__ import annotations

from collections.abc import Iterable
from functools import lru_cache
from importlib import resources
from importlib.resources.abc import Traversable

import yaml
from pydantic import ValidationError

from agentfence.scenarios.schema import BoundaryClass, Scenario

_CATALOG_DIR = "catalog"


class ScenarioError(RuntimeError):
    """Raised when the scenario catalog is malformed."""


def _catalog_root() -> Traversable:
    return resources.files("agentfence.scenarios") / _CATALOG_DIR


def _load_file(entry: Traversable) -> list[Scenario]:
    text = entry.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as err:
        raise ScenarioError(f"Invalid YAML in {entry.name}: {err}") from err
    if data is None:
        return []
    if not isinstance(data, list):
        raise ScenarioError(f"{entry.name} must contain a list of scenarios")
    scenarios: list[Scenario] = []
    for index, item in enumerate(data):
        try:
            scenarios.append(Scenario.model_validate(item))
        except ValidationError as err:
            raise ScenarioError(f"Invalid scenario #{index} in {entry.name}: {err}") from err
    return scenarios


@lru_cache(maxsize=1)
def load_catalog() -> tuple[Scenario, ...]:
    """Load and validate every scenario in the packaged catalog."""
    root = _catalog_root()
    collected: list[Scenario] = []
    seen: dict[str, str] = {}
    for entry in sorted(root.iterdir(), key=lambda p: p.name):
        if not entry.name.endswith((".yaml", ".yml")):
            continue
        for scenario in _load_file(entry):
            if scenario.id in seen:
                raise ScenarioError(
                    f"Duplicate scenario id {scenario.id!r} in {entry.name} "
                    f"(first seen in {seen[scenario.id]})"
                )
            seen[scenario.id] = entry.name
            collected.append(scenario)
    if not collected:
        raise ScenarioError("Scenario catalog is empty")
    return tuple(collected)


def filter_scenarios(
    scenarios: Iterable[Scenario],
    *,
    agent: str | None = None,
    boundaries: Iterable[BoundaryClass] | None = None,
) -> tuple[Scenario, ...]:
    """Filter scenarios by target agent and/or boundary class."""
    boundary_set = set(boundaries) if boundaries is not None else None
    result: list[Scenario] = []
    for scenario in scenarios:
        if agent is not None and not scenario.applies(agent):
            continue
        if boundary_set is not None and scenario.boundary not in boundary_set:
            continue
        result.append(scenario)
    return tuple(result)
