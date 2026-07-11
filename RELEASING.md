# Releasing

Releases are cut by pushing a `v*` tag. The [`release`](.github/workflows/release.yml)
workflow then:

1. runs the full gate (ruff, mypy, pytest);
2. builds the sdist + wheel;
3. creates a GitHub Release with the artifacts attached and generated notes;
4. **(gated)** publishes to PyPI via Trusted Publishing.

## Cutting a release

```bash
# bump the version in src/agentfence/__init__.py, commit via PR, then from main:
git tag v0.1.0
git push origin v0.1.0
```

## PyPI publishing — one-time setup (the spend/credential gate)

PyPI itself is free, but the first publish needs a credential that cannot be
self-provisioned. We use **Trusted Publishing** (OIDC) so no token is ever stored.

Until this is configured, releases still build and attach artifacts to the GitHub
Release — the PyPI job is skipped, not failed. To enable it:

1. Create the project on PyPI (or reserve the name), owner able to manage it.
2. On PyPI → the project → **Publishing** → add a **Trusted Publisher**:
   - Owner: `Lonkins`
   - Repository: `agentfence`
   - Workflow: `release.yml`
   - Environment: `pypi`
3. In the GitHub repo, set the variable `PYPI_TRUSTED_PUBLISHER` to `configured`
   (Settings → Secrets and variables → Actions → Variables), which un-gates the
   `pypi` job.

After that, every `v*` tag publishes automatically with no stored secret.

## Docs

The [`docs`](.github/workflows/docs.yml) workflow deploys the MkDocs site to
GitHub Pages on every push to `main` (Pages source: GitHub Actions).
