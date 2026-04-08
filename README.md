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

This repo is in active development.

### Completed

✅ **Google Authentication And App Session Boundary**
- Frontend: React `AuthProvider` restores auth state on app load
- Backend: FastAPI login/logout/current-user endpoints are live
- Session cookies: Starlette `SessionMiddleware` persists app session state
- User flow: Google sign-in, returning-session restore, and logout all work
- Coverage: UI 20 tests, API 16 tests with 93.66% backend coverage

### In Progress

Planning and architecture documentation:

- [`office-hours-design.md`](./office-hours-design.md) — approved product/design doc
- [`implementation-plan.md`](./implementation-plan.md) — PR-by-PR build plan
- [`eng-review-test-plan.md`](./eng-review-test-plan.md) — test strategy and critical
  flows
- [`TODOS.md`](./TODOS.md) — deferred follow-up work

## Planned Stack

- `apps/api/` — Python backend
- `apps/ingestion/` — WikiTree dump loading service (runs weekly)
- planned background worker component for staged import/search jobs
- `apps/ui/` — React + TypeScript frontend
- `apps/api/tests/` — backend tests
- `apps/ui/tests/` — frontend tests
- `e2e/` — Playwright end-to-end tests
- `migrations/` — database migrations
- shared Docker volume — raw uploaded GEDCOM storage in local development
- PostgreSQL — WikiTree dump cache (refreshed weekly) + app data
- `docker-compose.yml` — local orchestration

## Version 1 Goals

- Google-authenticated app session
- WikiTree-authenticated private-data reads through the backend
- WikiTree weekly dump cache for fast local search (millions of profiles)
- hybrid search: local dump first, API supplement when needed
- staged, resumable GEDCOM imports
- background worker execution for large import/search jobs
- one canonical person/relationship model
- snapshot-backed review receipts and evidence packets
- outward traversal through resolved matches
- later sync-review queue for GEDCOM facts not yet in WikiTree

## Engineering Rules

- every PR must touch fewer than 10 files
- every PR must be easy to review
- repo coverage target is at least 80%
- critical flows get Playwright coverage

## Getting Started

### Prerequisites

- Python 3.12+
- Node.js 18+
- Google OAuth credentials (get from [Google Cloud Console](https://console.cloud.google.com/apis/credentials))

### Backend Setup

```bash
cd apps/api

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"

# Configure environment (copy .env.example to .env and fill in values)
cp .env.example .env

# Run development server
uvicorn api.app:app --reload
```

Backend runs at `http://localhost:8000`  
API docs at `http://localhost:8000/docs`

### Frontend Setup

```bash
cd apps/ui

# Install dependencies
npm install

# Configure environment (copy .env.example to .env and fill in values)
cp .env.example .env

# Run development server
npm run dev
```

Frontend runs at `http://localhost:5173`

### Running Tests

**Backend:**
```bash
cd apps/api
source .venv/bin/activate
pytest -v
```

**Frontend:**
```bash
cd apps/ui
npm run test
npm run test:ci  # with coverage
```

## Next Step

Continue with the next unfinished boundary from
[`implementation-plan.md`](./implementation-plan.md): WikiTree connection, import job
storage/worker execution, and the canonical data model.
