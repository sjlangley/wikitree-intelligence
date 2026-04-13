"""REST API routes for import job management.

Endpoints:
- POST /import-jobs - Create job from uploaded GEDCOM
- GET /import-jobs - List user's jobs (paginated)
- GET /import-jobs/{job_id} - Get job status with stage details
- POST /import-jobs/{job_id}/pause - Pause running job
- POST /import-jobs/{job_id}/resume - Resume paused job
- DELETE /import-jobs/{job_id} - Cancel and delete job
"""

import logging
from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import ImportJob, ImportJobStage, get_db
from api.security.session_auth import CurrentUser
from api.services import import_pipeline
from api.settings import settings

logger = logging.getLogger(__name__)

router = APIRouter()

# GEDCOM storage root directory
GEDCOM_STORAGE_ROOT = Path(settings.gedcom_storage_path)


# ============================================================================
# Response Models
# ============================================================================


class ImportJobStageResponse(BaseModel):
    """Response model for import job stage."""

    model_config = ConfigDict(extra='forbid')

    name: str
    status: str
    records_total: int | None = None
    records_processed: int | None = None
    started_at: str | None = None
    completed_at: str | None = None
    last_checkpoint: str | None = None
    error_message: str | None = None


class ImportJobResponse(BaseModel):
    """Response model for import job."""

    model_config = ConfigDict(extra='forbid')

    id: str
    user_id: str
    status: str
    original_filename: str
    file_size_bytes: int
    worker_id: str | None = None
    heartbeat_at: str | None = None
    stages: list[ImportJobStageResponse]
    created_at: str
    updated_at: str | None = None


class ImportJobListResponse(BaseModel):
    """Response model for paginated job list."""

    model_config = ConfigDict(extra='forbid')
    jobs: list[ImportJobResponse]
    total: int
    limit: int
    offset: int


class JobActionResponse(BaseModel):
    """Response model for job actions (pause/resume/delete)."""

    model_config = ConfigDict(extra='forbid')

    id: str
    status: str
    message: str


# ============================================================================
# Helper Functions
# ============================================================================


def _job_to_response(
    job: ImportJob, stages: list[ImportJobStage] | None = None
) -> ImportJobResponse:
    """Convert ImportJob to response model.

    Args:
        job: ImportJob database model
        stages: Optional list of ImportJobStage models

    Returns:
        ImportJobResponse pydantic model
    """
    stage_responses: list[ImportJobStageResponse] = []
    if stages:
        for stage in stages:
            stage_responses.append(
                ImportJobStageResponse(
                    name=stage.stage_name,
                    status=stage.status.value,
                    # TODO: Implement in stage processing
                    records_total=None,
                    records_processed=None,
                    started_at=(
                        stage.started_at.isoformat()
                        if stage.started_at
                        else None
                    ),
                    completed_at=(
                        stage.completed_at.isoformat()
                        if stage.completed_at
                        else None
                    ),
                    last_checkpoint=None,  # TODO: Implement checkpointing
                    error_message=stage.error_message,
                )
            )

    logger.info(
        'Converting job to response: %s - status: %s - stages: %d',
        job.id,
        job.status.value,
        len(stage_responses),
    )

    return ImportJobResponse(
        id=str(job.id),
        user_id=str(job.user_id),
        status=job.status.value,
        original_filename=job.original_filename,
        file_size_bytes=job.file_size_bytes,
        worker_id=job.claimed_by,
        heartbeat_at=job.claimed_at.isoformat() if job.claimed_at else None,
        stages=stage_responses,
        created_at=job.created_at.isoformat(),
        updated_at=job.created_at.isoformat(),  # TODO: Add updated_at to model
    )


# ============================================================================
# Endpoints
# ============================================================================


@router.post(
    '/import-jobs',
    response_model=ImportJobResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_import_job(
    file: Annotated[UploadFile, File()],
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportJobResponse:
    """Create a new import job from uploaded GEDCOM file.

    Args:
        file: Uploaded GEDCOM file
        current_user: Authenticated user
        db: Database session

    Returns:
        Created import job with stages

    Raises:
        HTTPException: 422 if file validation fails
        HTTPException: 413 if file too large
    """
    # Validate file
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='No filename provided',
        )

    if not file.filename.endswith('.ged'):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail='File must be a .ged GEDCOM file',
        )

    # Check file size (100MB limit)
    file.file.seek(0, 2)  # Seek to end
    file_size = file.file.tell()
    file.file.seek(0)  # Reset to beginning

    if file_size > 100 * 1024 * 1024:  # 100MB in bytes
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail='File size exceeds 100MB limit',
        )

    # Sanitize filename
    safe_filename = Path(file.filename).name  # Remove path components

    # Create job
    job = await import_pipeline.create_import_job(
        db=db,
        user_id=current_user.userid,
        file=file.file,
        filename=safe_filename,
        gedcom_storage_root=GEDCOM_STORAGE_ROOT,
    )

    # Load stages for response
    result = await import_pipeline.get_job_with_stages(
        db, job.id, current_user.userid
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to retrieve created job',
        )

    job, stages = result
    return _job_to_response(job, stages)


@router.get('/import-jobs', response_model=ImportJobListResponse)
async def list_import_jobs(
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[str | None, Query()] = None,
) -> ImportJobListResponse:
    """List user's import jobs with pagination.

    Args:
        current_user: Authenticated user
        db: Database session
        limit: Maximum jobs to return (1-100)
        offset: Pagination offset
        status: Optional status filter (pending/running/paused/completed/failed)

    Returns:
        Paginated list of import jobs
    """
    jobs_with_stages, total = await import_pipeline.list_user_jobs(
        db=db,
        user_id=current_user.userid,
        limit=limit,
        offset=offset,
        status_filter=status,
    )

    return ImportJobListResponse(
        jobs=[
            _job_to_response(job, stages) for job, stages in jobs_with_stages
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get('/import-jobs/{job_id}', response_model=ImportJobResponse)
async def get_import_job(
    job_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ImportJobResponse:
    """Get import job status with stage details.

    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Import job with stages

    Raises:
        HTTPException: 404 if job not found or unauthorized
    """
    result = await import_pipeline.get_job_with_stages(
        db, job_id, current_user.userid
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Job not found',
        )

    job, stages = result
    return _job_to_response(job, stages)


@router.post('/import-jobs/{job_id}/pause', response_model=JobActionResponse)
async def pause_import_job(
    job_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobActionResponse:
    """Pause a running import job.

    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Job action response

    Raises:
        HTTPException: 404 if job not found or unauthorized
        HTTPException: 409 if job cannot be paused
    """
    result = await import_pipeline.get_job_with_stages(
        db, job_id, current_user.userid
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Job not found',
        )

    job, _ = result  # Stages not needed for pause

    try:
        await import_pipeline.pause_job(db, job_id, current_user.userid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    # Refresh to get updated status
    await db.refresh(job)

    return JobActionResponse(
        id=str(job.id),
        status=job.status.value,
        message='Job paused after current batch completes',
    )


@router.post('/import-jobs/{job_id}/resume', response_model=JobActionResponse)
async def resume_import_job(
    job_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobActionResponse:
    """Resume a paused import job.

    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Job action response

    Raises:
        HTTPException: 404 if job not found or unauthorized
        HTTPException: 409 if job cannot be resumed
    """
    result = await import_pipeline.get_job_with_stages(
        db, job_id, current_user.userid
    )

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Job not found',
        )

    job, _ = result  # Unpack tuple, stages not needed for resume

    try:
        await import_pipeline.resume_job(db, job_id, current_user.userid)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        ) from e

    # Refresh to get updated status
    await db.refresh(job)

    return JobActionResponse(
        id=str(job.id),
        status=job.status.value,
        message='Job queued for resumption',
    )


@router.delete('/import-jobs/{job_id}', response_model=JobActionResponse)
async def delete_import_job(
    job_id: UUID,
    current_user: CurrentUser,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JobActionResponse:
    """Cancel and delete an import job.

    Args:
        job_id: Job ID
        current_user: Authenticated user
        db: Database session

    Returns:
        Job action response

    Raises:
        HTTPException: 404 if job not found or unauthorized
    """
    job = await import_pipeline.cancel_job(
        db, job_id, current_user.userid, GEDCOM_STORAGE_ROOT
    )

    if job is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Job not found',
        )

    return JobActionResponse(
        id=str(job.id),
        status='cancelled',
        message='Job cancelled and files deleted',
    )
