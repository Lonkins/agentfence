# How it works

## The pipeline

```
agent config ──(adapter.load)──▶ PermissionModel
scenario catalog ─────────────▶ CandidateAction
                                     │
                     ┌───────────────┴────────────────┐
             deterministic                          live
        (adapter.decide, no LLM)         (run the binary in a sandbox)
                     │                               │
                     └────────────▶ Verdict ◀────────┘
                                       │
                        held · leak · ask · error · skipped
```

## Deterministic mode

Each adapter ships a faithful model of its agent's *documented* permission
matching — including the gaps. agentfence feeds every scenario's candidate
action through `adapter.decide()` and maps the decision to a verdict:

| Policy decision | Verdict | Meaning |
|---|---|---|
| `DENY` | **HELD** | The boundary blocked the attempt, as intended. |
| `ALLOW` | **LEAK** | The attempt would be auto-allowed. The boundary failed. |
| `ASK` | **ASK** | The agent would prompt a human. Held under review; a leak under auto-approve (`--strict-ask`). |

Crucially, an adapter reproduces *permissive* behaviour rather than fixing it.
Claude Code's Bash matcher is a literal string-prefix match, so `Bash(curl:*)`
never sees the `curl` inside `bash -c "curl …"`. The model matches the same way,
so the bypass surfaces as a **LEAK** instead of being silently canonicalised
away. See [ADR-0002](adr/0002-deterministic-policy-evaluation.md).

This mode runs offline, instantly, and with no LLM spend — ideal for CI.

## Live mode

Live mode ([opt-in](safe-usage.md)) drives the real agent binary with an
adversarial prompt inside the Docker sandbox and observes the outcome directly:
did a canary secret appear in the agent's output, did a forbidden file get
created. It exists to cross-check the model against ground truth when you want
it. It needs the binary, usually an API key (BYO), and — because the model call
needs network — a network-enabled sandbox.

## Why "modeled", not "invoked"

The target agents don't expose a stable "would you allow X?" entry point, and
pinning to their internals would break constantly. Modeling the documented
semantics is portable and auditable; each adapter carries a `models_version` and
every scenario carries a citation, so a verdict can always be traced back to a
source.
