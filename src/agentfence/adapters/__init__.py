"""Agent adapters and the adapter registry.

Importing this package registers every built-in adapter, so
:func:`get_adapter` and :func:`available_adapters` work without extra wiring.
"""

from __future__ import annotations

from agentfence.adapters.base import (
    AdapterError,
    AgentAdapter,
    available_adapters,
    detect_adapter,
    get_adapter,
    register_adapter,
)
from agentfence.adapters.claude_code import ClaudeCodeAdapter
from agentfence.adapters.codex import CodexAdapter
from agentfence.adapters.opencode import OpenCodeAdapter

register_adapter(ClaudeCodeAdapter())
register_adapter(CodexAdapter())
register_adapter(OpenCodeAdapter())

__all__ = [
    "AdapterError",
    "AgentAdapter",
    "ClaudeCodeAdapter",
    "CodexAdapter",
    "OpenCodeAdapter",
    "available_adapters",
    "detect_adapter",
    "get_adapter",
    "register_adapter",
]
