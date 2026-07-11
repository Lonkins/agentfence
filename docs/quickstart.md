# Quickstart

## Install

```bash
pip install agentfence
# or, for live mode and sandbox-backed scenarios:
pip install "agentfence[sandbox]"
```

Requires Python 3.12+. The deterministic core needs nothing else. Docker is only
needed for live mode.

## Run the battery

Point agentfence at your agent config — a file, or a directory it will search:

```bash
agentfence run .                          # autodetect the agent
agentfence run .claude/settings.json --agent claude-code
```

Exit code is the contract: **0** clean, **1** a leak (or error), **2** a usage
error. That is what makes it CI-ready.

## Output formats

```bash
agentfence run . -f table                 # rich terminal table (default)
agentfence run . -f json  -o report.json  # machine-readable
agentfence run . -f sarif -o report.sarif # GitHub code scanning
agentfence run . -f markdown -o report.md # signed conformance report
```

The Markdown report carries a SHA-256 integrity stamp. Set
`AGENTFENCE_SIGNING_KEY` to also append an HMAC-SHA256 signature.

## Narrow the run

```bash
agentfence run . -b deny-rule-bypass -b network-egress   # only these classes
agentfence run . --strict-ask                            # treat prompts as leaks
```

`--strict-ask` is for unattended / auto-approve agents, where a "the tool would
ask a human" outcome is really a leak because no human is there to say no.

## Explore

```bash
agentfence agents        # list adapters
agentfence scenarios     # list the catalog
```
