# 3. Sandbox isolation uses rootless, networkless, ephemeral Docker

Date: 2026-07-11

## Status

Accepted

## Context

Live mode and some sandbox-backed scenarios execute real commands that are, by
design, attempts to escape a boundary (write outside a workspace, reach the
network, read a credential file). This code must not touch the host.

## Decision

All untrusted execution happens inside a Docker container created per run with:

- `network_mode="none"` — no egress by default; network-egress scenarios assert
  the *attempt is blocked*, not that traffic succeeds.
- `read_only=True` root filesystem, with a single small `tmpfs` workspace mount;
  nothing persists after the container is removed (`auto_remove`, ephemeral).
- A non-root user (`--user`), `cap_drop=["ALL"]`, `no-new-privileges`, a locked
  seccomp profile, and strict CPU/memory/pids/time limits.
- No bind mounts of host paths into the container except a read-only copy of the
  agent config under test.

The runner refuses to execute if it cannot apply these controls (fail closed).

## Consequences

- The host filesystem, network, and credentials are not reachable from scenario
  code under normal container isolation.
- Container isolation is **not** a defense against kernel-level escapes. The
  threat model (docs/threat-model.md) states this plainly; users are told never
  to run live mode against agents or configs they do not control.
- Docker is an optional dependency (`agentfence[sandbox]`); the deterministic
  core never needs it, keeping the default install light and the default battery
  runnable with no daemon.
- macOS/Windows run Docker in a VM, which adds a layer; on native Linux we rely
  on the controls above. Rootless Docker or a rootless runtime is recommended
  and documented.
