# Implementation Plan

Generated on 2026-04-06
Branch: main
Source design: `office-hours-design.md`

## Goal

Ship version 1 of the WikiTree Match Workbench as a local-first web app that:

- imports a GEDCOM through a staged resumable pipeline
- stores durable match memory and review receipts
- authenticates the app user with Google
- connects to WikiTree for private-data reads through the backend
- lets the user anchor one known person, traverse outward, review matches, and queue
  later sync-review items

## Delivery Guardrails

- Every PR must touch fewer than 10 files.
- Every PR must ship with tests.
- Repo coverage target: at least 80% lines for backend and frontend packages.
- Critical user flows get Playwright coverage even if unit coverage is already high.
- One behavioral idea per PR. No mixed “while we’re here” work.
- Prefer modifying existing files over introducing new abstractions.
- If a PR needs 10+ files, split it before coding.

## Planned Stack

- Backend: Python
- Frontend: React + TypeScript
- Database: PostgreSQL as the only source of truth
- Local orchestration: Docker Compose
- Backend tests: `pytest`
- Frontend tests: `vitest`
- E2E tests: `playwright`
- CI: GitHub Actions

Datastore decision:

- use PostgreSQL only for version 1
- do not add ArangoDB or another graph database in the initial build
- if graph-specific read workloads become a real bottleneck later, add a derived graph
  projection from PostgreSQL instead of a second primary datastore

## Repo Shape

Keep it boring:

```text
apps/
  api/
    tests/
  ui/
    src/
    tests/
e2e/
migrations/
.github/workflows/
```

Use `apps/` as the monorepo home for runnable applications. In version 1 that means:

- `apps/api/`
- `apps/ui/`

Do not introduce extra packages, workers, or shared libraries in v1 unless a later PR
proves the duplication is real. Shared code should live inside one app until duplication
is real enough to justify extraction.

## Architecture Spine

```text
[ui SPA]
   |
   v
[api]
   |-- Google app session
   |-- WikiTree connection/session
   |-- import jobs
   |-- matching pipeline
   |-- review queue
   v
[postgres]
```

## PR Plan

### PR1: Repo Skeleton + Test Harness + CI

Purpose:
Create the smallest runnable project shell with coverage gates.

Files:
- `pyproject.toml`
- `apps/api/app.py`
- `apps/api/tests/test_health.py`
- `apps/ui/package.json`
- `apps/ui/src/App.tsx`
- `apps/ui/tests/App.test.tsx`
- `.github/workflows/ci.yml`
- `docker-compose.yml`
- `.gitignore`

Why this is reviewable:
- No business logic
- Proves toolchain boots
- Establishes the test contract early

Tests:
- backend health test
- frontend render test
- CI runs `pytest`, `vitest`, and coverage thresholds

Acceptance:
- `docker compose up` boots app and db
- CI passes
- backend and frontend coverage gates are both set to 80%

### PR2: Database Spine + Explicit State Machines

Purpose:
Introduce the canonical persistence model and job/review state enums before feature code.

Files:
- `migrations/001_initial_schema.sql`
- `apps/api/db.py`
- `apps/api/models.py`
- `apps/api/state_machines.py`
- `apps/api/tests/test_models.py`
- `apps/api/tests/test_import_job_states.py`
- `apps/api/tests/test_review_record_states.py`

Why this is reviewable:
- Pure data model PR
- No UI
- Easy to reason about invariants

Tests:
- allowed import job transitions
- allowed review record transitions
- persistence of checkpoints and decision history

Acceptance:
- import jobs and review receipts have explicit durable states
- one canonical model exists for people, relations, sources, external identities, and
  review snapshots
- schema includes the minimum version 1 tables:
  `app_users`, `app_sessions`, `wikitree_connections`, `import_jobs`,
  `import_job_stages`, `people`, `person_names`, `person_facts`, `relationships`,
  `sources`, `external_identities`, `match_reviews`, `evidence_packets`,
  and `sync_review_items`

### PR3: Backend Session Boundary

Purpose:
Implement backend-owned Google app auth and durable app sessions.

Files:
- `apps/api/auth_google.py`
- `apps/api/session_store.py`
- `apps/api/routes_auth.py`
- `apps/api/app.py`
- `apps/ui/src/routes/LoginPage.tsx`
- `apps/ui/src/lib/session.ts`
- `apps/api/tests/test_google_auth.py`
- `apps/ui/tests/routes/LoginPage.test.tsx`

Why this is reviewable:
- One concern only, app identity
- No WikiTree yet

Tests:
- successful sign-in creates backend session
- returning user restores session
- unauthorized request fails cleanly

Acceptance:
- SPA relies on backend session, not browser-stored identity tricks

### PR4: WikiTree Connection Boundary

Purpose:
Add WikiTree authentication and backend-owned private-data access.

Files:
- `apps/api/wikitree_client.py`
- `apps/api/wikitree_session.py`
- `apps/api/routes_wikitree.py`
- `apps/api/models.py`
- `apps/api/tests/test_wikitree_auth.py`
- `apps/api/tests/test_wikitree_private_access.py`
- `apps/ui/src/routes/WikiTreeSettingsPage.tsx`
- `apps/ui/tests/routes/WikiTreeSettingsPage.test.tsx`

Why this is reviewable:
- One external integration
- No import logic yet

Tests:
- WikiTree auth connect/disconnect
- private-data access only when connected
- expired WikiTree session shows reconnect path

Acceptance:
- backend owns WikiTree session material
- private data is provenance-tagged as WikiTree-authenticated

### PR5: Import Job API + Staged Pipeline Shell

Purpose:
Create resumable staged import jobs without full GEDCOM parsing yet.

Files:
- `apps/api/import_jobs.py`
- `apps/api/import_pipeline.py`
- `apps/api/routes_imports.py`
- `apps/api/models.py`
- `apps/api/tests/test_import_pipeline.py`
- `apps/api/tests/test_import_resume.py`
- `apps/ui/src/routes/ImportJobPage.tsx`
- `apps/ui/tests/routes/ImportJobPage.test.tsx`

Why this is reviewable:
- Focuses on job lifecycle only
- Uses fake stages first

Tests:
- stage transitions
- pause/resume
- failed stage becomes visible recoverable state

Acceptance:
- import jobs are checkpointed and resumable even before real GEDCOM parsing lands

### PR6: GEDCOM Parse + Normalize

Purpose:
Turn uploaded GEDCOM into normalized people, relations, and source provenance.

Files:
- `apps/api/gedcom_parser.py`
- `apps/api/gedcom_normalizer.py`
- `apps/api/import_pipeline.py`
- `apps/api/models.py`
- `apps/api/tests/test_gedcom_parser.py`
- `apps/api/tests/test_gedcom_normalizer.py`
- `apps/api/tests/fixtures/sample_clean.ged`
- `apps/api/tests/fixtures/sample_messy_redacted.ged`

Why this is reviewable:
- Pure import logic
- No matching decisions yet

Tests:
- clean synthetic fixture parsing
- messy redacted fixture parsing
- malformed GEDCOM failure path

Acceptance:
- import pipeline persists normalized canonical rows
- failure states are explicit and recoverable

### PR7: Anchor Flow + Matching Pipeline

Purpose:
Implement the first real “whoa” path, anchor one person and generate candidate matches.

Files:
- `apps/api/matching_pipeline.py`
- `apps/api/match_rules.py`
- `apps/api/routes_matches.py`
- `apps/api/models.py`
- `apps/api/tests/test_matching_pipeline.py`
- `apps/api/tests/test_match_rules.py`
- `apps/ui/src/routes/AnchorMatchPage.tsx`
- `apps/ui/tests/routes/AnchorMatchPage.test.tsx`

Why this is reviewable:
- First product logic PR
- Still limited to anchor + candidate generation

Tests:
- anchor selection
- likely / maybe / no-safe-match classification
- ambiguous relative goes to manual review

Acceptance:
- one anchored person can generate a reviewable candidate queue

### PR8: Review Receipts + Evidence Packets

Purpose:
Persist review snapshots, decisions, and evidence packets as stable receipts.

Files:
- `apps/api/review_records.py`
- `apps/api/evidence_packets.py`
- `apps/api/routes_reviews.py`
- `apps/api/models.py`
- `apps/api/tests/test_review_records.py`
- `apps/api/tests/test_evidence_packets.py`
- `apps/ui/src/routes/ReviewQueuePage.tsx`
- `apps/ui/tests/routes/ReviewQueuePage.test.tsx`

Why this is reviewable:
- No new traversal rules
- Just makes review trustworthy

Tests:
- accept/reject/defer decision persistence
- rejected candidates do not resurface endlessly
- evidence snapshot stays stable after later imports

Acceptance:
- review queue is durable and auditable

### PR9: Traversal Through Resolved Matches + Auto-Accept Rules

Purpose:
Make the engine continue outward through confident matches and auto-accept only when
surrounding confirmed relatives make the identity obvious.

Files:
- `apps/api/traversal.py`
- `apps/api/auto_accept.py`
- `apps/api/matching_pipeline.py`
- `apps/api/tests/test_traversal.py`
- `apps/api/tests/test_auto_accept.py`
- `apps/api/tests/test_conflict_fallback.py`
- `apps/ui/src/routes/ReviewQueuePage.tsx`

Why this is reviewable:
- One behavioral expansion on top of existing review flow

Tests:
- traversal does not stall on resolved matches
- derived auto-accepted match stores derivation chain
- conflict path falls back to manual review

Acceptance:
- engine spends attention on gaps and disagreements, not settled identity work

### PR10: Later Sync-Review Queue

Purpose:
Create the separate queue for already-matched profiles with useful GEDCOM-only facts.

Files:
- `apps/api/sync_review.py`
- `apps/api/routes_sync_review.py`
- `apps/api/models.py`
- `apps/api/tests/test_sync_review.py`
- `apps/api/tests/test_additive_vs_conflicting.py`
- `apps/ui/src/routes/SyncReviewPage.tsx`
- `apps/ui/tests/routes/SyncReviewPage.test.tsx`

Why this is reviewable:
- Cleanly separate from import and matching
- No write-back yet

Tests:
- matched profile with extra GEDCOM facts enters queue
- additive vs conflicting distinction
- queue item includes evidence provenance

Acceptance:
- later sync-review queue exists and stays separate from import

### PR11: End-to-End Hardening

Purpose:
Add Playwright coverage for the critical user flows and Compose smoke checks.

Files:
- `e2e/auth.spec.ts`
- `e2e/import-resume.spec.ts`
- `e2e/anchor-review.spec.ts`
- `e2e/sync-review.spec.ts`
- `.github/workflows/ci.yml`
- `docker-compose.yml`

Why this is reviewable:
- No new product behavior
- Pure quality hardening

Tests:
- Google login -> backend session
- WikiTree connect -> private data visible
- start/pause/resume import
- anchor -> candidate review -> traversal continuation
- later sync-review queue appears

Acceptance:
- critical browser flows are proven end to end

## Coverage Plan

Coverage target:

- backend: `pytest --cov=apps/api --cov-fail-under=80`
- frontend: `vitest --coverage --threshold.lines=80` from `apps/ui`
- E2E: Playwright for critical user journeys, not for every edge case

Quality bar:

- New backend branch logic requires `pytest`
- New frontend state logic requires `vitest`
- Auth, resumable import, anchor review, and sync-review flows require `playwright`

## Fixture Strategy

Use layered fixtures:

- tiny synthetic GEDCOM fixtures for unit tests
- one redacted messy GEDCOM fixture for integration truth
- mock WikiTree responses for most tests
- one narrow end-to-end “realistic response shape” fixture for browser flows

Default locations:

- backend tests: `apps/api/tests/`
- backend fixtures: `apps/api/tests/fixtures/`
- frontend tests: `apps/ui/tests/`
- e2e tests: `e2e/`

## Failure Modes To Design For

- malformed GEDCOM upload
- import stage crashes after partial persistence
- resume from stale checkpoint
- Google session missing or expired
- WikiTree private-data session expires mid-run
- fuzzy match misclassifies ambiguous relatives
- auto-accept tries to cross a conflicting field
- rejected candidate reappears after re-import
- sync-review item loses provenance

Every one of these should have either:

- a unit/integration test
- an E2E test
- or both

## Review Rules Per PR

Each PR description should include:

- purpose in one sentence
- exact files touched
- user-visible behavior change
- tests added
- explicit non-goals

Each PR should be easy to review in under 15 minutes.

If a PR cannot be explained in 5 bullets, it is too big.

## Parallel Worktree Strategy

Launch in this order:

```text
Lane A: PR1 -> PR3 -> PR4
Lane B: PR2 -> PR5 -> PR6
Lane C: PR7 -> PR8 -> PR9 -> PR10
Lane D: PR11
```

Execution notes:

- `Lane A` and `Lane B` can start in parallel after PR1/PR2 scaffolding is stable.
- `Lane C` should wait for auth, import, and canonical models to settle.
- `Lane D` can begin after PR7 once real flows exist, then finish after PR10.

Conflict flags:

- PR5, PR6, PR7, PR8, PR10 all touch `apps/api/models.py`, so sequence them.
- PR7, PR8, PR9 all touch the review UI route area under `apps/ui/src/routes/`, so
  keep them in one lane.
- CI updates should be folded into the same PR only when they directly support the new
  behavior under test.

## Suggested First Build

Start with PR1 immediately.

That gives you:

- repo shape
- test harness
- coverage gates
- CI contract

Without that, every later PR becomes harder to keep under control.
