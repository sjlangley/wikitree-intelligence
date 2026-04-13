"""Import job pipeline service layer.

Handles business logic for import job lifecycle:
- Job creation and GEDCOM file storage
- Job claiming and leasing (for worker processes)
- Progress tracking and checkpointing
- Job state transitions (pause/resume/fail/complete)
"""

from datetime import datetime, timedelta
import hashlib
import logging
from pathlib import Path
import shutil
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import ImportJob, ImportJobStage
from api.state_machines import ImportJobStageStatus, ImportJobStatus

logger = logging.getLogger(__name__)


async def create_import_job(
    db: AsyncSession,
    user_id: str,
    file: BinaryIO,
    filename: str,
    gedcom_storage_root: Path,
) -> ImportJob:
    """Create a new import job with uploaded GEDCOM file.

    Args:
        db: Database session
        user_id: User ID creating the job
        file: Uploaded GEDCOM file binary stream
        filename: Original filename
        gedcom_storage_root: Root directory for GEDCOM storage

    Returns:
        Created ImportJob with all stages initialized

    Raises:
        OSError: If file storage fails
    """
    # Create job record
    job = ImportJob(
        user_id=user_id,
        source_type='gedcom',
        original_filename=filename,
        stored_path='',  # Will be set after file storage
        file_size_bytes=0,  # Will be set after file storage
        content_sha256='',  # TODO: Calculate SHA256 hash
        status=ImportJobStatus.UPLOADED,
    )
    db.add(job)
    await db.flush()  # Get job.id

    # Store GEDCOM file (streaming to avoid memory doubling)
    storage_path = gedcom_storage_root / str(user_id) / str(job.id)
    storage_path.mkdir(parents=True, exist_ok=True)

    file_path = storage_path / 'original.ged'

    # Stream file to disk and compute size/hash incrementally
    sha256_hash = hashlib.sha256()
    file_size = 0

    with open(file_path, 'wb') as f:
        while chunk := file.read(8192):  # 8KB chunks
            f.write(chunk)
            sha256_hash.update(chunk)
            file_size += len(chunk)

    # Update job with file metadata
    job.stored_path = f'{user_id}/{job.id}/original.ged'
    job.file_size_bytes = file_size
    job.content_sha256 = sha256_hash.hexdigest()
    job.upload_completed_at = datetime.utcnow()
    # Transition to queued state now that upload is complete
    job.status = ImportJobStatus.QUEUED

    # Create stages
    stage_names = [
        'validate',
        'parse',
        'normalize',
        'search',
        'match',
        'review',
    ]
    for idx, stage_name in enumerate(stage_names):
        stage = ImportJobStage(
            import_job_id=job.id,
            stage_name=stage_name,
            order=idx,
            status=ImportJobStageStatus.PENDING,
        )
        db.add(stage)

    await db.commit()
    await db.refresh(job)

    return job


async def get_job_with_stages(
    db: AsyncSession, job_id: UUID, user_id: str
) -> tuple[ImportJob, list[ImportJobStage]] | None:
    """Get job with all stages loaded.

    Args:
        db: Database session
        job_id: Job ID to fetch
        user_id: User ID for ownership check

    Returns:
        Tuple of (ImportJob, stages list), or None if not found or unauthorized
    """
    result = await db.execute(
        select(ImportJob).where(  # pyrefly: ignore
            ImportJob.id == job_id,
            ImportJob.user_id == user_id,  # pyrefly: ignore
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        return None

    # Load stages
    stages_result = await db.execute(
        select(ImportJobStage)  # pyrefly: ignore
        .where(ImportJobStage.import_job_id == job_id)  # pyrefly: ignore
        .order_by(ImportJobStage.order)  # pyrefly: ignore
    )
    stages = list(stages_result.scalars().all())

    return (job, stages)


async def list_user_jobs(
    db: AsyncSession,
    user_id: str,
    limit: int = 20,
    offset: int = 0,
    status_filter: str | None = None,
) -> tuple[list[tuple[ImportJob, list[ImportJobStage]]], int]:
    """List user's import jobs with pagination.

    Args:
        db: Database session
        user_id: User ID
        limit: Max jobs to return
        offset: Pagination offset
        status_filter: Optional status filter
            (uploaded/queued/in_progress/paused/completed/failed/cancelled)

    Returns:
        Tuple of (jobs list, total count)
    """
    query = select(ImportJob).where(ImportJob.user_id == user_id)  # pyrefly: ignore

    if status_filter:
        try:
            status_enum = ImportJobStatus[status_filter.upper()]
            query = query.where(ImportJob.status == status_enum)  # pyrefly: ignore
        except KeyError:
            pass  # Invalid status, ignore filter

    # Get total count efficiently with COUNT(*)
    count_query = select(func.count()).select_from(query.subquery())  # pyrefly: ignore
    count_result = await db.execute(count_query)
    total = count_result.scalar_one()

    # Get paginated results
    query = (
        query.order_by(ImportJob.created_at.desc()).limit(limit).offset(offset)  # pyrefly: ignore
    )
    result = await db.execute(query)
    jobs = list(result.scalars().all())

    # Load stages for each job
    jobs_with_stages: list[tuple[ImportJob, list[ImportJobStage]]] = []
    for job in jobs:
        stages_result = await db.execute(
            select(ImportJobStage)  # pyrefly: ignore
            .where(ImportJobStage.import_job_id == job.id)  # pyrefly: ignore
            .order_by(ImportJobStage.order)  # pyrefly: ignore
        )
        stages = list(stages_result.scalars().all())
        jobs_with_stages.append((job, stages))

    return jobs_with_stages, total


async def pause_job(
    db: AsyncSession, job_id: UUID, user_id: str
) -> ImportJob | None:
    """Pause a running job.

    Args:
        db: Database session
        job_id: Job ID to pause
        user_id: User ID for ownership check

    Returns:
        Updated job, or None if not found/unauthorized

    Raises:
        ValueError: If job is not in a pauseable state
    """
    result = await get_job_with_stages(db, job_id, user_id)
    if result is None:
        return None

    job, _stages = result  # Unpack tuple

    if job.status not in (
        ImportJobStatus.QUEUED,
        ImportJobStatus.IN_PROGRESS,
    ):
        raise ValueError(f'Cannot pause job in status {job.status}')

    job.status = ImportJobStatus.PAUSED
    await db.commit()
    await db.refresh(job)

    return job


async def resume_job(
    db: AsyncSession, job_id: UUID, user_id: str
) -> ImportJob | None:
    """Resume a paused job.

    Args:
        db: Database session
        job_id: Job ID to resume
        user_id: User ID for ownership check

    Returns:
        Updated job, or None if not found/unauthorized

    Raises:
        ValueError: If job is not paused
    """
    result = await get_job_with_stages(db, job_id, user_id)
    if result is None:
        return None

    job, _stages = result  # Unpack tuple

    if job.status != ImportJobStatus.PAUSED:
        raise ValueError(f'Cannot resume job in status {job.status}')

    job.status = ImportJobStatus.QUEUED
    await db.commit()
    await db.refresh(job)

    return job


async def cancel_job(
    db: AsyncSession,
    job_id: UUID,
    user_id: str,
    gedcom_storage_root: Path,
) -> ImportJob | None:
    """Cancel and delete a job.

    Args:
        db: Database session
        job_id: Job ID to cancel
        user_id: User ID for ownership check
        gedcom_storage_root: Root directory for GEDCOM storage

    Returns:
        Cancelled job, or None if not found/unauthorized
    """
    result = await get_job_with_stages(db, job_id, user_id)
    if result is None:
        return None

    job, _stages = result  # Unpack tuple

    # Delete GEDCOM files
    storage_path = gedcom_storage_root / str(user_id) / str(job_id)
    logger.info(f'Deleting storage path for cancelled job: {storage_path}')
    if storage_path.exists():
        shutil.rmtree(storage_path)

    # Delete stages (use DELETE statement, not SELECT)
    await db.execute(
        delete(ImportJobStage).where(ImportJobStage.import_job_id == job_id)  # pyrefly: ignore
    )

    # Delete job
    await db.delete(job)
    await db.commit()

    return job


async def claim_next_job(db: AsyncSession, worker_id: str) -> ImportJob | None:
    """Claim next pending job for worker processing.

    Uses row-level locking to prevent double-claiming. Reclaims stale jobs
    where heartbeat hasn't been updated in 10 minutes.

    Args:
        db: Database session
        worker_id: Unique worker identifier

    Returns:
        Claimed job, or None if no jobs available
    """
    stale_threshold = datetime.utcnow() - timedelta(minutes=10)

    # Find next claimable job
    result = await db.execute(
        select(ImportJob)
        .where(
            ImportJob.status == ImportJobStatus.QUEUED,  # pyrefly: ignore
        )
        .where(
            (ImportJob.claimed_by.is_(None))  # pyrefly: ignore
            | (ImportJob.claimed_at < stale_threshold)  # pyrefly: ignore
        )
        .order_by(ImportJob.created_at)  # pyrefly: ignore
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    job = result.scalar_one_or_none()

    if job is None:
        return None

    # Claim the job
    job.claimed_by = worker_id
    job.claimed_at = datetime.utcnow()
    job.status = ImportJobStatus.IN_PROGRESS
    if job.started_at is None:
        job.started_at = datetime.utcnow()

    await db.commit()
    await db.refresh(job)

    # Load stages
    stages_result = await db.execute(
        select(ImportJobStage)
        .where(ImportJobStage.import_job_id == job.id)
        .order_by(ImportJobStage.id)
    )
    job.stages = list(stages_result.scalars().all())  # pyrefly: ignore[assignment]

    return job


async def heartbeat_job(db: AsyncSession, job_id: UUID, worker_id: str) -> None:
    """Refresh job heartbeat to maintain lease.

    Args:
        db: Database session
        job_id: Job ID
        worker_id: Worker ID that owns the job

    Raises:
        ValueError: If job not found or wrong worker
    """
    result = await db.execute(
        select(ImportJob).where(
            ImportJob.id == job_id, ImportJob.claimed_by == worker_id
        )
    )
    job = result.scalar_one_or_none()

    if job is None:
        raise ValueError(f'Job {job_id} not found or not owned by {worker_id}')

    job.claimed_at = datetime.utcnow()
    await db.commit()


async def get_current_stage(
    db: AsyncSession, job_id: UUID
) -> ImportJobStage | None:
    """Get the current active stage for a job.

    Args:
        db: Database session
        job_id: Job ID

    Returns:
        Current stage (pending or running), or None if all complete
    """
    result = await db.execute(
        select(ImportJobStage)  # pyrefly: ignore
        .where(ImportJobStage.import_job_id == job_id)  # pyrefly: ignore
        .where(
            ImportJobStage.status.in_(  # pyrefly: ignore
                [ImportJobStageStatus.PENDING, ImportJobStageStatus.IN_PROGRESS]
            )
        )
        .order_by(ImportJobStage.order)  # pyrefly: ignore
    )
    return result.scalars().first()


async def update_stage_progress(
    db: AsyncSession,
    job_id: UUID,
    stage_name: str,
    checkpoint_data: dict | None = None,
) -> None:
    """Update stage progress after batch completion.

    Args:
        db: Database session
        job_id: Job ID
        stage_name: Stage name
        checkpoint_data: Optional checkpoint data to store
    """
    result = await db.execute(
        select(ImportJobStage).where(
            ImportJobStage.import_job_id == job_id,
            ImportJobStage.stage_name == stage_name,
        )
    )
    stage = result.scalar_one_or_none()

    if stage is None:
        raise ValueError(f'Stage {stage_name} not found for job {job_id}')

    # Update checkpoint data
    stage.checkpoint_json = checkpoint_data or stage.checkpoint_json

    await db.commit()


async def transition_stage(
    db: AsyncSession, job_id: UUID, stage_name: str, status: str
) -> None:
    """Transition a stage to a new status.

    Args:
        db: Database session
        job_id: Job ID
        stage_name: Stage name
        status: New status (completed/failed)
    """
    result = await db.execute(
        select(ImportJobStage).where(
            ImportJobStage.import_job_id == job_id,
            ImportJobStage.stage_name == stage_name,
        )
    )
    stage = result.scalar_one_or_none()

    if stage is None:
        raise ValueError(f'Stage {stage_name} not found for job {job_id}')

    try:
        stage.status = ImportJobStageStatus[status.upper()]
    except KeyError as e:
        raise ValueError(f'Invalid status: {status}') from e

    if status.lower() in ('completed', 'failed'):
        stage.completed_at = datetime.utcnow()

    await db.commit()


async def fail_job(db: AsyncSession, job_id: UUID, error_message: str) -> None:
    """Mark job as failed with error message.

    Args:
        db: Database session
        job_id: Job ID
        error_message: Error description
    """
    await db.execute(
        update(ImportJob)
        .where(ImportJob.id == job_id)
        .values(
            status=ImportJobStatus.FAILED,
            completed_at=datetime.utcnow(),
        )
    )

    # Find failed stage and update error message
    await db.execute(
        update(ImportJobStage)  # pyrefly: ignore
        .where(  # pyrefly: ignore
            ImportJobStage.import_job_id == job_id,  # pyrefly: ignore
            ImportJobStage.status == ImportJobStageStatus.IN_PROGRESS,  # pyrefly: ignore
        )
        .values(
            status=ImportJobStageStatus.FAILED,
            error_message=error_message,
            completed_at=datetime.utcnow(),
        )
    )

    await db.commit()


async def complete_job(db: AsyncSession, job_id: UUID) -> None:
    """Mark job as completed.

    Args:
        db: Database session
        job_id: Job ID
    """
    await db.execute(
        update(ImportJob)
        .where(ImportJob.id == job_id)
        .values(
            status=ImportJobStatus.COMPLETED,
            completed_at=datetime.utcnow(),
        )
    )
    await db.commit()
