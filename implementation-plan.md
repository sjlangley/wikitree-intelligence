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

## Current Implementation Status

The repo has already shipped the Google auth/session boundary ahead of the rest of the
planned roadmap.

Implemented today:

- FastAPI app wiring with `SessionMiddleware`
- `POST /auth/login` to verify the Google token and create the app session
- `POST /auth/logout` to clear the app session
- `GET /user/current` to restore the signed-in user from session state
- React `AuthProvider` that loads auth state on startup and exposes login/logout actions
- UI states for loading, unauthenticated, and authenticated sessions
- backend and frontend tests covering the auth/session flow

Planning note:

- the current implementation landed out of original PR order
- the auth/session boundary is effectively complete even though the database spine and
  later roadmap items are still pending
- future PRs should build on the existing auth/session code rather than re-introducing a
  different login boundary

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
- Worker: Python background process pulling import work from PostgreSQL
- Ingestion: Separate Python app for WikiTree database dump loading (weekly)
- Frontend: React + TypeScript
- Database: PostgreSQL as the only source of truth
- Raw GEDCOM storage: shared Docker volume in local development, object storage later
- WikiTree dump cache: Local PostgreSQL tables refreshed weekly
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

- `apps/api/` — HTTP API for UI and session management
- `apps/ui/` — React frontend
- `apps/ingestion/` — Separate WikiTree dump ingestion service (runs weekly)

Use a separate worker process in v1, but keep the implementation inside `apps/api`
until duplication is real enough to justify extraction.

The ingestion app is separate because:
- Runs on a different schedule (weekly, not continuous)
- Requires different permissions (SFTP access to WikiTree dumps)
- Has different failure modes (network issues, dump format changes)
- Should not block or interfere with user-facing API or worker

## Architecture Spine

```text
[ui SPA]
   |
   v
[api]
   |-- Google app session
   |-- WikiTree connection/session
   |-- review queue
   |-- enqueue import/search work
   |
   +------> [worker]
              |-- claim queued jobs
              |-- run staged import/search batches
              |-- search WikiTree dump cache (fast local)
              |-- supplement with WikiTree API (private data only)
              |-- write checkpoints and outcomes
   v
[postgres]  <----  [ingestion app]
                      |-- downloads weekly WikiTree dumps (Sunday nights)
                      |-- parses TSV files
                      |-- upserts wikitree_dump_* tables
                      |-- tracks dump versions
```

Execution model:

- the API accepts uploads and creates durable job rows in PostgreSQL
- the API stores the raw GEDCOM in a shared mounted volume and records its path/metadata
- the worker pulls queued work from PostgreSQL rather than receiving pushes from an
  external queue
- the worker reads the GEDCOM from the shared mounted path
- the worker processes GEDCOM imports and WikiTree search in small batches so progress,
  retry, and pause/resume remain cheap
- the UI reads job status, counts, and queue summaries from the API

## PR Plan

### PR1: Repo Skeleton + Test Harness + CI ✅ COMPLETE

**Status:** Merged in PR #10 on 2026-04-08

**Implemented:**
- Docker infrastructure with multi-stage builds
- GitHub Actions workflows for API and UI
- docker-compose.yml with postgres, api, and ui services
- Health check endpoints
- Basic test infrastructure
- Coverage gates established

**Note:** Worker service will be added later when background job processing is implemented.

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
- `docker compose up` boots ui, api, worker, and db
- api and worker share a mounted data volume for uploaded GEDCOM files
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
  `app_users`, `wikitree_connections`, `import_jobs`,
  `import_job_stages`, `people`, `person_names`, `person_facts`, `relationships`,
  `sources`, `external_identities`, `wikitree_search_runs`,
  `wikitree_search_candidates`, `match_reviews`, `evidence_packets`, and
  `sync_review_items`
- sessions managed via signed cookies (no database table needed)

### PR3: Backend Session Boundary ✅ COMPLETE

**Status:** Implemented in current repo

**Implemented:**
- Google OAuth authentication flow
- Backend-owned session management with signed cookies
- Auth routes: `/auth/google/url`, `/auth/google/callback`, `/auth/logout`
- User routes: `/auth/me` for current user retrieval
- React `AuthProvider` with session restore on app load
- Frontend login/logout flow with UI states
- Comprehensive test coverage (API: 93%+, UI tests)

Purpose:
Implement backend-owned Google app auth and durable app sessions.

Status:
Implemented in simplified form in the current repo.

Files:
- `apps/api/src/api/routes/auth.py`
- `apps/api/src/api/routes/user.py`
- `apps/api/src/api/security/google_bearer_token.py`
- `apps/api/src/api/security/session_auth.py`
- `apps/api/src/api/app.py`
- `apps/ui/src/lib/auth.tsx`
- `apps/ui/src/components/GoogleSignInButton.tsx`
- `apps/ui/src/components/LoggedInScreen.tsx`
- `apps/api/tests/routers/test_auth.py`
- `apps/api/tests/routers/test_user.py`
- `apps/api/tests/test_google_bearer_token.py`
- `apps/ui/tests/auth.test.tsx`
- `apps/ui/tests/GoogleSignInButton.test.tsx`
- `apps/ui/tests/LoggedInScreen.test.tsx`

Why this is reviewable:
- One concern only, app identity
- No WikiTree yet

Tests:
- successful sign-in creates backend session
- returning user restores session
- unauthorized request fails cleanly

Acceptance:
- SPA relies on backend session, not browser-stored identity tricks
- complete in current repo, using signed session cookies rather than a database-backed
  session store

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

### PR5: WikiTree Dump Ingestion App

Purpose:
Create a separate ingestion application to load WikiTree weekly database dumps into
PostgreSQL for fast local search.

Files:
- `apps/ingestion/main.py`
- `apps/ingestion/dump_loader.py`
- `apps/ingestion/sftp_client.py`
- `apps/ingestion/parsers.py`
- `apps/ingestion/tests/test_dump_loader.py`
- `migrations/005_wikitree_dump_tables.sql`

Why this is reviewable:
- Single responsibility: load dump data
- No UI coupling
- Clear schema additions

Tests:
- parse sample TSV dump files
- upsert logic handles updates correctly
- dump version tracking
- handles missing/corrupted files gracefully

Acceptance:
- ingestion app can download and parse WikiTree dumps
- dump data loaded into `wikitree_dump_people`, `wikitree_dump_marriages` tables
- `wikitree_dump_versions` tracks which dump is current
- runs as separate Docker service on Sunday nights
- API/worker can query dump cache for fast local search

Schema additions:

```sql
wikitree_dump_versions
  id
  dump_date         -- Date the dump was created by WikiTree (YYYY-MM-DD)
  downloaded_at     -- When we downloaded it
  loaded_at         -- When we finished loading it
  record_count      -- Number of people loaded
  status            -- downloading, loading, ready, failed
  is_current        -- Only one dump should be current=true
  error_message
  file_size_bytes
  file_sha256

wikitree_dump_people
  user_id           -- WikiTree User ID (integer)
  wikitree_id       -- WikiTree-123 format
  first_name
  last_name_birth
  last_name_current
  birth_date        -- YYYY-MM-DD or decade for private
  death_date
  birth_location
  death_location
  father_id         -- WikiTree User ID
  mother_id         -- WikiTree User ID
  gender
  privacy_level     -- 10-60 (see WikiTree privacy docs)
  photo_url
  is_connected      -- Part of main tree
  dump_version_id   -- FK to wikitree_dump_versions
  INDEX (first_name, last_name_birth)
  INDEX (wikitree_id)
  INDEX (birth_date, birth_location)
  INDEX (father_id, mother_id)

wikitree_dump_marriages
  user_id1          -- WikiTree User ID
  user_id2          -- WikiTree User ID
  marriage_date
  marriage_location
  dump_version_id   -- FK to wikitree_dump_versions
  INDEX (user_id1, user_id2)
```

Implementation notes:
- Use SFTP to download from apps.wikitree.com/dumps/
- Parse tab-separated files with Python csv module
- Upsert strategy: truncate old dump, insert new (simple)
- Or: keep last 2 dumps for rollback capability
- Track which dump is "current" for search queries

### PR6: Import Job API + Staged Pipeline Shell

Purpose:
Create resumable staged import jobs and a worker-owned execution loop without full
GEDCOM parsing yet.

Files:
- `apps/api/src/api/import_jobs.py`
- `apps/api/src/api/import_pipeline.py`
- `apps/api/src/api/worker.py`
- `apps/api/src/api/routes_imports.py`
- `apps/api/src/api/models.py`
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
- worker claims one queued job safely
- failed stage becomes visible recoverable state

Acceptance:
- import jobs are checkpointed and resumable even before real GEDCOM parsing lands
- API enqueues work and the worker advances the job without blocking user requests
- raw GEDCOM uploads are persisted in shared volume storage and referenced from the job
  record

Implementation sketch:

```python
async def run_worker() -> None:
    while True:
        job = claim_next_job(worker_id=WORKER_ID)
        if job is None:
            await asyncio.sleep(POLL_SECONDS)
            continue

        while True:
            heartbeat_lease(job.id, worker_id=WORKER_ID)
            result = run_stage_batch(job.id, worker_id=WORKER_ID)

            if result.state in {"completed", "failed"}:
                break
```

The first cut should keep this boring:

- `claim_next_job(...)` uses PostgreSQL leasing so only one worker owns a job at a time
- `run_stage_batch(...)` handles one bounded chunk of work and commits a checkpoint
- the API never performs long import/search work inline; it only enqueues and reports
  status

### PR7: GEDCOM Parse + Normalize

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
- worker can persist partial batch progress during large imports
- failure states are explicit and recoverable

### PR8: Anchor Flow + Matching Pipeline

Purpose:
Implement the first real “whoa” path, anchor one person and generate candidate matches.

Files:
- `apps/api/matching_pipeline.py`
- `apps/api/match_rules.py`
- `apps/api/wikitree_search_cache.py`
- `apps/api/routes_matches.py`
- `apps/api/models.py`
- `apps/api/tests/test_matching_pipeline.py`
- `apps/api/tests/test_match_rules.py`
- `apps/api/tests/test_wikitree_search_cache.py`
- `apps/ui/src/routes/AnchorMatchPage.tsx`
- `apps/ui/tests/routes/AnchorMatchPage.test.tsx`

Why this is reviewable:
- First product logic PR
- Still limited to anchor + candidate generation

Tests:
- anchor selection
- likely / maybe / no-safe-match classification
- top candidate summaries are cached per searched person
- ambiguous relative goes to manual review

Acceptance:
- one anchored person can generate a reviewable candidate queue
- search results are cached without creating fake canonical WikiTree people for
  unconfirmed candidates
- a searched person can end the run as `needs_review` or `no_safe_match`
- matching/search work can be resumed by the worker from the last durable checkpoint

### PR9: Review Receipts + Evidence Packets

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
- UI clearly separates `needs review`, `missing from WikiTree`, and `resolved`
  outcomes

### PR10: Traversal Through Resolved Matches + Auto-Accept Rules

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

### PR11: Later Sync-Review Queue

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
- later sync-review is distinct from the `missing from WikiTree` queue and from
  unresolved candidate review

### PR12: End-to-End Hardening

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
- no-safe-match person appears in the missing queue with manual handoff details
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
- mock both candidate-hit and no-safe-match WikiTree search shapes
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
