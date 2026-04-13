# PR6: Import Job API + Staged Pipeline Shell

Implementation plan for resumable import job infrastructure

**Status:** Planning (PR5 deferred until WikiTree dump access available)

## Objective

Build the job execution infrastructure for resumable, staged GEDCOM imports without implementing full parsing yet. This establishes the worker pattern, job lifecycle, and checkpointing system that all future import/search work will use.

## Success Criteria

- Import jobs can be created via API with uploaded GEDCOM file
- Jobs progress through stages with durable checkpoints
- Worker process claims and executes jobs without blocking API requests
- Jobs can pause, resume, and fail gracefully
- UI shows real-time job status and progress
- All work happens in small batches with explicit state transitions

## Key Design Decisions

### Worker Architecture

**Pattern:** PostgreSQL-backed job queue with lease-based claiming

- Worker polls database for `pending` jobs
- Claims job with worker_id + heartbeat timestamp
- Processes work in small batches (50-100 records at a time)
- Commits checkpoint after each batch
- Releases job on completion/failure or heartbeat expiry

**No external queue:** RabbitMQ, Redis, or SQS add deployment complexity. PostgreSQL can handle job claiming with row-level locking for version 1 scale.

### File Storage

**Location:** Shared Docker volume at `/data/gedcom` (local dev), object storage later

**Structure:**
```
/data/gedcom/
  {app_user_id}/
    {job_id}/
      original.ged          # Uploaded file, never modified
      metadata.json         # File info: size, filename, upload timestamp
```

**Database reference:** `import_jobs.gedcom_path` stores relative path

### Job Stages

Version 1 stages (even without full implementation):

1. **validate** - Quick file checks (GEDCOM header, size limits, encoding)
2. **parse** - Extract people/relations (stub for now)
3. **normalize** - Clean names/dates/places (stub for now)
4. **search** - Find WikiTree candidates (stub for now)
5. **match** - Score and rank candidates (stub for now)
6. **review** - Populate review queue (stub for now)

Each stage:
- Has its own `import_job_stages` row with status (pending/running/completed/failed)
- Tracks progress: `records_total`, `records_processed`, `last_checkpoint`
- Can fail independently without breaking other stages
- Stores stage-specific metadata in `stage_data` JSONB column

### Leasing Strategy

**Heartbeat-based with timeout:**

```python
claim_next_job(worker_id: str) -> ImportJob | None:
    # PostgreSQL row-level lock prevents double-claiming
    SELECT * FROM import_jobs
    WHERE status = 'pending'
      AND (worker_id IS NULL OR heartbeat_at < NOW() - INTERVAL '10 minutes')
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED

    UPDATE import_jobs
    SET worker_id = %worker_id,
        heartbeat_at = NOW(),
        status = 'running'
    WHERE id = %job_id
```

**Heartbeat refresh:** Every 60 seconds while processing

**Stale job recovery:** If heartbeat hasn't updated in 10 minutes, job is reclaimed by another worker

### Performance Optimizations

**Database Query Optimization:**
- Use SQLAlchemy `joinedload()` for job+stages queries to eliminate N+1 (single query with JOIN instead of 1+6 queries)
- Add composite index `CREATE INDEX idx_import_jobs_status_created ON import_jobs(status, created_at)` for efficient job claiming
- Pydantic validation `Field(le=100)` on pagination limit to prevent unbounded queries

**File I/O Optimization:**
- Single-pass GEDCOM validation (check header + count records in one loop instead of reading twice)
- FastAPI Form `max_size` validation to reject oversized uploads during streaming (prevents OOM)

**Write Optimization:**
- Heartbeat interval increased to 60s (halves write volume while maintaining sub-2-minute failure detection)
- Conditional JSONB updates (only update `stage_data` when checkpoint data actually changes)

**UI Performance:**
- Exponential backoff polling: starts at 2s, increases to 5s → 10s when no changes detected, resets to 2s on update
- Reduces API load from 150 req/min to ~30 req/min for typical job lifecycle

**Error Handling:**
- FileNotFoundError handler in stage_runners (fail job gracefully if GEDCOM file deleted mid-processing)

## Files to Create/Modify (10 files)

### Backend API (4 files)

1. **`apps/api/src/api/routes/import_jobs.py`** (NEW)
   - `POST /import-jobs` - Create job from uploaded GEDCOM
   - `GET /import-jobs` - List user's jobs (paginated)
   - `GET /import-jobs/{job_id}` - Get job status with stage details
   - `POST /import-jobs/{job_id}/pause` - Pause running job
   - `POST /import-jobs/{job_id}/resume` - Resume paused job
   - `DELETE /import-jobs/{job_id}` - Cancel and delete job

2. **`apps/api/src/api/services/import_pipeline.py`** (NEW)
   - `create_import_job(user_id, file, filename)` - Persist GEDCOM, create job + stages
   - `claim_next_job(worker_id)` - Lease next pending job
   - `heartbeat_job(job_id, worker_id)` - Refresh lease
   - `get_current_stage(job_id)` - Get active stage for job
   - `update_stage_progress(job_id, stage_name, records_processed, checkpoint_data)` - Update stage state
   - `transition_stage(job_id, stage_name, status)` - Move stage to next state
   - `fail_job(job_id, error_message)` - Mark job as failed
   - `complete_job(job_id)` - Mark all stages complete

3. **`apps/api/src/api/app.py`** (MODIFY)
   - Register import_jobs router
   - Add startup check for `/data/gedcom` directory existence

4. **`apps/api/src/api/database.py`** (MODIFY)
   - Add file storage helper: `get_gedcom_storage_path(user_id, job_id)`

### Worker Process (3 files)

5. **`apps/worker/main.py`** (NEW)
   - FastAPI application for worker process (run via `uvicorn worker.main:app --port 8081`)
   - `GET /health/live` - Liveness probe (is process running?)
   - `GET /health/ready` - Readiness probe (can claim jobs? DB connection healthy?)
   - Background task runs job processing loop (polls every 5 seconds)
   - Claims jobs via API service, runs batches using local stage runners
   - Graceful shutdown on SIGTERM/SIGINT
   - Logging for observability
   - Imports from `api.services.import_pipeline` and `api.database` for state management

6. **`apps/worker/stage_runners.py`** (NEW)
   - `validate_stage(job_id, batch_size)` - Check GEDCOM format/encoding
   - `parse_stage(job_id, batch_size)` - Stub: log progress, sleep 0.1s per "record"
   - `normalize_stage(job_id, batch_size)` - Stub: log progress
   - `search_stage(job_id, batch_size)` - Stub: log progress
   - `match_stage(job_id, batch_size)` - Stub: log progress
   - `review_stage(job_id, batch_size)` - Stub: log progress
   - Each returns: `{records_processed: int, stage_complete: bool, checkpoint_data: dict}`

7. **`apps/worker/__init__.py`** (NEW)
   - Makes worker a proper Python package

### Frontend (2 files)

8. **`apps/ui/src/components/ImportJobPage.tsx`** (NEW)
   - Job list view with status badges
   - Upload GEDCOM form
   - Job detail view with stage progress bars
   - Pause/resume/cancel actions
   - Auto-refresh every 2 seconds while job is running

9. **`apps/ui/src/components/ImportJobCard.tsx`** (NEW)
   - Single job summary card
   - Progress visualization (overall + per-stage)
   - Status badge (pending/running/paused/completed/failed)
   - Action buttons (pause/resume/cancel/view)

### Tests (6 files)

10. **`apps/api/tests/test_import_jobs_routes.py`** (NEW)
    - Test all HTTP endpoints (POST/GET/DELETE /import-jobs, pause/resume)
    - Request validation and auth checks
    - File upload validation (size, extension, sanitization)
    - HTTP status codes and error responses

11. **`apps/api/tests/test_import_pipeline.py`** (NEW)
    - Test job creation with file upload
    - Test lease claiming (no double-claim race)
    - Test heartbeat refresh
    - Test stale job reclaim after timeout
    - Test stage transitions
    - Test batch processing with checkpoints
    - Test pause/resume
    - Test job failure and error capture
    - Test auth/ownership filtering

12. **`apps/worker/tests/test_worker_main.py`** (NEW)
    - Test GET /health/live endpoint (always returns 200)
    - Test GET /health/ready endpoint (200 when DB healthy, 503 when DB down)
    - Test worker main loop (poll, claim, process)
    - Test signal handling (SIGTERM/SIGINT graceful shutdown)
    - Test process_job() end-to-end execution
    - Test pause check per batch
    - Test error recovery (continue after exception)

13. **`apps/worker/tests/test_stage_runners.py`** (NEW)
    - Test validate_stage() with valid/invalid GEDCOM
    - Test error cases (missing header, file not found, encoding errors)
    - Test all stub stages (parse/normalize/search/match/review)
    - Verify batch processing and checkpoint data

14. **`apps/ui/tests/ImportJobPage.test.tsx`** (NEW)
    - Test job list rendering and empty state
    - Test upload form submission
    - Test auto-refresh behavior
    - Test pause/resume/delete interactions

15. **`apps/ui/tests/ImportJobCard.test.tsx`** (NEW)
    - Test status badge rendering for all states
    - Test progress bar visualization
    - Test action button states
    - Test timestamp formatting

## API Endpoints

### POST /api/import-jobs

**Request:**
```
Content-Type: multipart/form-data

file: <gedcom binary>
```

**Response:**
```json
{
  "id": "uuid",
  "user_id": "google-subject-id",
  "status": "pending",
  "gedcom_filename": "family.ged",
  "gedcom_size_bytes": 524288,
  "stages": [
    {"name": "validate", "status": "pending", "records_total": 0, "records_processed": 0},
    {"name": "parse", "status": "pending", "records_total": 0, "records_processed": 0},
    {"name": "normalize", "status": "pending", "records_total": 0, "records_processed": 0},
    {"name": "search", "status": "pending", "records_total": 0, "records_processed": 0},
    {"name": "match", "status": "pending", "records_total": 0, "records_processed": 0},
    {"name": "review", "status": "pending", "records_total": 0, "records_processed": 0}
  ],
  "created_at": "2026-04-10T12:00:00Z"
}
```

### GET /api/import-jobs

**Query params:**
- `limit` (default: 20, max: 100)
- `offset` (default: 0)
- `status` (pending/running/paused/completed/failed)

**Response:**
```json
{
  "jobs": [...],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

### GET /api/import-jobs/{job_id}

**Response:**
```json
{
  "id": "uuid",
  "user_id": "google-subject-id",
  "status": "running",
  "gedcom_filename": "family.ged",
  "gedcom_size_bytes": 524288,
  "worker_id": "worker-pod-123",
  "heartbeat_at": "2026-04-10T12:05:30Z",
  "stages": [
    {
      "name": "validate",
      "status": "completed",
      "records_total": 1250,
      "records_processed": 1250,
      "started_at": "2026-04-10T12:00:15Z",
      "completed_at": "2026-04-10T12:00:18Z"
    },
    {
      "name": "parse",
      "status": "running",
      "records_total": 1250,
      "records_processed": 873,
      "started_at": "2026-04-10T12:00:20Z",
      "last_checkpoint": "2026-04-10T12:05:28Z",
      "stage_data": {"batch_number": 18}
    },
    ...
  ],
  "created_at": "2026-04-10T12:00:00Z",
  "updated_at": "2026-04-10T12:05:30Z"
}
```

### POST /api/import-jobs/{job_id}/pause

**Response:**
```json
{
  "id": "uuid",
  "status": "paused",
  "message": "Job paused after current batch completes"
}
```

### POST /api/import-jobs/{job_id}/resume

**Response:**
```json
{
  "id": "uuid",
  "status": "pending",
  "message": "Job queued for resumption"
}
```

### DELETE /api/import-jobs/{job_id}

**Response:**
```json
{
  "id": "uuid",
  "status": "cancelled",
  "message": "Job cancelled and files deleted"
}
```

## Database Schema Updates

Already exist in PR2 schema. No new tables needed.

**Usage clarifications:**

`import_jobs` table:
- `worker_id` - Set when job is claimed, NULL when pending/paused
- `heartbeat_at` - Updated every 60s by worker
- `gedcom_path` - Relative path: `{user_id}/{job_id}/original.ged`
- `gedcom_filename` - Original upload filename
- `gedcom_size_bytes` - File size for progress estimation

`import_job_stages` table:
- `records_total` - Set after validate stage counts GEDCOM records
- `records_processed` - Incremented after each batch
- `last_checkpoint` - Timestamp of last batch commit
- `stage_data` - JSONB for stage-specific state (batch number, resume cursor, etc.)
- `error_message` - Set when stage fails
- `started_at`, `completed_at` - Stage lifecycle timestamps

## Worker Implementation

### FastAPI Application with Background Job Loop

```python
# apps/worker/main.py
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import asyncio
import os
import socket
import sys
from pathlib import Path
from sqlalchemy import text

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.import_pipeline import (
    claim_next_job,
    heartbeat_job,
    get_current_stage,
    update_stage_progress,
    transition_stage,
    fail_job,
    complete_job,
)
from api.database import init_db, get_db
from worker.stage_runners import STAGE_RUNNERS
import logging

logger = logging.getLogger(__name__)

WORKER_ID = os.getenv("WORKER_ID", f"worker-{socket.gethostname()}-{os.getpid()}")
POLL_INTERVAL = 5  # seconds
HEARTBEAT_INTERVAL = 60  # seconds (reduced write load vs 30s)
BATCH_SIZE = 50

app = FastAPI(title="Import Job Worker", version="1.0")
shutdown_flag = False

@app.get('/health/live')
async def liveness():
    """Kubernetes liveness probe - is process running?"""
    return {"status": "alive", "worker_id": WORKER_ID}

@app.get('/health/ready')
async def readiness():
    """Kubernetes readiness probe - can it process jobs?"""
    try:
        async with get_db() as db:
            await db.execute(text("SELECT 1"))
        return {"status": "ready", "worker_id": WORKER_ID}
    except Exception as e:
        logger.error(f"Readiness check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "error": str(e)}
        )

@app.on_event("startup")
async def startup():
    """Start job processing loop as background task"""
    await init_db()
    asyncio.create_task(worker_main_loop())
    logger.info(f"Worker {WORKER_ID} started")

async def worker_main_loop():
    """Main job processing loop - runs as background task"""
    logger.info(f"Worker loop starting, polling every {POLL_INTERVAL}s")

    while not shutdown_flag:
        try:
            job = await claim_next_job(WORKER_ID)

            if job is None:
                await asyncio.sleep(POLL_INTERVAL)
                continue

            logger.info(f"Claimed job {job.id}")

            try:
                await process_job(job)
            except Exception as e:
                logger.error(f"Job {job.id} failed: {e}")
                await fail_job(job.id, str(e))
        except Exception as e:
            logger.error(f"Worker loop error: {e}")
            await asyncio.sleep(POLL_INTERVAL)

    logger.info(f"Worker {WORKER_ID} shut down cleanly")

async def process_job(job):
    """Process all stages for a job with batch checkpointing."""
    while True:
        async with get_db() as db:
            current_stage = await get_current_stage(db, job.id)

            if current_stage is None:
                # All stages complete
                await complete_job(db, job.id)
                logger.info(f"Job {job.id} completed")
                break

            # Check if job was paused
            if job.status == "paused":
                logger.info(f"Job {job.id} paused")
                break

            # Run one batch using worker's stage runner
            runner = STAGE_RUNNERS[current_stage.stage_name]

            try:
                result = await runner(db, job.id, BATCH_SIZE)

                # Update stage progress
                await update_stage_progress(
                    db,
                    job.id,
                    current_stage.stage_name,
                    result["records_processed"],
                    result.get("checkpoint_data"),
                )

                if result["stage_complete"]:
                    await transition_stage(db, job.id, current_stage.stage_name, "completed")

                await heartbeat_job(db, job.id, WORKER_ID)
                await db.commit()

            except Exception as e:
                logger.error(f"Stage {current_stage.stage_name} failed: {e}")
                await transition_stage(db, job.id, current_stage.stage_name, "failed")
                await fail_job(db, job.id, str(e))
                await db.commit()
                raise
```

### State Management (API Service)

```python
# apps/api/src/api/services/import_pipeline.py
async def get_current_stage(db: AsyncSession, job_id: str) -> ImportJobStage | None:
    """Get the current active stage for a job."""
    result = await db.execute(
        select(ImportJobStage)
        .where(ImportJobStage.job_id == job_id)
        .where(ImportJobStage.status.in_([ImportJobStageStatus.PENDING, ImportJobStageStatus.RUNNING]))
        .order_by(ImportJobStage.created_at)
    )
    return result.scalars().first()

async def update_stage_progress(
    db: AsyncSession,
    job_id: str,
    stage_name: str,
    records_processed: int,
    checkpoint_data: dict | None = None,
) -> None:
    """Update stage progress after batch completion."""
    result = await db.execute(
        select(ImportJobStage)
        .where(ImportJobStage.job_id == job_id)
        .where(ImportJobStage.stage_name == stage_name)
    )
    stage = result.scalars().first()

    if stage:
        stage.records_processed += records_processed
        stage.last_checkpoint = datetime.utcnow()
        if checkpoint_data:
            stage.stage_data = checkpoint_data

async def transition_stage(
    db: AsyncSession,
    job_id: str,
    stage_name: str,
    status: str,
) -> None:
    """Transition a stage to a new status."""
    result = await db.execute(
        select(ImportJobStage)
        .where(ImportJobStage.job_id == job_id)
        .where(ImportJobStage.stage_name == stage_name)
    )
    stage = result.scalars().first()

    if stage:
        stage.status = ImportJobStageStatus[status.upper()]
        if status == "completed":
            stage.completed_at = datetime.utcnow()
        elif status == "failed":
            stage.completed_at = datetime.utcnow()
```

## Stage Runner Stubs

For PR6, implement minimal stubs that simulate work:

```python
# apps/worker/stage_runners.py
async def validate_stage(db: AsyncSession, job_id: str, batch_size: int) -> dict:
    """Validate GEDCOM file format."""
    job = await db.get(ImportJob, job_id)

    # Read first 1KB to check GEDCOM header
    storage_path = get_gedcom_storage_path(job.user_id, job.id)
    full_path = Path("/data/gedcom") / storage_path / "original.ged"

    with open(full_path, "rb") as f:
        header = f.read(1024).decode("utf-8", errors="ignore")

    if "0 HEAD" not in header:
        raise ValueError("Invalid GEDCOM file: missing 0 HEAD")

    # Count records (simplified: count "0 @" lines)
    record_count = 0
    with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            if line.startswith("0 @"):
                record_count += 1

    # Update records_total for all stages
    stages = await db.execute(
        select(ImportJobStage).where(ImportJobStage.job_id == job_id)
    )
    for stage in stages.scalars():
        stage.records_total = record_count

    return {
        "records_processed": record_count,
        "stage_complete": True,
        "stage_data": {"record_count": record_count}
    }

async def parse_stage(db: AsyncSession, job_id: str, batch_size: int) -> dict:
    """Parse GEDCOM (stub for now)."""
    stage = await get_stage(db, job_id, "parse")

    # Simulate processing batch_size records
    remaining = stage.records_total - stage.records_processed
    to_process = min(batch_size, remaining)

    # Simulate work (0.01s per record)
    await asyncio.sleep(to_process * 0.01)

    return {
        "records_processed": to_process,
        "stage_complete": (stage.records_processed + to_process >= stage.records_total),
        "stage_data": {"batch_number": (stage.stage_data.get("batch_number", 0) + 1)}
    }

# Similar stubs for normalize, search, match, review...
STAGE_RUNNERS = {
    "validate": validate_stage,
    "parse": parse_stage,
    "normalize": normalize_stage,
    "search": search_stage,
    "match": match_stage,
    "review": review_stage,
}
```

## UI Components

### ImportJobPage Layout

```
+--------------------------------------------------+
| Import Jobs                        [Upload GEDCOM]|
+--------------------------------------------------+
|                                                  |
| [ImportJobCard - Running]                        |
| [ImportJobCard - Completed]                      |
| [ImportJobCard - Failed]                         |
|                                                  |
+--------------------------------------------------+
```

### ImportJobCard Layout

```
+--------------------------------------------------+
| family.ged                    [Pause] [Cancel]   |
| Running - 873 / 1250 records (70%)              |
|                                                  |
| ✓ Validate   1250/1250  [=========] 100%        |
| → Parse       873/1250  [======---]  70%        |
|   Normalize     0/1250  [---------]   0%        |
|   Search        0/1250  [---------]   0%        |
|   Match         0/1250  [---------]   0%        |
|   Review        0/1250  [---------]   0%        |
|                                                  |
| Started: 2 minutes ago                           |
| Last update: 5 seconds ago                       |
+--------------------------------------------------+
```

## Testing Strategy

### Backend Unit Tests

#### 1. `apps/api/tests/test_import_jobs_routes.py` (NEW)

HTTP endpoint tests - validates routing, auth, request/response:

**POST /api/import-jobs:**
- ✓ Upload valid GEDCOM → 201 with job object
- ✓ Upload without file → 422 validation error
- ✓ Upload file exceeding size limit (100MB) → 413
- ✓ Upload non-.ged file → 422 validation error
- ✓ Filename with path traversal (../) → sanitized
- ✓ Unauthorized request → 401

**GET /api/import-jobs:**
- ✓ User with jobs → 200 with paginated list
- ✓ User with no jobs → 200 empty array
- ✓ Invalid pagination params → 422
- ✓ Only returns current user's jobs (filter test)
- ✓ Unauthorized → 401

**GET /api/import-jobs/{id}:**
- ✓ Job exists, correct user → 200 with job detail
- ✓ Job exists, wrong user → 404 (don't leak existence)
- ✓ Job not found → 404
- ✓ Unauthorized → 401

**POST /api/import-jobs/{id}/pause:**
- ✓ Pause running job → 200, status=paused
- ✓ Pause already paused → 200 (idempotent)
- ✓ Pause completed job → 409
- ✓ Wrong user → 404

**POST /api/import-jobs/{id}/resume:**
- ✓ Resume paused job → 200, status=pending
- ✓ Resume already pending → 200 (idempotent)
- ✓ Resume completed job → 409
- ✓ Wrong user → 404

**DELETE /api/import-jobs/{id}:**
- ✓ Delete pending job → 200, files removed
- ✓ Delete running job → 200, cancel + cleanup
- ✓ Verify GEDCOM files deleted from disk
- ✓ Wrong user → 404

#### 2. `apps/api/tests/test_import_pipeline.py` (EXPAND EXISTING)

Service layer tests - validates business logic, database operations:

**create_import_job():**
- ✓ Create with valid file → job + 6 stages in DB
- ✓ File stored at {user_id}/{job_id}/original.ged
- ✓ Metadata captured (filename, size, timestamp)
- ✓ Filename sanitization (replace unsafe chars)
- ✓ Concurrent creates → unique constraint handled

**claim_next_job():**
- ✓ Returns oldest pending job (FIFO ordering)
- ✓ Two workers cannot claim same job (race test)
- ✓ Reclaims stale job (heartbeat > STALE_TIMEOUT)
- ✓ Returns None when no jobs available
- ✓ Skips paused jobs

**heartbeat_job():**
- ✓ Updates heartbeat timestamp
- ✓ Job without heartbeat for STALE_TIMEOUT becomes claimable
- ✓ Heartbeat with wrong worker_id → error
- ✓ Heartbeat non-existent job → error

**get_current_stage():**
- ✓ Returns first pending stage
- ✓ Returns running stage if exists
- ✓ Returns None when all stages complete
- ✓ Respects stage ordering

**update_stage_progress():**
- ✓ Increments records_processed
- ✓ Updates last_checkpoint timestamp
- ✓ Stores checkpoint_data JSONB
- ✓ Invalid stage_name → error

**transition_stage():**
- ✓ pending → running → completed
- ✓ pending → failed
- ✓ Sets completed_at timestamp
- ✓ Invalid state transition → error

**fail_job():**
- ✓ Marks job status=failed
- ✓ Captures error message
- ✓ Sets completed_at
- ✓ Failed job not reclaimed
- ✓ Idempotent (fail already-failed)

#### 3. `apps/worker/tests/test_worker_main.py` (NEW)

Worker process tests - validates execution loop, signal handling:

**Main loop:**
- ✓ Poll → claim → process → heartbeat cycle
- ✓ No jobs available → sleep POLL_INTERVAL → retry
- ✓ Worker claims and completes 3 jobs sequentially
- ✓ Exception in process_job → log + continue (don't crash)

**Signal handling:**
- ✓ SIGTERM → complete current batch → shutdown cleanly
- ✓ SIGINT → complete current batch → shutdown cleanly
- ✓ Signal during poll (no job) → shutdown immediately
- ✓ Shutdown flag prevents new job claims

**process_job():**
- ✓ Processes all 6 stages end-to-end
- ✓ Checks pause status before each batch
- ✓ Heartbeat called per batch (timing verification)
- ✓ Stage failure → fail_job() called
- ✓ All stages complete → complete_job() called

#### 4. `apps/worker/tests/test_stage_runners.py` (NEW)

Stage runner tests - validates execution logic, error handling:

**validate_stage():**
- ✓ Valid GEDCOM → counts records, returns stage_complete=True
- ✓ Missing "0 HEAD" → raises ValueError
- ✓ File not found → raises FileNotFoundError
- ✓ Invalid UTF-8 encoding → handles with errors='ignore'
- ✓ Empty file → returns record_count=0
- ✓ Sets records_total on all stages

**Stub stages (parse/normalize/search/match/review):**
- ✓ Process single batch → records_processed incremented
- ✓ Process final batch → stage_complete=True
- ✓ Simulate work timing (sleep)
- ✓ Checkpoint data increments batch_number
- ✓ All stubs follow same contract (return dict)

### Frontend Unit Tests

#### 5. `apps/ui/tests/ImportJobPage.test.tsx` (NEW)

**Rendering:**
- ✓ Renders job list when jobs exist
- ✓ Renders empty state when no jobs
- ✓ Shows upload GEDCOM button
- ✓ Job status badges displayed correctly

**Upload form:**
- ✓ File input accepts .ged files
- ✓ Submit triggers POST /import-jobs
- ✓ Success → job added to list
- ✓ Error → displays error message

**Auto-refresh:**
- ✓ Polls GET /import-jobs every 2 seconds when running job exists
- ✓ Stops polling when all jobs complete
- ✓ Cleanup on component unmount

**User interactions:**
- ✓ Click job card → shows detail view
- ✓ Pause button → POST /pause → status updates
- ✓ Resume button → POST /resume → status updates
- ✓ Delete button → DELETE /job → removed from list

#### 6. `apps/ui/tests/ImportJobCard.test.tsx` (NEW)

**Rendering:**
- ✓ Renders job filename and status badge
- ✓ Progress bars for each stage
- ✓ Overall completion percentage
- ✓ Timestamps (started, last update)

**Status badges:**
- ✓ Pending → gray badge
- ✓ Running → blue animated badge
- ✓ Paused → yellow badge
- ✓ Completed → green badge
- ✓ Failed → red badge

**Action buttons:**
- ✓ Running job → Pause and Cancel buttons visible
- ✓ Paused job → Resume and Cancel buttons visible
- ✓ Completed job → only View button visible
- ✓ Failed job → Retry and Delete buttons (future)

**Progress visualization:**
- ✓ Stage checkmark when completed
- ✓ Current stage highlighted
- ✓ Pending stages grayed out
- ✓ Error indicator on failed stage

### Integration Tests

**1. End-to-End Job Execution** (Backend integration test)
- Create job via service layer
- Worker claims and processes all 6 stages
- Each stage completes in order
- Job marked completed
- All checkpoints persisted

**2. Multi-Job Processing** (Backend integration test)
- Create 3 jobs
- Worker processes in FIFO order
- Each completes independently
- Verify isolation (no cross-job contamination)

**3. Pause/Resume Workflow** (Backend integration test)
- Start job processing
- Pause mid-stage
- Verify worker stops after current batch
- Resume
- Verify processing continues from checkpoint

**4. Worker Crash Recovery** (Backend integration test)
- Start job processing
- Simulate worker crash (don't call heartbeat)
- Wait for STALE_TIMEOUT
- New worker claims and resumes from last checkpoint
- Job completes successfully

### E2E Tests (Deferred to later PR)

Full user flow with Playwright, deferred until backend + frontend integrated:
- Upload GEDCOM via UI
- Watch progress updates in real-time
- Pause/resume via UI
- Job completes
- View completed job detail

## Acceptance Criteria

- [ ] POST /api/import-jobs accepts GEDCOM upload and creates job
- [ ] Worker claims pending jobs and processes stages in order
- [ ] Each stage processes in batches with durable checkpoints
- [ ] Job status updates visible via GET /api/import-jobs/{id}
- [ ] Pause stops job after current batch, resume re-queues it
- [ ] Cancel deletes job and GEDCOM files
- [ ] Clean separation: API owns HTTP + state management, Worker owns job execution + stage logic
- [ ] Stale jobs (no heartbeat) are reclaimed by another worker
- [ ] Failed stages mark job as failed with error message
- [ ] UI shows job list with status badges
- [ ] UI shows job detail with stage progress bars
- [ ] Database models and state management only - execution logic lives in worker
- [ ] UI auto-refreshes while job is running
- [ ] All tests pass (backend + frontend)
- [ ] Backend coverage ≥ 80%
- [ ] Worker runs as FastAPI application via `uvicorn worker.main:app --port 8081`
- [ ] Worker health endpoints (`/health/live`, `/health/ready`) return correct status

## Future Enhanced in Later PRs

This PR establishes infrastructure only. Later PRs will:

- PR7: Replace parse/normalize stubs with real GEDCOM parsing
- PR8: Replace search/match stubs with WikiTree API + dump search
- PR9: Replace review stub with evidence packet generation
- PR10+: Add UI for reviewing matches, approving candidates

## Notes

- **Why stubs?** Lets us test the worker pattern, checkpointing, and job lifecycle without implementing complex parsing/matching logic first. Each stub simulates realistic batch processing.

- **Why 10 files?** At the limit but necessary. Worker is a separate process (`apps/worker/`) not part of API. Groups related logic appropriately.

- **Why no dump integration?** PR5 deferred until WikiTree dump access available. Search/match stubs will work without it.

- **Worker deployment:** Separate `apps/worker/` directory with FastAPI application. Run via `uvicorn worker.main:app --port 8081`. Docker compose starts worker container on port 8081 with health check endpoints (`/health/live`, `/health/ready`) for Kubernetes probes. For production, scale horizontally with multiple worker pods. Worker imports from `api` package for shared models/services. Background task runs job processing loop.

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | — |
| Codex Review | `/codex review` | Independent 2nd opinion | 0 | — | — |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | CLEAR (PLAN) | 8 issues, 1 critical gap (FileNotFoundError handler) |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | — |

**UNRESOLVED:** 0 decisions pending

**CRITICAL GAPS PLANNED FOR IMPLEMENTATION:**
- Gap #3: Add a `FileNotFoundError` handler to `stage_runners` so the job fails gracefully if the GEDCOM file is deleted
- Gap #4: DB connection loss - accepted plan decision (rely on job reclaim via heartbeat timeout)
- Gap #8: Duplicate batch work on crash - accepted plan decision (rare, stubs don't care, real parsing will address)

**PERFORMANCE OPTIMIZATIONS TO IMPLEMENT:**
1. N+1 query → use SQLAlchemy `joinedload()` for job + stages
2. Double file read → switch to single-pass validation
3. Missing indexes → add a composite index on `(status, created_at)`
4. Aggressive polling → implement exponential backoff (2s→5s→10s)
5. Limit enforcement → enforce via Pydantic `Field(le=100)`
6. Heartbeat writes → use a 60s interval (halved from 30s)
7. Unconditional JSONB updates → make updates conditional
8. File size enforcement → enforce via FastAPI Form `max_size` validation

**SCOPE ADDITIONS:**
- Worker health endpoints (`/health/live`, `/health/ready`) moved from TODO to base scope - essential for production deployment (adds ~15 min)
- Worker implemented as FastAPI application instead of pure Python process (enables Kubernetes health probes, monitoring integrations)

**VERDICT:** ENG CLEARED — ready to implement
