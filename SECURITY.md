# Security Policy

## Reporting a vulnerability

agentfence is a security tool. If you find a vulnerability **in agentfence
itself** — for example a sandbox-escape in the runner, or a way to make the
deterministic engine report a leaking config as clean — please report it
privately.

- **Preferred:** open a [GitHub private security advisory](https://github.com/Lonkins/agentfence/security/advisories/new).
- **Email:** tomprice13@pm.me

Please include a description, affected version, and reproduction steps. We aim
to acknowledge within 72 hours and to ship a fix or mitigation before any
public disclosure. Please do not open a public issue for a vulnerability.

## Scope and threat model

agentfence executes adversarial scenarios. The **deterministic** engine runs no
untrusted code — it evaluates candidate actions against a modeled permission
engine in-process. The **live** engine and the sandbox runner execute real
commands, and are designed to do so inside an isolated, network-disabled,
ephemeral Docker container. See [docs/threat-model.md](docs/threat-model.md)
for the isolation guarantees and their limits.

**Do not run live mode against a config or agent you do not control, and never
outside the provided sandbox.** The sandbox reduces but does not eliminate risk;
container isolation is not a security boundary against a determined kernel-level
attacker.

## Supported versions

The latest released minor version receives security fixes. Pre-1.0, only the
newest release is supported.
