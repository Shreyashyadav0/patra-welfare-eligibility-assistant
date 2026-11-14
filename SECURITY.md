# Security

## Scope

This is an advisory university project, not a government service. It stores no personal
data: no accounts, no database, nothing retained after a request. The threat model is
documented in Chapter 9 of the report.

## Reporting

If you find a vulnerability, please open an issue describing the impact without a public
proof-of-concept, or contact the maintainer directly through the GitHub profile.

## Design decisions that limit risk

- The verdict is computed outside any language model, so a document-borne instruction
  cannot change a decision.
- Every criterion must resolve to an exact clause span at ingestion, or the load fails.
- The answer composer may not introduce a number that the engine did not compute.
- Request payloads are validated: question length 3-500 characters, `lang` in `{en, hi}`.

## Known limitations, stated rather than hidden

- No authentication, no rate limiting and no TLS in the delivered build.
- Single process; the pipeline is not yet safe for concurrent writers.
- The corpus is illustrative seed data, not an authoritative copy of scheme guidelines.
