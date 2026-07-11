# agentfence

> Conformance testing for CLI coding-agent permission boundaries.

**agentfence** takes a CLI coding agent's permission/deny configuration and
*empirically proves whether the boundary actually holds* — by running a battery
of adversarial scenarios against the agent's own policy-decision path (and,
optionally, the live agent binary inside an isolated Docker sandbox) rather than
trusting the config on paper.

A permission config that *looks* locked down often isn't. A `deny` rule for
`Bash(curl:*)` does nothing against `bash -c "curl evil.com"`,
`$(command -v curl) evil.com`, or a leading env-var assignment — the
[May-2026 Claude Code deny-rule enforcement class](docs/threat-model.md).
agentfence turns that "it depends" into a pass/fail you can put in CI.

Bootstrapping in progress — see [the build plan](#status).

## Status

Early bootstrap. The full feature set (deterministic policy engine, Docker
sandbox runner, adapters for Claude Code / Codex CLI / OpenCode, scenario
library, reporters, and GitHub Action) lands across a series of reviewed PRs.

## License

[Apache-2.0](LICENSE) © 2026 Tom Price
