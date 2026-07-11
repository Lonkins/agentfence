"""The deterministic conformance engine — zero network, zero LLM.

It feeds each scenario's candidate action through the agent's own modeled
permission engine (the adapter's ``decide``) and records whether the boundary
held. No model, no sandbox, no side effects: the default battery is instant and
reproducible (ADR-0002).
"""

from __future__ import annotations

from collections.abc import Iterable

from agentfence.adapters.base import AgentAdapter
from agentfence.engine.models import ConformanceReport, ScenarioResult, Verdict, verdict_for
from agentfence.permissions import PermissionDecision, PermissionModel
from agentfence.scenarios.schema import Scenario


class DeterministicEngine:
    """Evaluates scenarios against a loaded permission model."""

    def __init__(
        self,
        adapter: AgentAdapter,
        model: PermissionModel,
        *,
        strict_ask: bool = False,
    ) -> None:
        self.adapter = adapter
        self.model = model
        #: Treat an ASK (human prompt) as a leak — appropriate for unattended /
        #: auto-approve runs where no human is there to say no.
        self.strict_ask = strict_ask

    def evaluate(self, scenario: Scenario) -> ScenarioResult:
        if not scenario.applies(self.adapter.name):
            return self._result(
                scenario,
                decision=None,
                verdict=Verdict.SKIPPED,
                detail=f"Not applicable to {self.adapter.name}.",
            )
        try:
            decision = self.adapter.decide(self.model, scenario.attempt)
        except Exception as err:  # adapter robustness: never let one case abort the run
            return self._result(
                scenario,
                decision=None,
                verdict=Verdict.ERROR,
                detail=f"Adapter error: {err}",
            )
        verdict = verdict_for(decision, strict_ask=self.strict_ask)
        return self._result(
            scenario,
            decision=decision,
            verdict=verdict,
            detail=self._repro(scenario, decision, verdict),
        )

    def run(self, scenarios: Iterable[Scenario]) -> ConformanceReport:
        results = tuple(self.evaluate(s) for s in scenarios)
        return ConformanceReport(
            agent=self.adapter.name,
            adapter_version=self.adapter.models_version,
            config_source=self.model.source,
            mode="deterministic",
            strict_ask=self.strict_ask,
            results=results,
        )

    def _result(
        self,
        scenario: Scenario,
        *,
        decision: PermissionDecision | None,
        verdict: Verdict,
        detail: str,
    ) -> ScenarioResult:
        return ScenarioResult(
            scenario_id=scenario.id,
            title=scenario.title,
            boundary=scenario.boundary,
            agent=self.adapter.name,
            attempt=scenario.attempt,
            expected=scenario.expected.value,
            decision=decision,
            verdict=verdict,
            citation=scenario.citation,
            detail=detail,
        )

    def _repro(self, scenario: Scenario, decision: PermissionDecision, verdict: Verdict) -> str:
        action = scenario.attempt
        base = (
            f"Fed {action.tool}({action.value!r}) through the {self.adapter.name} "
            f"permission engine; it decided {decision.value.upper()} "
            f"(expected {scenario.expected.value})."
        )
        if verdict is Verdict.LEAK:
            return f"{base} LEAK: boundary '{scenario.boundary.value}' would be auto-allowed."
        if verdict is Verdict.ASK:
            return f"{base} Held only by a human prompt; a leak under auto-approve."
        return base
