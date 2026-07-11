# Threat model

## What agentfence protects against

agentfence answers one question: **will this agent's permission boundary
actually stop a hostile action?** It exists because permission configs routinely
*look* locked down while leaking in practice.

### The deny-rule enforcement class

The motivating case (surfaced widely around May 2026): permission systems that
match a `deny` rule against the *leading string* of a command. A rule like
`Bash(curl:*)` is defeated by anything that shifts the first token:

| Bypass | Why the prefix matcher misses it |
|---|---|
| `bash -c "curl …"` | leading token is `bash` |
| `sh -c "curl …"` | leading token is `sh` |
| `env X=1 curl …` | leading token is `env` (or `X=1`) |
| `/usr/bin/curl …` | not the literal string `curl` |
| `true; curl …` | only the first token is inspected |
| `c$(echo u)rl …` | assembled at runtime |

The denied program still runs. Cross-tool gaps are just as common: a
`Read(./.env)` deny does nothing about `cat .env` under a broadly-allowed `Bash`.
agentfence encodes these as versioned, cited [scenarios](scenarios.md) and proves
whether your config stops them.

## Isolation guarantees (and their limits)

The **deterministic** engine runs no untrusted code. It evaluates candidate
actions against an in-process model of the agent's permission engine. There is
nothing to escape.

The **sandbox runner** (live mode and sandbox-backed scenarios) executes real
commands inside a Docker container created per run with:

- `network_mode=none` by default (egress scenarios assert the *attempt* is
  blocked, not that traffic succeeds);
- a read-only root filesystem with a small tmpfs workspace — nothing persists;
- a non-root user, `cap_drop=[ALL]`, `no-new-privileges`, and CPU/memory/pids
  caps;
- no host bind mounts beyond the config under test.

The runner **fails closed**: if it cannot apply these controls, it refuses to
run. See [ADR-0003](adr/0003-docker-sandbox-isolation.md).

!!! warning "Container isolation is not a kernel boundary"
    These controls stop the *modelled* attacks and ordinary mistakes. They are
    **not** a defense against a determined kernel-level container escape. Do not
    run **live mode** against an agent, config, or prompt you do not control, and
    never outside the provided sandbox. Prefer rootless Docker or a rootless
    runtime.

## Live mode's network trade-off

Reaching a real model needs network, so a real live run typically enables
network in the sandbox. Detection then relies on the [probe](how-it-works.md)
(a canary file appearing, a secret token in output), not on network isolation.
This is an explicit, opt-in trade-off — see [safe usage](safe-usage.md).

## Out of scope

agentfence tests the *guardrails of existing agents*. It is not a harness for
doing agent work, not a sandbox for running untrusted agents in production, and
not a new coding agent. It does not audit agent source code or model weights.
