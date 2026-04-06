# WikiTree Intelligence

WikiTree Intelligence is a local-first genealogy workbench for reconciling GEDCOM data
with WikiTree.

The core job is not bulk import. The core job is:

- finding likely existing WikiTree matches before creating duplicates
- preserving durable match memory between runs
- resuming large imports safely
- surfacing missing matches and data discrepancies
- preparing later sync-review items for already-matched profiles

## Status

This repo is in planning mode.

Current source-of-truth docs:

- [`office-hours-design.md`](./office-hours-design.md) — approved product/design doc
- [`implementation-plan.md`](./implementation-plan.md) — PR-by-PR build plan
- [`eng-review-test-plan.md`](./eng-review-test-plan.md) — test strategy and critical
  flows
- [`TODOS.md`](./TODOS.md) — deferred follow-up work

## Planned Stack

- `apps/api/` — Python backend
- `apps/web/` — React + TypeScript frontend
- `apps/api/tests/` — backend tests
- `apps/web/tests/` — frontend tests
- `e2e/` — Playwright end-to-end tests
- `migrations/` — database migrations
- `docker-compose.yml` — local orchestration

## Version 1 Goals

- Google-authenticated app session
- WikiTree-authenticated private-data reads through the backend
- staged, resumable GEDCOM imports
- one canonical person/relationship model
- snapshot-backed review receipts and evidence packets
- outward traversal through resolved matches
- later sync-review queue for GEDCOM facts not yet in WikiTree

## Engineering Rules

- every PR must touch fewer than 10 files
- every PR must be easy to review
- repo coverage target is at least 80%
- critical flows get Playwright coverage

## Next Step

Start with `PR1` from [`implementation-plan.md`](./implementation-plan.md).
