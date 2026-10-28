# Contributing Guidelines

## Branching
- Branch format: `feature/<area>-<short-name>`
- Allowed `<area>` values: `profiling`, `dds`, `ingestion`, `dbt`, `mage`, `tests`, `dashboard`, `advanced`, `docs`
- Always `git pull` before starting new work.
- Never commit directly to `main`.

## Pull Requests
- Each PR requires at least **1 reviewer approval**.
- For dbt changes, the reviewer must run `dbt build` before approving.

## Commits
- Use short imperative commit messages.

## Data and Secrets Policy
- Never commit data files, `.duckdb`, `.pbix`, or tokens/credentials.

## Power BI Collaboration
- `.pbix` is shared on Google Drive and edited by one person at a time.
