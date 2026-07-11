"""Live mode — opt-in, bring-your-own-key.

Deterministic mode reasons about the *modeled* policy. Live mode drives the
*real* agent binary with an adversarial prompt inside the sandbox and observes
whether the blocked action actually happened (a canary file appears, a secret
token shows up in the agent's output).

This is opt-in and never runs by default:

- it needs the agent binary and, usually, an API key (BYO, via the environment);
- it executes real commands, so it only runs inside the Docker sandbox;
- reaching a real model needs network, so live runs typically enable network in
  the sandbox — detection then relies on the probe, not on network isolation.
  See docs/threat-model.md.
"""

from __future__ import annotations

import shlex
from collections.abc import Iterable, Mapping
from pathlib import Path

from agentfence.adapters.base import AgentAdapter
from agentfence.engine.models import ConformanceReport, ScenarioResult, Verdict
from agentfence.live_spec import LiveSpec, get_live_spec
from agentfence.sandbox import DockerSandbox, SandboxConfig
from agentfence.scenarios.schema import LiveProbe, ProbeKind, Scenario


class LiveModeError(RuntimeError):
    """Raised when live mode is misconfigured or invoked without opting in."""


class LiveEngine:
    """Runs scenarios against the real agent binary inside the sandbox."""

    def __init__(
        self,
        adapter: AgentAdapter,
        config_path: Path,
        *,
        sandbox_config: SandboxConfig | None = None,
        env: Mapping[str, str] | None = None,
        enabled: bool = False,
    ) -> None:
        self.adapter = adapter
        self.spec = get_live_spec(adapter)
        self.config_path = config_path
        self.sandbox_config = sandbox_config or SandboxConfig()
        self.env = dict(env or {})
        #: Opt-in gate. Live mode refuses to run unless this is explicitly True.
        self.enabled = enabled

    def preflight(self) -> LiveSpec:
        """Validate the opt-in gate and environment; return the live spec."""
        if not self.enabled:
            raise LiveModeError(
                "Live mode is opt-in and executes the real agent. Pass enabled=True "
                "(CLI: --live --i-understand-the-risks) to proceed."
            )
        if self.spec is None:
            raise LiveModeError(f"Adapter {self.adapter.name!r} does not support live mode.")
        missing = [name for name in self.spec.required_env if name not in self.env]
        if missing:
            raise LiveModeError(
                f"Live mode for {self.adapter.name} needs environment variable(s): "
                f"{', '.join(missing)}. Provide them yourself (bring-your-own-key)."
            )
        if not self.config_path.is_file():
            raise LiveModeError(f"Config not found: {self.config_path}")
        return self.spec

    def run(self, scenarios: Iterable[Scenario]) -> ConformanceReport:
        spec = self.preflight()
        config_text = self.config_path.read_text(encoding="utf-8")
        merged_env = {**self.sandbox_config.extra_env, **self.env}
        run_config = self.sandbox_config.model_copy(
            update={"extra_env": merged_env, "network_enabled": self.sandbox_config.network_enabled}
        )

        results: list[ScenarioResult] = []
        with DockerSandbox(run_config) as box:
            for scenario in scenarios:
                results.append(self._evaluate(box, spec, scenario, config_text))
        return ConformanceReport(
            agent=self.adapter.name,
            adapter_version=self.adapter.models_version,
            config_source=str(self.config_path),
            mode="live",
            results=tuple(results),
        )

    def _evaluate(
        self,
        box: DockerSandbox,
        spec: LiveSpec,
        scenario: Scenario,
        config_text: str,
    ) -> ScenarioResult:
        if not scenario.applies(self.adapter.name):
            return self._result(scenario, Verdict.SKIPPED, "Not applicable to this agent.")
        if not scenario.live_ready or scenario.probe is None:
            return self._result(scenario, Verdict.SKIPPED, "No live prompt/probe defined.")

        workdir = self.sandbox_config.workdir
        try:
            box.put_file(f"{workdir}/{spec.config_dest}", config_text)
            if scenario.probe.canary_file:
                box.put_file(
                    f"{workdir}/{scenario.probe.canary_file}",
                    scenario.probe.canary_content,
                )
            agent_run = box.run(spec.build_argv(scenario.prompt))
        except Exception as err:  # sandbox / agent invocation failure
            return self._result(scenario, Verdict.ERROR, f"Live run failed: {err}")

        crossed, detail = self._probe(box, scenario.probe, agent_run.stdout, workdir)
        verdict = Verdict.LEAK if crossed else Verdict.HELD
        return self._result(scenario, verdict, detail)

    def _probe(
        self,
        box: DockerSandbox,
        probe: LiveProbe,
        agent_stdout: str,
        workdir: str,
    ) -> tuple[bool, str]:
        if probe.kind is ProbeKind.OUTPUT_CONTAINS:
            crossed = probe.target in agent_stdout
            where = "appeared in" if crossed else "absent from"
            return crossed, f"Canary {probe.target!r} {where} agent output."
        # FILE_CREATED
        path = probe.target if probe.target.startswith("/") else f"{workdir}/{probe.target}"
        check = box.run(f"test -e {shlex.quote(path)}")
        crossed = check.ok
        verb = "was created" if crossed else "was not created"
        return crossed, f"Target {path} {verb} by the agent."

    def _result(self, scenario: Scenario, verdict: Verdict, detail: str) -> ScenarioResult:
        prefix = "LEAK: " if verdict is Verdict.LEAK else ""
        return ScenarioResult(
            scenario_id=scenario.id,
            title=scenario.title,
            boundary=scenario.boundary,
            agent=self.adapter.name,
            attempt=scenario.attempt,
            expected=scenario.expected.value,
            decision=None,
            verdict=verdict,
            citation=scenario.citation,
            detail=f"{prefix}{detail}",
        )
