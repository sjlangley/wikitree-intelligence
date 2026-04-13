# TODOs

## Safe WikiTree Write-Back From Sync Review

What:
Add a future workflow for applying approved later sync-review items back into WikiTree
in a deliberate, traceable way.

Why:
Version 1 can identify matched profiles where GEDCOM contains useful facts or sources
that WikiTree does not yet have. Without a follow-up write-back flow, that value stops at
review instead of improving the real tree.

Pros:
- Turns review findings into real WikiTree improvements
- Keeps import and enrichment separate
- Creates a clear path from evidence packet to user-approved update

Cons:
- Needs careful auth and API boundary design
- Requires audit history and rollback thinking
- Raises trust and correctness requirements compared with read-only review

Context:
This should not be part of the initial import pipeline. Import resolves identity,
produces evidence packets, and populates the later sync-review queue. A future write-back
workflow would take human-approved deltas from that queue and convert them into explicit
WikiTree updates with traceability.

Depends on / blocked by:
- Version 1 later sync-review queue
- Stable evidence packet format
- Confirmed WikiTree authentication and update capabilities

## Worker Metrics and Observability

What:
Add structured logging and metrics for worker performance tracking (jobs/sec, average batch duration, queue depth, stage timing).

Why:
Worker runs headless with no telemetry. Production performance issues require guessing at bottlenecks and capacity limits.

Pros:
- Enables data-driven capacity planning
- Faster diagnosis of performance regressions
- Visibility into stage-specific bottlenecks
- Foundation for auto-scaling decisions

Cons:
- Adds ~30 minutes of implementation work
- Introduces metrics library dependency (likely Prometheus client)
- Small runtime overhead for metric collection

Context:
Essential for production deployment. Without metrics, we can't answer basic questions like "how many jobs per hour can one worker handle?" or "which stage is the slowest?" Should include: jobs claimed/completed/failed per minute, batch processing time (p50/p95/p99), current queue depth, worker uptime.

Depends on / blocked by:
- None (can be added to worker main loop immediately)

## Stage Retry Logic with Exponential Backoff

What:
Automatically retry failed stages up to 3 attempts with exponential backoff (1min, 5min, 15min) before marking job as permanently failed.

Why:
Currently jobs fail permanently on first error. Transient failures (network hiccups, temporary WikiTree API unavailability, rate limits) cause user-visible failures that could self-heal.

Pros:
- Improves reliability without user intervention
- Handles rate limiting gracefully
- Reduces support burden from transient errors
- Industry standard pattern

Cons:
- Adds complexity to error handling
- Failed jobs take longer to surface (up to ~20 minutes)
- Need to distinguish transient vs permanent errors

Context:
Should track retry count and backoff timing in import_job_stages.stage_data JSONB. Log each retry attempt with error details. Surface retry status in UI ("Retrying in 5 minutes..."). Consider making retry count/intervals configurable per stage type.

Depends on / blocked by:
- None (extends existing stage transition logic)

## Job Priority Queue

What:
Add priority field to import_jobs table. High-priority jobs are claimed before lower-priority jobs regardless of creation time.

Why:
All jobs currently processed FIFO. No way to prioritize VIP users, urgent imports, or smaller jobs that can complete quickly.

Pros:
- Supports tiered service levels
- Improves perceived performance (small jobs don't wait behind large ones)
- Enables emergency queue-jumping when needed
- Minimal schema change

Cons:
- Risk of priority inversion (low-priority jobs starve)
- Need UI/API to set priority
- Adds ~20 minutes work

Context:
Add priority ENUM ('low', 'normal', 'high', 'urgent') with default 'normal'. Update claim_next_job() query to ORDER BY priority DESC, created_at ASC. Consider adding priority to user settings (paid users get 'high' by default). May need max-priority-age rule to prevent starvation.

Depends on / blocked by:
- None (straightforward schema + query change)

## Progress ETA Display

What:
Calculate and display estimated time remaining based on records processed per second and records remaining.

Why:
UI shows "873 / 1250 records (70%)" but users ask "how much longer?" Without ETA, large imports feel endless.

Pros:
- Better user experience (set expectations)
- Reduces "is it stuck?" support questions
- Helps users decide pause vs wait
- Industry standard UX pattern

Cons:
- ETA accuracy depends on consistent stage timing
- Can be misleading if work isn't uniform (early records may process faster)
- ~30 minutes implementation

Context:
Calculate rolling average of records/second over last 5 checkpoints. Display "~5 minutes remaining" in UI. Update calculation after each progress update. Show "Calculating..." for first few batches. Consider per-stage ETA since different stages have different speeds. Handle edge cases: paused jobs, stage transitions, batch size changes.

Depends on / blocked by:
- Worker metrics (TODO 1) - need timing history to calculate accurate ETA

## Immediate Job Cancellation

What:
Support CANCEL button that immediately terminates worker mid-batch (sends SIGKILL to worker process handling that job).

Why:
Current PAUSE waits for batch to complete (~5-30 seconds). Users expect CANCEL to stop immediately, especially for accidental uploads.

Pros:
- Matches user mental model of "cancel"
- Frees resources faster
- Better UX for large file mistakes
- Clear distinction between pause and cancel

Cons:
- Needs worker process management (track PIDs, send signals)
- Risk of partial batch leaving inconsistent state
- Adds ~25 minutes complexity
- Requires careful cleanup of partial work

Context:
Add job_id → worker_pid mapping in Redis or database. CANCEL endpoint sends SIGKILL to worker, marks job cancelled, cleans up lock. Worker needs signal handler to mark interrupted batches. Consider SIGTERM before SIGKILL to allow graceful cleanup. Document that cancelled jobs may need manual cleanup of partial parsed data.

Depends on / blocked by:
- None (but requires process tracking infrastructure)

## Dynamic Batch Size Tuning

What:
Auto-adjust batch size based on average record processing time. Start at 50, increase to 100 if records process quickly (<10ms), decrease to 25 if slow (>50ms).

Why:
Fixed 50 records/batch may be inefficient. Simple GEDCOM records (minimal fields) could batch 200+. Complex records (many relations, sources) may need batches of 10.

Pros:
- Optimizes throughput automatically
- Adapts to file characteristics
- Reduces checkpoint overhead for simple files
- Improves responsiveness for complex files

Cons:
- Adds tuning complexity
- Need to measure and track timing accurately
- ~40 minutes implementation
- Won't show benefit until real parsing implemented

Context:
Track average ms/record for last 3 batches in stage_data. Adjust batch size up/down by 25% when crossing thresholds. Cap at min=10, max=500. Log batch size changes for observability. Consider per-stage tuning (validation may want larger batches than matching).

Depends on / blocked by:
- Real GEDCOM parsing implementation (stubs have no timing variation)

## Job History Retention Policy

What:
Auto-archive completed and failed jobs older than 30 days to import_jobs_archive table. Keep recent jobs in main table for performance.

Why:
Without retention policy, import_jobs table grows unbounded. Large tables slow down job claiming query and list endpoints.

Pros:
- Maintains query performance over time
- Reduces backup size and cost
- Preserves data for auditing (not deleted)
- Clear lifecycle policy

Cons:
- Need scheduled task (cron/airflow)
- Need archive table + migration
- Adds ~35 minutes work
- Need UI access to archived jobs

Context:
Create import_jobs_archive table (same schema + archived_at timestamp). Daily cron job moves jobs with completed_at/updated_at > 30 days. Keep index on archive table for user queries. API filters to recent jobs by default, archived jobs via ?include_archived=true. Consider compressed storage for archive table.

Depends on / blocked by:
- None (but wait until production has meaningful job volume to test cutoffs)
