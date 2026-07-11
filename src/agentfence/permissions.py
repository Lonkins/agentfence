"""Core permission primitives shared by adapters, scenarios, and the engine.

These types are agent-agnostic. An :class:`~agentfence.adapters.base.AgentAdapter`
parses a specific agent's config into a :class:`PermissionModel` and evaluates a
:class:`CandidateAction` against it, returning a :class:`PermissionDecision`.
"""

from __future__ import annotations

import re
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

# Common tool names across the agents we model. Kept as plain strings (the set is
# open — adapters may use their own names) with constants for the frequent ones.
TOOL_BASH = "Bash"
TOOL_READ = "Read"
TOOL_WRITE = "Write"
TOOL_EDIT = "Edit"
TOOL_WEBFETCH = "WebFetch"
TOOL_WEBSEARCH = "WebSearch"

# Tools whose specifier is a filesystem path.
PATH_TOOLS = frozenset({TOOL_READ, TOOL_WRITE, TOOL_EDIT, "MultiEdit", "NotebookEdit"})
# Tools whose specifier is a URL / domain.
WEB_TOOLS = frozenset({TOOL_WEBFETCH, TOOL_WEBSEARCH})

_RULE_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_-]*)\s*(?:\((.*)\)\s*)?$", re.DOTALL)


class PermissionDecision(StrEnum):
    """What an agent's permission engine would do with a candidate action."""

    ALLOW = "allow"
    DENY = "deny"
    ASK = "ask"


class Rule(BaseModel):
    """A single parsed permission rule, e.g. ``Bash(curl:*)``."""

    model_config = ConfigDict(frozen=True)

    tool: str
    specifier: str | None = None
    raw: str

    @classmethod
    def parse(cls, raw: str) -> Rule:
        """Parse a ``Tool`` or ``Tool(specifier)`` rule string.

        A bare tool name (no parentheses) becomes a rule with ``specifier=None``
        that matches any invocation of that tool.
        """
        match = _RULE_RE.match(raw)
        if match is None:
            # Unrecognised syntax is preserved verbatim as a bare-tool rule so a
            # malformed config never silently drops a rule the author intended.
            return cls(tool=raw.strip(), specifier=None, raw=raw)
        tool, specifier = match.group(1), match.group(2)
        return cls(tool=tool, specifier=specifier, raw=raw)


class CandidateAction(BaseModel):
    """A tool call to test against a permission model.

    ``value`` is the command (for Bash), the path (for file tools), or the URL
    (for web tools). ``description`` is a short human label for reports.
    """

    model_config = ConfigDict(frozen=True)

    tool: str
    value: str
    description: str = ""


class PermissionModel(BaseModel):
    """A normalized allow/deny/ask policy loaded from an agent config."""

    model_config = ConfigDict(frozen=True)

    agent: str
    allow: tuple[Rule, ...] = ()
    deny: tuple[Rule, ...] = ()
    ask: tuple[Rule, ...] = ()
    # Decision when no rule matches. Most agents prompt the user, i.e. ASK.
    default_decision: PermissionDecision = PermissionDecision.ASK
    source: str = ""

    @property
    def rule_count(self) -> int:
        return len(self.allow) + len(self.deny) + len(self.ask)
