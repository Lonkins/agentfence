# GitHub Action

Gate every PR on your coding agent's permission boundary actually holding. The
Action runs the deterministic battery (zero network, zero LLM) against your
committed config and fails the build on any leak.

```yaml
name: agent-guardrails
on: [pull_request]
permissions:
  contents: read
  security-events: write   # for SARIF upload (the default)
jobs:
  agentfence:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: Lonkins/agentfence@v0.1.0
        with:
          config: .            # a file or a directory to search
```

## Inputs

| Input | Default | Description |
|---|---|---|
| `config` | — (required) | Config file, or directory to search. |
| `agent` | autodetect | `claude-code`, `codex`, or `opencode`. |
| `boundaries` | all | Space-separated boundary classes to restrict the run. |
| `strict-ask` | `false` | Treat a human prompt (ASK) as a leak. |
| `fail-on-leak` | `true` | Fail the job on any leak or error. |
| `sarif-file` | `agentfence.sarif` | Where to write the SARIF report. |
| `upload-sarif` | `true` | Upload SARIF to GitHub code scanning. |
| `agentfence-spec` | `agentfence` | pip install spec (pin a version, or `.` for a checkout). |
| `python-version` | `3.12` | Python used to run agentfence. |

## Outputs

| Output | Description |
|---|---|
| `exit-code` | agentfence exit code (`0` clean, `1` leak/error). |

## SARIF in code scanning

With `upload-sarif: true` (and `security-events: write`), leaks appear in the
repository's **Security → Code scanning** tab, anchored at the config file.

## Self-tested

The Action is proven in agentfence's own CI: a
[self-test workflow](https://github.com/Lonkins/agentfence/blob/main/.github/workflows/action-selftest.yml)
asserts it **fails** a deliberately weak config and **passes** a hardened one on
every push.
