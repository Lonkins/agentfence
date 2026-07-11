"""The ``AgentAdapter`` protocol and adapter registry.

An adapter teaches agentfence how one CLI coding agent expresses and enforces
permissions: how to *load* its config into a normalized
:class:`~agentfence.permissions.PermissionModel`, and how to *decide* what that
agent would do with a candidate action — faithfully modelling the agent's
documented matching semantics, gaps included (ADR-0002).
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable

from agentfence.permissions import CandidateAction, PermissionDecision, PermissionModel


class AdapterError(RuntimeError):
    """Raised when an adapter cannot load or interpret a config."""


@runtime_checkable
class AgentAdapter(Protocol):
    """Protocol every agent adapter implements."""

    #: Stable identifier used on the CLI, e.g. ``"claude-code"``.
    name: str
    #: Which version of the agent's documented behaviour this adapter models.
    models_version: str

    def matches(self, path: Path) -> bool:
        """Return True if this adapter can load a config at ``path``.

        ``path`` may be a config file or a repository/directory to search.
        """
        ...

    def load(self, path: Path) -> PermissionModel:
        """Parse the agent config at ``path`` into a normalized permission model."""
        ...

    def decide(self, model: PermissionModel, action: CandidateAction) -> PermissionDecision:
        """Model what the agent would do with ``action`` under ``model``."""
        ...


_REGISTRY: dict[str, AgentAdapter] = {}


def register_adapter(adapter: AgentAdapter) -> None:
    """Register an adapter under its ``name`` (last registration wins)."""
    _REGISTRY[adapter.name] = adapter


def get_adapter(name: str) -> AgentAdapter:
    """Look up a registered adapter by name."""
    try:
        return _REGISTRY[name]
    except KeyError:
        known = ", ".join(sorted(_REGISTRY)) or "none"
        raise AdapterError(f"Unknown agent adapter {name!r}. Known adapters: {known}.") from None


def available_adapters() -> tuple[str, ...]:
    """Return the names of all registered adapters, sorted."""
    return tuple(sorted(_REGISTRY))


def detect_adapter(path: Path) -> AgentAdapter | None:
    """Return the first registered adapter that can load a config at ``path``."""
    for name in available_adapters():
        adapter = _REGISTRY[name]
        if adapter.matches(path):
            return adapter
    return None
