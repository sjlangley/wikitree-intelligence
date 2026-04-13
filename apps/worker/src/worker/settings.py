"""This module defines the configuration settings for the application.

It uses Pydantic's BaseSettings to load environment variables from a `.env`
file.
"""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from worker.enums import Environment


class Settings(BaseSettings):
    """The application settings."""

    model_config = SettingsConfigDict(env_file='.env')

    log_level: str = Field(default='INFO', alias='LOG_LEVEL')

    # Environment setting (e.g., 'development', 'production')
    environment: Environment = Field(
        default=Environment.PRODUCTION, alias='ENVIRONMENT'
    )

    database_url: str | None = Field(default=None, alias='DATABASE_URL')
    database_name: str = Field(
        default='conversations',
        description='The database name for storing conversations.',
        alias='DATABASE_NAME',
    )
    database_user: str = Field(
        default='nobody',
        description='Database username for storing conversations.',
        alias='DATABASE_USER',
    )
    database_password: str = Field(
        default='',
        description='Database password for storing conversations.',
        alias='DATABASE_PASSWORD',
    )
    database_host: str = Field(default='localhost', alias='DATABASE_HOST')
    database_port: int = Field(default=5432, alias='DATABASE_PORT')


settings = Settings()  # pyrefly: ignore[missing-argument]
