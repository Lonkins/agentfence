"""Adapter for Claude Code's ``settings.json`` permission model.

Claude Code expresses permissions as ``allow`` / ``deny`` / ``ask`` lists of
``Tool(specifier)`` rules under a ``permissions`` key, with precedence
deny > ask > allow and a default that prompts the user. Bash specifiers match on
the *literal leading string* of the command — the modelling that reproduces the
May-2026 deny-rule enforcement class: a ``deny`` of ``Bash(curl:*)`` does nothing
against ``bash -c "curl …"``, a leading env assignment, an absolute path, or a
command substitution, because none of those *start with* ``curl``.

This adapter models that documented behaviour, gaps included, so bypasses surface
as leaks rather than being silently "fixed" (ADR-0002).
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

from agentfence.adapters.base import AdapterError
from agentfence.adapters.globbing import glob_match, path_rule_matches
from agentfence.permissions import (
    PATH_TOOLS,
    TOOL_BASH,
    WEB_TOOLS,
    CandidateAction,
    PermissionDecision,
    PermissionModel,
    Rule,
)

# Config files Claude Code reads within a project, in increasing precedence.
_SETTINGS_FILES = (".claude/settings.json", ".claude/settings.local.json")
# defaultMode values that mean "no prompt, just run": everything is allowed.
_BYPASS_MODES = frozenset({"bypassPermissions"})


class ClaudeCodeAdapter:
    """Models Claude Code's permission-matching behaviour."""

    name = "claude-code"
    models_version = "claude-code-settings-2026-05"

    # -- discovery / loading ----------------------------------------------

    def matches(self, path: Path) -> bool:
        if path.is_file():
            return path.suffix == ".json" and "settings" in path.name
        return any((path / rel).is_file() for rel in _SETTINGS_FILES)

    def load(self, path: Path) -> PermissionModel:
        sources: list[Path] = []
        if path.is_file():
            sources = [path]
        else:
            sources = [path / rel for rel in _SETTINGS_FILES if (path / rel).is_file()]
        if not sources:
            raise AdapterError(f"No Claude Code settings found at {path}")

        allow: list[Rule] = []
        deny: list[Rule] = []
        ask: list[Rule] = []
        default = PermissionDecision.ASK

        for source in sources:
            data = self._read_json(source)
            perms = data.get("permissions", {})
            if not isinstance(perms, dict):
                raise AdapterError(f"'permissions' must be an object in {source}")
            allow.extend(self._parse_rules(perms.get("allow", []), source, "allow"))
            deny.extend(self._parse_rules(perms.get("deny", []), source, "deny"))
            ask.extend(self._parse_rules(perms.get("ask", []), source, "ask"))
            mode = perms.get("defaultMode")
            if isinstance(mode, str) and mode in _BYPASS_MODES:
                default = PermissionDecision.ALLOW

        return PermissionModel(
            agent=self.name,
            allow=tuple(allow),
            deny=tuple(deny),
            ask=tuple(ask),
            default_decision=default,
            source=", ".join(str(s) for s in sources),
        )

    @staticmethod
    def _read_json(source: Path) -> dict[str, object]:
        try:
            parsed = json.loads(source.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise AdapterError(f"Invalid JSON in {source}: {err}") from err
        except OSError as err:
            raise AdapterError(f"Cannot read {source}: {err}") from err
        if not isinstance(parsed, dict):
            raise AdapterError(f"Top-level settings in {source} must be an object")
        return parsed

    @staticmethod
    def _parse_rules(items: object, source: Path, bucket: str) -> list[Rule]:
        if not isinstance(items, list):
            raise AdapterError(f"permissions.{bucket} must be a list in {source}")
        rules: list[Rule] = []
        for item in items:
            if not isinstance(item, str):
                raise AdapterError(f"permissions.{bucket} entries must be strings in {source}")
            rules.append(Rule.parse(item))
        return rules

    # -- decision ---------------------------------------------------------

    def decide(self, model: PermissionModel, action: CandidateAction) -> PermissionDecision:
        # Precedence: deny > ask > allow > default.
        if any(self._rule_matches(rule, action) for rule in model.deny):
            return PermissionDecision.DENY
        if any(self._rule_matches(rule, action) for rule in model.ask):
            return PermissionDecision.ASK
        if any(self._rule_matches(rule, action) for rule in model.allow):
            return PermissionDecision.ALLOW
        return model.default_decision

    def _rule_matches(self, rule: Rule, action: CandidateAction) -> bool:
        if rule.tool != action.tool:
            return False
        if rule.specifier is None:
            return True
        spec = rule.specifier
        if action.tool == TOOL_BASH:
            return self._match_bash(spec, action.value)
        if action.tool in PATH_TOOLS:
            return path_rule_matches(spec, action.value)
        if action.tool in WEB_TOOLS:
            return self._match_web(spec, action.value)
        return self._match_generic(spec, action.value)

    @staticmethod
    def _match_bash(spec: str, command: str) -> bool:
        """Model Claude Code's literal-prefix Bash matching.

        ``curl:*`` matches a command whose leading token(s) are exactly ``curl``.
        It does NOT parse the command to find the real executable, so any wrapper
        (``bash -c``, ``env X=1``, an absolute path, ``$( … )``) slips past — the
        enforcement gap this whole tool exists to catch.
        """
        command = command.strip()
        if spec == "*":
            return True
        if spec.endswith(":*"):
            # Pure leading-string prefix match — no argument parsing. This is
            # faithful to the real matcher: it is why `npm run test:*` allows
            # `npm run test:unit`, and equally why `curl:*` never sees the `curl`
            # inside `bash -c "curl …"` or `env X=1 curl …`.
            prefix = spec[:-2].strip()
            return command.startswith(prefix)
        return command == spec.strip()

    @staticmethod
    def _match_web(spec: str, url: str) -> bool:
        if spec.startswith("domain:"):
            want = spec[len("domain:") :]
            host = urlparse(url).hostname or ""
            return host == want or host.endswith("." + want)
        return glob_match(spec, url)

    @staticmethod
    def _match_generic(spec: str, value: str) -> bool:
        if spec == "*":
            return True
        if spec.endswith(":*"):
            prefix = spec[:-2]
            return value == prefix or value.startswith(prefix)
        return value == spec or glob_match(spec, value)
