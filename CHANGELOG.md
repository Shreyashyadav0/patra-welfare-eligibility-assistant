# Changelog

All notable changes to this project. Format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versioning follows
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.1.0] - 2026-11-14

### Added
- Continuous integration: tests on Python 3.12 and 3.13, lint and format check,
  and a benchmark smoke test on every push and pull request.
- `ruff` for linting and formatting, with rules configured in `pyproject.toml`,
  and a `pre-commit` hook so the checks run before a commit rather than after.
- Structured logging (`patra.logging_conf`), a request-level log line in the API
  and a decision log in the pipeline, with the level controlled by `PATRA_LOG_LEVEL`.
- `CONTRIBUTING.md`, `SECURITY.md`, a pull-request template and a bug-report template.
- Docker `HEALTHCHECK` against `/health`.

### Fixed
- `engine.py`: loop variable shadowed the `dataclasses.field` import.
- `engine.py`: `zip()` calls are now explicit about strictness.
- Unused imports and unsorted import blocks across the package.
- Dependencies in `pyproject.toml` aligned with the pinned versions in `requirements.txt`.

## [1.0.0] - 2026-11-13

### Added
- Deterministic eligibility engine: ten operators, three-valued clause outcomes,
  interval-based conflict detection, mandatory-failure rule.
- Hybrid retrieval (BM25 + TF-IDF vector index, reciprocal rank fusion, lexical
  reranking) and scheme linking with English and Devanagari aliases.
- Rule-based profile extraction, including negation handling.
- Calibrated abstention gate: eight features, scheme-disjoint cross-fitting, a stated
  coverage floor, and threshold selection against an accuracy target.
- FastAPI + Jinja interface, CLI (`demo`, `eval`, `serve`), and 47 tests.
- Evaluation harness: thirteen metrics including both denominators, a 46-item
  bilingual benchmark, and published artefacts of the last run.
- Project report, synopsis, defence brief and submission checklist.
