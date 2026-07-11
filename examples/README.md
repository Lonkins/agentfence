# Examples

## Demo configs

- **`demo-weak-config/`** — a deliberately loose Claude Code config: it broadly
  allows `Bash` and tries to stop network egress with a naive `deny` of
  `Bash(curl:*)`. agentfence proves that `bash -c "curl …"`, `env X=1 curl …`,
  and `cat .env` all slip past it. Running the Action against this config
  **fails** the build.
- **`demo-hardened-config/`** — the same intent, done right: the dangerous
  wrappers and exfil tools are denied and only a safe allowlist auto-runs. The
  same battery is **clean**.

Try locally:

```bash
pip install agentfence
agentfence run examples/demo-weak-config --agent claude-code       # exit 1
agentfence run examples/demo-hardened-config --agent claude-code   # exit 0
```

## GitHub Action

`workflow.yml` is a copy-paste workflow for your own repo. Drop it in
`.github/workflows/`, point `config:` at your committed agent config, and every
PR is gated on the permission boundary actually holding.

The Action is self-tested in this repo by
[`.github/workflows/action-selftest.yml`](../.github/workflows/action-selftest.yml),
which asserts the weak config fails and the hardened config passes on every push.

### Inputs

| Input | Default | Description |
|---|---|---|
| `config` | — (required) | Config file or directory to search. |
| `agent` | autodetect | `claude-code`, `codex`, or `opencode`. |
| `boundaries` | all | Space-separated boundary classes to restrict the run. |
| `strict-ask` | `false` | Count a human prompt (ASK) as a leak. |
| `fail-on-leak` | `true` | Fail the job on any leak or error. |
| `upload-sarif` | `true` | Upload SARIF to GitHub code scanning. |
| `agentfence-spec` | `agentfence` | pip install spec (pin a version, or `.` for a checkout). |
