# RepoRip

RepoRip is a local discovery tool for finding newly emerging GitHub projects
that may represent interesting naming, domain, and business opportunities.

## MVP workflow

RepoRip can:

- search recently created GitHub repositories;
- filter by stars, language, category, and candidate-pool size;
- score candidates for name quality, brandability, momentum, and independence;
- run live domain-availability checks across supported TLDs;
- rank final opportunities using candidate quality plus `.com` availability;
- inspect exact-name GitHub repository and account collisions;
- browse matching GitHub repositories;
- analyze a selected repository's business potential using README and GitHub evidence;
- separate observed evidence, inference, and commercial hypotheses;
- export the visible final opportunities to CSV.

## Run locally

After the project environment has been created:

```powershell
.\.venv\Scripts\Activate.ps1
.\run-reporip.cmd
```

You can also run the module directly:

```powershell
python -m reporip.app
```

## GitHub authentication

RepoRip can optionally use a `GITHUB_TOKEN` environment variable for GitHub
API requests. Never commit tokens, `.env` files, credentials, or other secrets.

## Project status

RepoRip v0.1.0 is the first working MVP. It is under active development.
