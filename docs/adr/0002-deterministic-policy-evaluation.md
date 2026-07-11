# 2. Deterministic mode models the agent's permission engine in-process

Date: 2026-07-11

## Status

Accepted

## Context

The core promise of agentfence is a **zero-spend, zero-LLM** default that still
tells the truth about whether a permission boundary holds. There are three ways
to decide whether an agent would allow a candidate action:

1. **Drive the real agent** with an adversarial prompt and watch what it does
   (live mode). Truthful, but needs a model in the loop (cost, non-determinism)
   and a sandbox for every case.
2. **Invoke the agent's own permission-check code** as a library. Ideal in
   theory, but the CLI agents we target (Claude Code, Codex CLI, OpenCode) do
   not expose a stable, importable "would you allow X?" entry point, and pinning
   to their internals would break constantly.
3. **Re-implement the agent's documented permission-matching semantics** as a
   small, well-tested evaluator, and feed candidate actions through it.

## Decision

Deterministic mode takes option 3: each `AgentAdapter` ships a faithful model of
its target agent's *documented* permission-matching rules (rule syntax, match
precedence, command tokenization, path globbing). agentfence feeds each
scenario's candidate action through that model and asserts allow/deny/ask.

The model is deliberately conservative: where the real agent's matcher is known
to be *permissive* in a way that enables a bypass (e.g. prefix-only command
matching that misses `bash -c "curl …"`), the model reproduces that permissive
behavior so the bypass surfaces as a **LEAK**. It does not "fix" the agent's
matcher — that would hide the very defect we exist to find.

Every modeled matcher is pinned to a cited source (the agent's permission docs
and, where relevant, the specific enforcement bug) and covered by golden
fixtures that assert both the leaking and the hardened outcome.

## Consequences

- The default battery runs offline, instantly, and reproducibly — good for CI.
- Fidelity is bounded by our model of each agent's documented behavior. When an
  agent changes its matcher, the adapter must be updated; adapters therefore
  carry a `models_version` and cite the behavior they encode.
- Live mode (ADR-0004, opt-in) exists precisely to cross-check the model against
  the real binary when a user wants ground truth.
- A modeled matcher can drift from reality. We mitigate with citations, golden
  fixtures, and a documented "this models documented behavior, not the binary"
  caveat in every report.
