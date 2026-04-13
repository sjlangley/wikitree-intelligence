# Import Job Worker

Background worker process for executing resumable, staged GEDCOM import jobs.

## Overview

The worker is a FastAPI application that claims and processes import jobs from a PostgreSQL-backed job queue. It runs independently from the main API server, enabling horizontal scaling and fault tolerance.

**Architecture pattern:** Lease-based job claiming with heartbeat monitoring

- Worker polls database for pending jobs (every 5 seconds)
- Claims jobs with exclusive lock (PostgreSQL `FOR UPDATE SKIP LOCKED`)
- Processes work in small batches (50 records at a time)
- Commits checkpoints after each batch
- Refreshes heartbeat every 60 seconds
- Releases job on completion or failure

## Job Processing Pipeline

Each import job progresses through 6 stages:

1. **validate** - GEDCOM format validation, encoding check, record counting
2. **parse** - Extract people and relationships (stub for now)
3. **normalize** - Clean names, dates, places (stub for now)
4. **search** - Find WikiTree candidate matches (stub for now)
5. **match** - Score and rank candidates (stub for now)
6. **review** - Populate review queue with evidence (stub for now)

**Batch processing:** Each stage processes 50 records per batch, commits checkpoint to database, then continues. Jobs are resumable from the last checkpoint if the worker crashes.

**Stale job recovery:** If a worker crashes, its heartbeat stops updating. After 10 minutes of no heartbeat, another worker automatically reclaims and resumes the job from the last checkpoint.

## Running the Worker

### Local Development

```bash
cd apps/worker

# Set environment variables
export DATABASE_URL="postgresql+asyncpg://user:pass@localhost/wikitree"
export WORKER_ID="worker-local-$(hostname)"

# Run with uvicorn
uvicorn worker.main:app --port 8081 --reload
```

### Production Deployment

```bash
# Docker
docker run -p 8081:8081 \
  -e DATABASE_URL="..." \
  -e WORKER_ID="worker-pod-xyz" \
  -v /data/gedcom:/data/gedcom \
  wikitree-worker:latest

# Kubernetes
kubectl apply -f k8s/worker-deployment.yaml
```

### Health Endpoints

The worker exposes two health check endpoints for Kubernetes probes:

- **`GET /health/live`** - Liveness probe (is process running?)
  - Returns 200 if process is alive
  - Never returns error (if it can respond, it's alive)

- **`GET /health/ready`** - Readiness probe (can it process jobs?)
  - Returns 200 if database connection is healthy
  - Returns 503 if database is unreachable
  - Use for load balancer routing decisions

**Example Kubernetes probes:**

```yaml
livenessProbe:
  httpGet:
    path: /health/live
    port: 8081
  initialDelaySeconds: 10
  periodSeconds: 30

readinessProbe:
  httpGet:
    path: /health/ready
    port: 8081
  initialDelaySeconds: 5
  periodSeconds: 10
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | Yes | - | PostgreSQL connection string (must use asyncpg driver) |
| `WORKER_ID` | No | `worker-{hostname}-{pid}` | Unique worker identifier for lease tracking |
| `POLL_INTERVAL` | No | `5` | Seconds between job queue polls |
| `HEARTBEAT_INTERVAL` | No | `60` | Seconds between heartbeat updates |
| `BATCH_SIZE` | No | `50` | Records to process per batch |
| `LOG_LEVEL` | No | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |

## File Structure

```
apps/worker/
├── README.md              # This file
├── __init__.py            # Python package marker
├── main.py                # FastAPI app + worker loop
├── stage_runners.py       # Stage execution logic
└── tests/
    ├── test_worker_main.py
    └── test_stage_runners.py
```

## Stage Runners

Each stage is implemented as an async function in `stage_runners.py`:

```python
async def validate_stage(db: AsyncSession, job_id: str, batch_size: int) -> dict:
    """
    Validate GEDCOM file format, count records.

    Returns:
        {
            "records_processed": int,    # Number of records processed in this batch
            "stage_complete": bool,      # True if stage finished
            "checkpoint_data": dict      # Stage-specific state (for resume)
        }
    """
```

**Contract:** All stage runners must:
- Accept `db`, `job_id`, `batch_size` parameters
- Return dict with `records_processed`, `stage_complete`, `checkpoint_data`
- Raise exceptions for unrecoverable errors (will fail job)
- Handle `FileNotFoundError` gracefully (GEDCOM file deleted)

**Stubs:** Stages 2-6 are currently stubs that simulate work with `asyncio.sleep()`. They will be replaced with real implementations in future PRs:
- PR7: Real GEDCOM parsing
- PR8: WikiTree search and matching
- PR9: Evidence packet generation

## Graceful Shutdown

The worker handles `SIGTERM` and `SIGINT` signals gracefully:

1. Sets `shutdown_flag = True`
2. Finishes processing current batch
3. Commits checkpoint to database
4. Exits cleanly (does not claim new jobs)

**Important:** Do not send `SIGKILL` unless absolutely necessary. Use `SIGTERM` to allow checkpoint commit.

```bash
# Graceful shutdown
kill -TERM <worker-pid>

# Force kill (may lose current batch progress)
kill -KILL <worker-pid>
```

## Monitoring and Observability

### Logging

The worker logs structured information for debugging:

```
INFO:worker:Worker worker-pod-123 started
INFO:worker:Worker loop starting, polling every 5s
INFO:worker:Claimed job abc-123
INFO:worker:Processing stage validate for job abc-123 (batch 1)
INFO:worker:Stage validate completed for job abc-123
INFO:worker:Job abc-123 completed
```

**Log levels:**
- `DEBUG`: Detailed batch processing, checkpoint data
- `INFO`: Job lifecycle events, stage transitions
- `WARNING`: Recoverable errors, retries
- `ERROR`: Job failures, database errors

### Metrics (Future)

Future PRs will add Prometheus metrics:
- `worker_jobs_claimed_total` - Counter of jobs claimed
- `worker_jobs_completed_total` - Counter of jobs completed
- `worker_jobs_failed_total` - Counter of jobs failed
- `worker_batch_duration_seconds` - Histogram of batch processing time
- `worker_queue_depth` - Gauge of pending jobs in queue

## Scaling

**Horizontal scaling:** Run multiple worker instances for throughput

```bash
# Run 3 worker instances
docker-compose up --scale worker=3
```

**How it works:**
- Each worker has unique `WORKER_ID`
- PostgreSQL `FOR UPDATE SKIP LOCKED` prevents double-claiming
- Jobs are distributed FIFO across available workers
- If a worker crashes, another reclaims its job after 10 minutes

**Scaling guidelines:**
- 1 worker: ~10-20 jobs/hour (depends on GEDCOM size)
- 3 workers: ~30-60 jobs/hour
- 10 workers: ~100-200 jobs/hour

**Bottlenecks:**
- Database connection pool (increase pool size for >10 workers)
- File I/O (use object storage instead of shared volume for >20 workers)

## Testing

```bash
cd apps/worker

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=term-missing

# Run specific test file
pytest tests/test_stage_runners.py -v

# Run in watch mode
pytest-watch
```

**Test coverage targets:**
- Overall: ≥80%
- `main.py`: ≥90% (critical worker loop)
- `stage_runners.py`: ≥85% (validate stage must be well tested)

## Troubleshooting

### Worker not claiming jobs

**Symptom:** Worker polls but never claims jobs

**Diagnosis:**
```sql
-- Check pending jobs
SELECT id, status, worker_id, heartbeat_at
FROM import_jobs
WHERE status = 'pending';

-- Check stale jobs
SELECT id, status, worker_id, heartbeat_at
FROM import_jobs
WHERE status = 'running'
  AND heartbeat_at < NOW() - INTERVAL '10 minutes';
```

**Fixes:**
- Verify `DATABASE_URL` is correct
- Check database connectivity (`/health/ready` endpoint)
- Ensure jobs exist with `status='pending'`

### Job stuck in running state

**Symptom:** Job shows `running` but no progress for >10 minutes

**Diagnosis:**
```sql
-- Find stuck job
SELECT id, worker_id, heartbeat_at, updated_at
FROM import_jobs
WHERE id = 'abc-123';
```

**Fixes:**
- If `heartbeat_at` is stale (>10 min old), wait for auto-reclaim
- If worker crashed, restart worker to reclaim job
- If genuinely stuck, manually reset: `UPDATE import_jobs SET status='pending', worker_id=NULL WHERE id='abc-123'`

### FileNotFoundError during processing

**Symptom:** Job fails with "GEDCOM file not found"

**Root cause:** GEDCOM file was deleted from `/data/gedcom/` while job was running

**Prevention:**
- Never manually delete files from `/data/gedcom/`
- Use `DELETE /api/import-jobs/{id}` endpoint to cancel jobs (cleans up files)

**Recovery:** Job will fail gracefully with error message. User must re-upload GEDCOM.

### High database load

**Symptom:** Database CPU/connections spiking

**Diagnosis:**
- Check number of active workers: `SELECT COUNT(DISTINCT worker_id) FROM import_jobs WHERE status='running'`
- Check heartbeat write rate: ~N workers × 1 write/60s

**Fixes:**
- Reduce `HEARTBEAT_INTERVAL` to 120s (halves write load)
- Reduce worker count if over-provisioned
- Add database read replica for health checks

## Development Notes

### Adding a New Stage

1. Add stage function to `stage_runners.py`:
   ```python
   async def my_new_stage(db: AsyncSession, job_id: str, batch_size: int) -> dict:
       # Implementation
       return {
           "records_processed": count,
           "stage_complete": done,
           "checkpoint_data": state
       }
   ```

2. Register in `STAGE_RUNNERS` dict:
   ```python
   STAGE_RUNNERS = {
       # ...
       "my_new_stage": my_new_stage,
   }
   ```

3. Add to database schema (`import_job_stages` table)

4. Add tests to `tests/test_stage_runners.py`

### Testing Worker Loop Locally

```python
# In Python REPL
from worker.main import worker_main_loop, shutdown_flag
import asyncio

# Run one iteration
asyncio.run(worker_main_loop())

# Simulate graceful shutdown
shutdown_flag = True
```

## References

- [PR6 Implementation Plan](../../pr6-import-job-plan.md) - Full architectural spec
- [API Documentation](../api/README.md) - API endpoints for job management
- [Database Schema](../../schema.md) - `import_jobs` and `import_job_stages` tables
