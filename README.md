# RepoReveal

RepoReveal is a local discovery tool for finding promising GitHub repository names and, in later checkpoints, comparing those names with domain availability.

## Current milestone

Checkpoint 1 focuses only on GitHub repository discovery:

- search recently created repositories;
- filter by minimum stars and optional language;
- display useful repository metadata;
- open a selected repository in the browser;
- export results to CSV.

Domain availability checking is deliberately deferred to Checkpoint 2.

## Run locally

After the bootstrap script has completed:

```powershell
.\.venv\Scripts\Activate.ps1
python -m reporeveal.app
```

## Secrets

RepoReveal may optionally use a `GITHUB_TOKEN` environment variable in the future/current GitHub client. Never commit tokens, `.env` files, credentials, or other secrets.