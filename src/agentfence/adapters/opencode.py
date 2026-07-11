"""Adapter for OpenCode's ``permission`` configuration.

OpenCode assigns each tool a level — ``allow`` / ``ask`` / ``deny`` — and for
``bash`` (and optionally ``edit``) accepts a map of glob patterns to levels, with
``*`` as the catch-all. The **most specific matching pattern wins** (not a
deny-precedence), which is exactly why ``{"*": "allow", "curl*": "deny"}`` denies
``curl …`` yet still allows ``bash -c "curl …"`` — the same deny-rule bypass
class, expressed in a different config shape.
"""

from __future__ import annotations

import fnmatch
import json
import re
from pathlib import Path
from typing import Any

from agentfence.adapters.base import AdapterError
from agentfence.permissions import (
    WEB_TOOLS,
    CandidateAction,
    PermissionDecision,
    PermissionModel,
)

_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})
_CONFIG_FILES = ("opencode.json", "opencode.jsonc")
_LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)

_LEVELS: dict[str, PermissionDecision] = {
    "allow": PermissionDecision.ALLOW,
    "deny": PermissionDecision.DENY,
    "ask": PermissionDecision.ASK,
}


def _level_to_decision(level: str) -> PermissionDecision:
    return _LEVELS.get(level, PermissionDecision.ASK)


def _specificity(pattern: str) -> int:
    """Literal (non-wildcard) length — the more literal chars, the more specific."""
    return len(pattern.replace("*", "").replace("?", ""))


def _resolve_level(value: object, subject: str, default: str) -> str:
    """Resolve a tool's level for ``subject`` (a command / path / url).

    ``value`` is either a bare level string or a map of glob patterns to levels.
    For a map, the most specific matching pattern wins.
    """
    if isinstance(value, str):
        return value
    if isinstance(value, dict):
        best_level: str | None = None
        best_score = -1
        for pattern, level in value.items():
            if not isinstance(pattern, str) or not isinstance(level, str):
                continue
            if fnmatch.fnmatchcase(subject, pattern) and _specificity(pattern) > best_score:
                best_score = _specificity(pattern)
                best_level = level
        return best_level if best_level is not None else default
    return default


class OpenCodeAdapter:
    """Models OpenCode's per-tool permission levels."""

    name = "opencode"
    models_version = "opencode-permission-2026-06"

    # -- discovery / loading ----------------------------------------------

    def matches(self, path: Path) -> bool:
        if path.is_file():
            return path.name in _CONFIG_FILES or (
                path.suffix in {".json", ".jsonc"} and "opencode" in path.name
            )
        return any((path / rel).is_file() for rel in _CONFIG_FILES)

    def load(self, path: Path) -> PermissionModel:
        source = self._resolve_source(path)
        raw = source.read_text(encoding="utf-8")
        # ponytail: strip only whole-line // comments — safe against "http://"
        # inside strings, unlike a naive global strip.
        cleaned = _LINE_COMMENT.sub("", raw)
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as err:
            raise AdapterError(f"Invalid JSON in {source}: {err}") from err
        if not isinstance(data, dict):
            raise AdapterError(f"Top-level config in {source} must be an object")

        permission = data.get("permission", {})
        if not isinstance(permission, dict):
            raise AdapterError(f"'permission' must be an object in {source}")

        return PermissionModel(
            agent=self.name,
            default_decision=PermissionDecision.ASK,
            source=str(source),
            metadata=dict(permission),
        )

    def _resolve_source(self, path: Path) -> Path:
        if path.is_file():
            return path
        for rel in _CONFIG_FILES:
            candidate = path / rel
            if candidate.is_file():
                return candidate
        raise AdapterError(f"No OpenCode config found at {path}")

    # -- decision ---------------------------------------------------------

    def decide(self, model: PermissionModel, action: CandidateAction) -> PermissionDecision:
        perm: dict[str, Any] = model.metadata
        tool = action.tool
        if tool == "Bash":
            level = _resolve_level(perm.get("bash", "ask"), action.value, "ask")
        elif tool in _WRITE_TOOLS:
            level = _resolve_level(perm.get("edit", "ask"), action.value, "ask")
        elif tool in WEB_TOOLS:
            level = _resolve_level(perm.get("webfetch", "ask"), action.value, "ask")
        elif tool == "Read":
            # OpenCode has no read gate by default — reads are allowed unless a
            # 'read' permission is explicitly configured.
            level = _resolve_level(perm.get("read", "allow"), action.value, "allow")
        else:
            level = "ask"
        return _level_to_decision(level)
