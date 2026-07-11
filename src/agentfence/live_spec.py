"""How to drive a real agent binary in live mode.

Kept in a dependency-free module so adapters can declare a ``live_spec`` without
importing the engine (which would create an import cycle).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict

if TYPE_CHECKING:
    from agentfence.adapters.base import AgentAdapter


class LiveSpec(BaseModel):
    """Headless invocation recipe for one agent.

    ``argv_template`` tokens are used verbatim except ``{prompt}``, which is
    replaced with the scenario's adversarial prompt. The agent config is written
    to ``config_dest`` (relative to the sandbox workdir) before the run.
    """

    model_config = ConfigDict(frozen=True)

    binary: str
    argv_template: tuple[str, ...]
    config_dest: str
    required_env: tuple[str, ...] = ()

    def build_argv(self, prompt: str) -> list[str]:
        return [prompt if tok == "{prompt}" else tok for tok in self.argv_template]


def get_live_spec(adapter: AgentAdapter) -> LiveSpec | None:
    """Return an adapter's live spec, if it declares one."""
    spec = getattr(adapter, "live_spec", None)
    return spec if isinstance(spec, LiveSpec) else None
