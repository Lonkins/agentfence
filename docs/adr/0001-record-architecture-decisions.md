# 1. Record architecture decisions

Date: 2026-07-11

## Status

Accepted

## Context

agentfence makes security claims about other tools. The reasoning behind its
design — especially *how* it decides a boundary held or leaked — must be
auditable, or its own verdicts are not trustworthy. Decisions need to be
discoverable long after the commit that made them scrolls out of view.

## Decision

We keep lightweight Architecture Decision Records (ADRs) in `docs/adr/`, one
Markdown file per decision, numbered sequentially, following the
[Nygard format](https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions.html).
An ADR is written whenever a decision would otherwise only live in a maintainer's
head: engine semantics, isolation model, adapter scope, report formats.

## Consequences

- Contributors and auditors can trace *why* the tool behaves as it does.
- ADRs are immutable once accepted; a reversal is a new ADR that supersedes the old.
- Trivial or easily reversible choices do not need an ADR.
