# AGENTS.md

## Project purpose

RepoRip discovers interesting GitHub repository names. A later checkpoint will compare candidate names with domain availability.

## Current scope

Checkpoint 1 is GitHub discovery only. Do not add domain lookup, scraping, databases, accounts, cloud hosting, payment systems, installers, or AI scoring unless explicitly requested.

## Architecture

- `src/reporip/app.py` - Tkinter desktop UI.
- `src/reporip/github_client.py` - GitHub REST search client and query construction.
- `src/reporip/models.py` - application data models.
- `tests/` - deterministic unit tests.

Keep network/API logic separate from GUI logic.

## Environment

- Target OS: Windows 11 for primary local use.
- Python: 3.11+.
- UI: Python standard-library Tkinter.
- Runtime dependencies: none beyond Python standard library for Checkpoint 1.
- Development uses a local `.venv`.

## Development commands

Run:

```powershell
.\.venv\Scripts\Activate.ps1
python -m reporip.app
```

Tests:

```powershell
python -m unittest discover -s tests -v
```

Syntax/import validation:

```powershell
python -m compileall src
```

## Workflow

- `main` should remain known-good.
- Meaningful development happens on a feature/fix branch.
- Inspect current source before replacing existing files.
- Make the smallest coherent change.
- Do not combine unrelated cleanup/refactoring.
- Local GUI and Windows behaviour must be tested by the user.
- Commit/push only at useful checkpoints.
- Never merge without explicit user approval.

## Security

- Never commit API keys, GitHub tokens, passwords, `.env` files, certificates, or personal data.
- Read `GITHUB_TOKEN` only from the process environment.
- Do not log secrets.
- Do not embed developer credentials.

## Dependencies

Avoid new dependencies unless they clearly improve the project. Inspect compatibility, packaging and licensing before adding any.

## Current non-goals

- Domain availability checking.
- Scraping Instant Domain Search.
- Persistent database.
- SaaS/cloud deployment.
- Authentication UI.
- Packaging/installer.
- Trademark checking.