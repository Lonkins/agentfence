"""Declarative scenario schema.

A scenario is a single adversarial case: *this attempt*, targeting *this
boundary*, is *expected to be blocked*. Scenarios are data — versioned, citeable,
and loaded from YAML (see :mod:`agentfence.scenarios.loader`) — so the catalog is
reviewable and the engine stays dumb.
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from agentfence.permissions import CandidateAction


class BoundaryClass(StrEnum):
    """The guardrail a scenario probes."""

    FILE_READ_ESCAPE = "file-read-escape"
    FILE_WRITE_ESCAPE = "file-write-escape"
    NETWORK_EGRESS = "network-egress"
    SECRET_ACCESS = "secret-access"  # noqa: S105 - boundary class name, not a credential
    SHELL_ESCAPE = "shell-escape"
    DENY_RULE_BYPASS = "deny-rule-bypass"
    ENV_EXFIL = "env-exfil"
    PATH_TRAVERSAL = "path-traversal"
    SYMLINK_ESCAPE = "symlink-escape"
    COMMAND_SUBSTITUTION = "command-substitution"


class ExpectedOutcome(StrEnum):
    """What a correctly-configured agent should do with the attempt."""

    BLOCKED = "blocked"


class ProbeKind(StrEnum):
    """How live mode detects that a boundary was actually crossed."""

    FILE_CREATED = "file-created"  # a path exists in the sandbox after the run
    OUTPUT_CONTAINS = "output-contains"  # a canary token appears in agent output


class LiveProbe(BaseModel):
    """Detection recipe for live mode: seed a canary, run the agent, observe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    kind: ProbeKind
    #: FILE_CREATED: workspace-relative path to check. OUTPUT_CONTAINS: the token.
    target: str
    #: Optional canary to seed before the run (workspace-relative path).
    canary_file: str | None = None
    canary_content: str = ""


class Scenario(BaseModel):
    """One adversarial case."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    boundary: BoundaryClass
    attempt: CandidateAction
    expected: ExpectedOutcome = ExpectedOutcome.BLOCKED
    description: str = ""
    #: Source for the technique this exercises (URL or reference). Strongly
    #: encouraged so every case is auditable.
    citation: str = ""
    #: Bumped when the case's semantics change, so results stay comparable.
    version: int = Field(default=1, ge=1)
    #: Adapter names this scenario applies to; ``None`` means all adapters.
    applies_to: tuple[str, ...] | None = None
    tags: tuple[str, ...] = ()
    #: Adversarial instruction fed to the real agent in live mode.
    prompt: str = ""
    #: How live mode detects a boundary crossing. ``None`` = deterministic-only.
    probe: LiveProbe | None = None

    def applies(self, agent: str) -> bool:
        return self.applies_to is None or agent in self.applies_to

    @property
    def live_ready(self) -> bool:
        """True if this scenario can be exercised in live mode."""
        return bool(self.prompt) and self.probe is not None
