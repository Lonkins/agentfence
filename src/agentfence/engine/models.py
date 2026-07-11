"""Result and report models produced by the engines.

Shared by the deterministic engine, the live engine (Part 7), and every reporter
(Part 8). A :class:`Verdict` is the per-scenario outcome; a
:class:`ConformanceReport` aggregates them for one agent + config.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from agentfence.permissions import CandidateAction, PermissionDecision
from agentfence.scenarios.schema import BoundaryClass


class Verdict(StrEnum):
    """Per-scenario outcome."""

    HELD = "held"  # boundary blocked the attempt, as expected
    LEAK = "leak"  # boundary failed: the attempt would be auto-allowed
    ASK = "ask"  # the agent would prompt a human — held under review, weak under auto-approve
    ERROR = "error"  # the adapter could not decide
    SKIPPED = "skipped"  # scenario does not apply to this agent


def verdict_for(decision: PermissionDecision, *, strict_ask: bool) -> Verdict:
    """Map a permission decision to a verdict for an ``expected: blocked`` scenario."""
    if decision is PermissionDecision.ALLOW:
        return Verdict.LEAK
    if decision is PermissionDecision.DENY:
        return Verdict.HELD
    # ASK: a human gate. A leak only if the agent runs unattended (auto-approve).
    return Verdict.LEAK if strict_ask else Verdict.ASK


class ScenarioResult(BaseModel):
    """The outcome of evaluating one scenario against one config."""

    model_config = ConfigDict(frozen=True)

    scenario_id: str
    title: str
    boundary: BoundaryClass
    agent: str
    attempt: CandidateAction
    expected: str
    decision: PermissionDecision | None
    verdict: Verdict
    citation: str = ""
    detail: str = ""

    @property
    def leaked(self) -> bool:
        return self.verdict is Verdict.LEAK


class ConformanceReport(BaseModel):
    """All scenario results for one agent + config, plus summary accessors."""

    model_config = ConfigDict(frozen=True)

    agent: str
    adapter_version: str
    config_source: str
    mode: str = "deterministic"
    strict_ask: bool = False
    results: tuple[ScenarioResult, ...] = ()

    def count(self, verdict: Verdict) -> int:
        return sum(1 for r in self.results if r.verdict is verdict)

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def leaks(self) -> tuple[ScenarioResult, ...]:
        return tuple(r for r in self.results if r.verdict is Verdict.LEAK)

    @property
    def has_leak(self) -> bool:
        return any(r.verdict is Verdict.LEAK for r in self.results)

    @property
    def has_error(self) -> bool:
        return any(r.verdict is Verdict.ERROR for r in self.results)

    @property
    def ok(self) -> bool:
        """True when the battery is clean: no leaks and no errors."""
        return not self.has_leak and not self.has_error

    def summary_counts(self) -> dict[str, int]:
        return {verdict.value: self.count(verdict) for verdict in Verdict}
