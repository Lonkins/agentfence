# Safe usage

## Deterministic mode is always safe

The default battery runs no untrusted code, makes no network calls, and has no
side effects. Run it anywhere, including untrusted CI. There is nothing to
isolate.

## Live mode: opt-in and gated

Live mode executes the real agent binary against adversarial prompts. It is off
by default and refuses to run unless you explicitly opt in:

```bash
agentfence run . --live --i-understand-the-risks --agent claude-code
```

Preflight **fails closed** if:

- you did not pass `--i-understand-the-risks`;
- the adapter has no live spec;
- a required API-key environment variable is missing (bring-your-own-key);
- the config file is not found.

## Rules for live mode

1. **Only test what you control.** Never point live mode at an agent, config, or
   prompt from an untrusted source.
2. **Keep it in the sandbox.** Live mode runs the agent inside the Docker
   sandbox on purpose. Do not bypass it.
3. **Bring your own key.** agentfence never ships or stores credentials. You
   provide the key via the environment for your own runs.
4. **Mind the network trade-off.** A real model call needs network, so live runs
   usually enable network in the sandbox. Detection then relies on the probe,
   not on network isolation. See the [threat model](threat-model.md).
5. **Prefer rootless.** Rootless Docker (or a rootless runtime) narrows the blast
   radius of any container-escape bug.

## Reports and signing

The Markdown conformance report includes a SHA-256 integrity digest so tampering
is detectable. For attested reports from a trusted runner, set a signing key:

```bash
AGENTFENCE_SIGNING_KEY="$MY_HMAC_KEY" agentfence run . -f markdown -o report.md
```

An `HMAC-SHA256` signature over the report body is appended. Verify it with the
same key.
