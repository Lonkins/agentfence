# agentfence

**Conformance testing for CLI coding-agent permission boundaries.**

agentfence takes a CLI coding agent's permission/deny configuration and
*empirically proves whether the boundary actually holds* — rather than trusting
the config on paper.

A permission config that *looks* locked down often isn't. A `deny` rule for
`Bash(curl:*)` does nothing against `bash -c "curl evil.com"`,
`env X=1 curl evil.com`, or a leading path — the
[May-2026 deny-rule enforcement class](threat-model.md). agentfence turns that
"it depends" into a pass/fail you can put in CI.

## Two modes

- **Deterministic (default, zero-spend):** feeds candidate tool calls through a
  faithful model of the agent's own permission engine and asserts allow/deny.
  No model, no network, no side effects — instant and reproducible.
- **Live (opt-in, bring-your-own-key):** drives the real agent binary with
  adversarial prompts inside an isolated Docker sandbox and watches whether the
  blocked action actually happens.

## Supported agents

| Agent | Config | Permission model |
|---|---|---|
| Claude Code | `.claude/settings.json` | allow/deny/ask rules |
| Codex CLI | `.codex/config.toml` | sandbox mode + approval policy |
| OpenCode | `opencode.json` | per-tool levels |

## What it checks

Ten boundary classes: deny-rule bypass, network egress, secret access,
file read/write escape, path traversal, symlink escape, shell escape, command
substitution, and environment-variable exfiltration. Every scenario is
versioned and cited — see the [catalog](scenarios.md).

## Get started

```bash
pip install agentfence
agentfence run .            # autodetects your agent config
```

Then wire it into CI with the [GitHub Action](github-action.md).
