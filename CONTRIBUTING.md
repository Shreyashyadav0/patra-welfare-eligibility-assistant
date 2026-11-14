# Contributing

This is a university project, but it is laid out so that someone else could pick it up.
That means the same rules a team would use.

## Setup

```bash
python3 -m pip install -e ".[dev]"
pre-commit install          # optional but recommended
make test
```

## Before you push

```bash
ruff check src tests        # lint
ruff format src tests       # format
make test                   # 47 tests
make eval                   # benchmark still runs
```

CI runs the same four checks on Python 3.12 and 3.13. A pull request that fails them
will not be merged.

## Conventions

- **Commits** follow [Conventional Commits](https://www.conventionalcommits.org/):
  `feat:`, `fix:`, `docs:`, `test:`, `chore:`. One concern per commit.
- **Branches** are `feat/<short-name>`, `fix/<short-name>`, `docs/<short-name>`.
- **Tests** come with the change. A bug fix without a regression test is not finished.
- **Data** belongs in `data/`, never in `src/`. A criterion's `clause_text` must be an
  exact substring of its document; ingestion will refuse it otherwise, on purpose.
- **No personal data or credentials** in code, data or commit metadata. Use
  `PATRA_LOG_LEVEL` and environment variables for anything environment-specific.

## Where things live

| I want to change… | Edit |
|---|---|
| how a verdict is computed | `src/patra/engine.py` |
| how evidence is retrieved | `src/patra/index.py`, `src/patra/retrieve.py` |
| when the system abstains | `src/patra/gate.py` |
| what a scheme requires | `data/criteria/<scheme>.json` + the document in `data/corpus/` |
| what is measured | `src/patra/evaluate.py` |
| the HTTP surface | `src/patra/api.py` |
| any tunable | `src/patra/settings.py` |
