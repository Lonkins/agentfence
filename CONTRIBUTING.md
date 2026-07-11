# Contributing to agentfence

Thanks for your interest. agentfence is a security tool, so correctness and
reproducibility matter more than speed. Small, well-tested, well-scoped changes
are the norm.

## Development setup

Requires [`uv`](https://docs.astral.sh/uv/) and Python 3.12+. Docker is only
needed for sandbox and live-mode tests.

```bash
git clone https://github.com/Lonkins/agentfence
cd agentfence
uv sync --all-extras --dev
uv run pre-commit install
```

## The loop

```bash
uv run ruff format .          # format
uv run ruff check --fix .     # lint
uv run mypy                   # strict types
uv run pytest -m "not docker and not live"   # fast tests
uv run pytest -m docker       # sandbox tests (needs Docker)
```

Every push runs the same checks in CI. Pre-commit runs a subset locally.
Never bypass the hooks with `--no-verify`; if a hook fails, fix the cause.

## Pull requests

- Branch off `main`. Use a descriptive branch name (`feat/…`, `fix/…`, `docs/…`).
- Follow [Conventional Commits](https://www.conventionalcommits.org/) for commit
  and PR titles. PRs are **squash-merged**, so the PR title becomes history.
- Keep PRs atomic and self-explanatory. Include tests for behavior changes and
  docs for user-facing changes.
- CI must be green before merge. `main` is protected.

## Adding a scenario

Scenarios live in `src/agentfence/scenarios/catalog/` as versioned YAML. Each
case declares the `attempt`, the `boundary` it targets, and the `expected`
verdict. See the [scenario catalog docs](docs/scenarios.md) and the
[scenario schema](src/agentfence/scenarios/schema.py). A new scenario needs a
citation for the technique it exercises and at least one fixture config that
proves both the leaking and hardened outcomes.

## Adding an agent adapter

Implement the `AgentAdapter` protocol (see `src/agentfence/adapters/base.py`)
and the [adapter authoring guide](docs/adapters.md). An adapter must faithfully
model the target agent's documented permission-matching semantics and ship
golden fixtures.

## Security

Do not open public issues for vulnerabilities. See [SECURITY.md](SECURITY.md).
