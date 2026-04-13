"""REST API handler for health checking."""

from fastapi import APIRouter, status
from worker.models.health import HealthCheck
from worker.settings import settings

router = APIRouter()


@router.get(
    '/live',
    response_description='Kubernetes liveness probe',
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
    include_in_schema=False,
)
async def liveness() -> HealthCheck:
    """Kubernetes liveness probe - is process running?

    Returns HTTP 200 if the process is alive and can serve requests.
    Never returns error - if it can respond, it's alive.
    """
    return HealthCheck(status='alive', worker_id=settings.worker_id)


@router.get(
    '/ready',
    response_description='Kubernetes readiness probe',
    status_code=status.HTTP_200_OK,
    response_model=HealthCheck,
    include_in_schema=False,
)
async def readiness() -> HealthCheck:
    """Kubernetes readiness probe - can it process jobs?

    Returns HTTP 200 if the worker is ready to claim jobs.

    TODO: When database is implemented, check:
    - Database connection is healthy
    - Can execute SELECT 1
    - Connection pool has available connections

    If any check fails, return HTTP 503 Service Unavailable.
    """
    # For now, always ready (no DB dependency yet)
    return HealthCheck(status='ready', worker_id=settings.worker_id)
