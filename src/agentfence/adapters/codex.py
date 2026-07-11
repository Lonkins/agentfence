"""Adapter for the Codex CLI sandbox configuration (``config.toml``).

Codex does not use allow/deny rule lists. Its boundary is a **sandbox**: a
``sandbox_mode`` (``read-only`` / ``workspace-write`` / ``danger-full-access``),
a network toggle, a set of writable roots, and an ``approval_policy`` governing
whether commands run without a human. The boundary reasons about *capabilities*
(write here, reach the network) rather than command strings, so this adapter
decides from the structured hints on :class:`CandidateAction`.

Notably, the Codex sandbox gates writes and network but **not reads** — so a
secret-read boundary is only as strong as the approval policy. agentfence
surfaces that rather than pretending the sandbox covers it.
"""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import Any

from agentfence.adapters.base import AdapterError
from agentfence.permissions import (
    CandidateAction,
    PermissionDecision,
    PermissionModel,
)

_MODE_READ_ONLY = "read-only"
_MODE_WORKSPACE_WRITE = "workspace-write"
_MODE_FULL_ACCESS = "danger-full-access"
_APPROVAL_NEVER = "never"
_WRITE_TOOLS = frozenset({"Write", "Edit", "MultiEdit", "NotebookEdit"})

# Config locations searched inside a project directory.
_CONFIG_FILES = (".codex/config.toml", "codex.toml")


def _norm(path: str) -> str:
    path = path.strip()
    return path[:-1] if len(path) > 1 and path.endswith("/") else path


def _under_roots(path: str, roots: list[str]) -> bool:
    target = _norm(path)
    for root in roots:
        rr = _norm(root)
        if rr in ("", "."):  # the workspace itself: relative paths are inside it
            if not target.startswith("/"):
                return True
            continue
        if target == rr or target.startswith(rr + "/"):
            return True
    return False


class CodexAdapter:
    """Models the Codex CLI sandbox + approval policy."""

    name = "codex"
    models_version = "codex-cli-config-2026-06"

    # -- discovery / loading ----------------------------------------------

    def matches(self, path: Path) -> bool:
        if path.is_file():
            return path.suffix == ".toml"
        return any((path / rel).is_file() for rel in _CONFIG_FILES)

    def load(self, path: Path) -> PermissionModel:
        source = self._resolve_source(path)
        try:
            data = tomllib.loads(source.read_text(encoding="utf-8"))
        except tomllib.TOMLDecodeError as err:
            raise AdapterError(f"Invalid TOML in {source}: {err}") from err
        except OSError as err:
            raise AdapterError(f"Cannot read {source}: {err}") from err

        mode = str(data.get("sandbox_mode", _MODE_READ_ONLY))
        approval = str(data.get("approval_policy", "on-request"))
        ws = data.get("sandbox_workspace_write", {})
        if not isinstance(ws, dict):
            raise AdapterError(f"'sandbox_workspace_write' must be a table in {source}")
        network = bool(ws.get("network_access", False))
        roots_raw = ws.get("writable_roots", [])
        if not isinstance(roots_raw, list) or not all(isinstance(r, str) for r in roots_raw):
            raise AdapterError(f"writable_roots must be a list of strings in {source}")

        metadata: dict[str, Any] = {
            "sandbox_mode": mode,
            "approval_policy": approval,
            "network_access": network,
            "writable_roots": list(roots_raw),
        }
        return PermissionModel(
            agent=self.name,
            default_decision=PermissionDecision.ASK,
            source=str(source),
            metadata=metadata,
        )

    def _resolve_source(self, path: Path) -> Path:
        if path.is_file():
            return path
        for rel in _CONFIG_FILES:
            candidate = path / rel
            if candidate.is_file():
                return candidate
        raise AdapterError(f"No Codex config found at {path}")

    # -- decision ---------------------------------------------------------

    def decide(self, model: PermissionModel, action: CandidateAction) -> PermissionDecision:
        mode = str(model.metadata.get("sandbox_mode", _MODE_READ_ONLY))
        approval = str(model.metadata.get("approval_policy", "on-request"))
        network = bool(model.metadata.get("network_access", False))
        roots = [str(r) for r in model.metadata.get("writable_roots", [])]

        if mode == _MODE_FULL_ACCESS:
            # No sandbox at all: everything the model asks for runs.
            return PermissionDecision.ALLOW

        if action.network_egress:
            permitted = mode == _MODE_WORKSPACE_WRITE and network
            return PermissionDecision.ALLOW if permitted else PermissionDecision.DENY

        # A write is signalled by the explicit hint, or by a write-capable file
        # tool whose value is the target path.
        write_target = action.writes_path
        if write_target is None and action.tool in _WRITE_TOOLS:
            write_target = action.value
        if write_target is not None:
            if mode == _MODE_READ_ONLY:
                return PermissionDecision.DENY
            under = _under_roots(write_target, roots)
            return PermissionDecision.ALLOW if under else PermissionDecision.DENY

        # Reads and other commands are not gated by the sandbox — only the
        # approval policy stands between the agent and a secret file.
        return self._approval_decision(approval)

    @staticmethod
    def _approval_decision(approval: str) -> PermissionDecision:
        return PermissionDecision.ALLOW if approval == _APPROVAL_NEVER else PermissionDecision.ASK
