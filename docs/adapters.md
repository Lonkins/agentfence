# Writing an adapter

An adapter teaches agentfence how one CLI coding agent expresses and enforces
permissions. It implements the `AgentAdapter` protocol:

```python
from pathlib import Path
from agentfence.permissions import CandidateAction, PermissionDecision, PermissionModel


class MyAgentAdapter:
    name = "my-agent"
    models_version = "my-agent-2026-07"   # what documented behaviour you model

    def matches(self, path: Path) -> bool:
        """Can this adapter load a config at `path` (file or repo dir)?"""

    def load(self, path: Path) -> PermissionModel:
        """Parse the agent config into a normalized permission model."""

    def decide(self, model: PermissionModel, action: CandidateAction) -> PermissionDecision:
        """Model what the agent would do with `action` under `model`."""
```

Register it so the CLI can find it:

```python
from agentfence.adapters import register_adapter
register_adapter(MyAgentAdapter())
```

## The golden rule: model documented behaviour, gaps and all

`decide()` must reproduce the agent's real matching semantics — *including*
permissive gaps. If the agent's matcher is bypassable, your model must be
bypassable in the same way, so the bypass surfaces as a **LEAK**. Do not
"helpfully" canonicalise paths or parse command wrappers the real agent doesn't.
See [ADR-0002](adr/0002-deterministic-policy-evaluation.md).

## Two shapes of permission model

- **Rule lists** (Claude Code, OpenCode): match `tool` + `value` against
  allow/deny/ask rules. Store them in `PermissionModel.allow/deny/ask`.
- **Sandbox / capability** (Codex): decide from the structured capability hints
  on `CandidateAction` (`writes_path`, `reads_path`, `network_egress`). Stash the
  structured policy in `PermissionModel.metadata` and read it back in `decide()`.

## Optional: live mode

Declare a `live_spec` to make your adapter drivable in live mode:

```python
from agentfence.live_spec import LiveSpec

class MyAgentAdapter:
    live_spec = LiveSpec(
        binary="my-agent",
        argv_template=("my-agent", "run", "{prompt}"),  # {prompt} is substituted
        config_dest="my-agent.json",                     # where config is seeded
        required_env=("MY_AGENT_API_KEY",),              # BYO-key env vars
    )
```

## Ship fixtures

Every adapter needs golden fixtures: a loose config that leaks and a hardened
config that is clean, with a parametrised decision table. This is the evidence
that your model is faithful — and the regression guard when the agent changes.
