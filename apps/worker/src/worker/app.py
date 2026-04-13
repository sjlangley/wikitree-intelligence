"""Entrypoint for the API application."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from worker.logging import setup_logging
from worker.routes import health
from worker.settings import Settings, settings

logger = logging.getLogger(__name__)


def _get_safe_settings_for_logging(settings_to_log: Settings) -> dict:
    """Get settings with sensitive values redacted for logging.

    Args:
        settings_to_log: The application settings.


    Returns:
        Dictionary of settings with sensitive values masked.
    """
    # Fields that should never be logged
    sensitive_fields = {
        'database_password',
        'database_url',
    }

    data = settings_to_log.model_dump()
    safe_data = {}

    for key, value in data.items():
        if key in sensitive_fields:
            safe_data[key] = '***REDACTED***'
        else:
            safe_data[key] = value

    return safe_data


def _log_startup_settings(settings_to_log: Settings) -> None:
    """Log application settings at startup for debugging.

    Args:
        settings_to_log: The application settings to log.
    """
    safe_settings = _get_safe_settings_for_logging(settings_to_log)
    logger.info(
        'Application startup configuration: %s',
        safe_settings,
    )


@asynccontextmanager
async def lifespan(application: FastAPI):
    setup_logging()
    _log_startup_settings(settings)

    yield


app = FastAPI(lifespan=lifespan)

app.include_router(health.router, prefix='/health')
