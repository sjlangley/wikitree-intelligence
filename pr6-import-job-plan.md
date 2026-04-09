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
      AND (worker_id IS NULL OR heartbeat_at < NOW() - INTERVAL '5 minutes')
    ORDER BY created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
    
    UPDATE import_jobs
    SET worker_id = %worker_id,
        heartbeat_at = NOW(),
        status = 'running'
    WHERE id = %job_id
```

**Heartbeat refresh:** Every 30 seconds while processing

**Stale job recovery:** If heartbeat hasn't updated in 5 minutes, job is reclaimed by another worker

## Files to Create/Modify (10 files)

### Backend API (5 files)

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
   - Main worker loop (run via `python -m worker.main`)
   - Polls for jobs every 5 seconds
   - Claims job via API service, runs batches using local stage runners
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

### Tests (1 file)

10. **`apps/api/tests/test_import_pipeline.py`** (NEW)
    - Test job creation with file upload
    - Test lease claiming (no double-claim race)
    - Test heartbeat refresh
    - Test stale job reclaim after timeout
    - Test stage transitions
    - Test batch processing with checkpoints
    - Test pause/resume
    - Test job failure and error capture

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
- `heartbeat_at` - Updated every 30s by worker
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

### Main Loop

```python
# apps/worker/main.py
import asyncio
import os
import signal
import socket
import sys
import time
from pathlib import Path

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
HEARTBEAT_INTERVAL = 30  # seconds
BATCH_SIZE = 50

shutdown_flag = False

def signal_handler(signum, frame):
    global shutdown_flag
    logger.info(f"Received signal {signum}, shutting down gracefully...")
    shutdown_flag = True

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

async def main():
    # Initialize database connection
    await init_db()
    
    logger.info(f"Worker {WORKER_ID} starting...")
    
    while not shutdown_flag:
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
    
    logger.info(f"Worker {WORKER_ID} shut down cleanly")

async def Get current stage
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
    State Management (API responsibility)

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
            if result.get("stage_data"):
                current_stage.stage_data = result["stage_data"]
            
            if result["stage_complete"]:
                current_stage.status = ImportJobStageStatus.COMPLETED
                curre (Worker responsibility)

For PR6, implement minimal stubs that simulate work:

```python
# apps/worker
                "job_complete": False,
                "job_paused": False,
                "records_processed": result["records_processed"]
            }
            
        except Exception as e:
            logger.error(f"Stage {current_stage.stage_name} failed: {e}")
            current_stage.status = ImportJobStageStatus.FAILED
            current_stage.error_message = str(e)
            current_stage.completed_at = datetime.utcnow()
            
            job.status = ImportJobStatus.FAILED
            await db.commit()
            
            return {"job_failed": True, "error": str(e)}
```

## Stage Runner Stubs

For PR6, implement minimal stubs that simulate work:

```python
# apps/api/src/api/services/stage_runners.py
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

### Unit Tests

1. **Job Creation**
   - Upload GEDCOM creates job + 6 stages
   - File stored at correct path
   - Metadata captured correctly

2. **Lease Claiming**
   - claim_next_job returns oldest pending job
   - Two workers cannot claim same job (race condition test)
   - Stale jobs (heartbeat > 5min) are reclaimed

3. **Heartbeat**
   - heartbeat_job updates timestamp
   - Job without heartbeat for 5min becomes claimable

4. **Batch Processing**
   - run_stage_batch processes batch_size records
   - Checkpoint updates after each batch
   - Stage transitions when records_processed == records_total

5. **Pause/Resume**
   - Paused job stops processing after current batch
   - Resumed job becomes pending and gets reclaimed
   - Paused job not claimed by workers

6. **Failure Handling**
   - Stage error marks stage + job as failed
   - Error message captured
   - Failed job not reclaimed

### Integration Tests

1. **End-to-End Job Execution**
   - Create job
   - Worker claims and processes all stages
   - Job completes successfully
   - All stages marked completed

2. **Multi-Job Processing**
   - Create 3 jobs
   - Worker processes them in order (FIFO)
   - Each job completes independently

## Acceptance Criteria

- [ ] POST /api/import-jobs accepts GEDCOM upload and creates job
- [ ] Worker claims pending jobs and processes stages in order
- [ ] Each stage processes in batches with durable checkpoints
- [ ] Job status updates visible via GET /api/import-jobs/{id}
- [ ] Pause stops job after current batch, resume re-queues it
- [ ] Cancel deletes job and GEDCOM filesClean separation: API owns HTTP + state management, Worker owns job execution + stage logic
- [ ] Stale jobs (no heartbeat) are reclaimed by another worker
- [ ] Failed stages mark job as failed with error message
- [ ] UI shows job list with status badges
- [ ] UI shows job detail with stage progress barsdatabase models and state management only - execution logic lives in worker
- [ ] UI auto-refreshes while job is running
- [ ] All tests pass (backend + frontend)
- [ ] Backend coverage ≥ 80%
- [ ] Worker runs as separate process via `python -m worker.main`

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

- **Worker deployment:** Separate `apps/worker/` directory with its own entry point. Docker compose starts worker container. For production, scale horizontally with multiple worker pods. Worker imports from `api` package for shared models/services.
