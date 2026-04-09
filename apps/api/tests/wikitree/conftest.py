"""Shared fixtures for WikiTree tests."""

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from api.wikitree.session import WikiTreeSessionManager


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite database for testing."""
    # Create async engine with in-memory SQLite
    engine = create_async_engine(
        'sqlite+aiosqlite:///:memory:',
        echo=False,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    # Create session
    async with AsyncSession(engine) as session:
        yield session

    # Cleanup
    await engine.dispose()


@pytest_asyncio.fixture
async def session_manager(db_session):
    """Create WikiTree session manager with test database."""
    return WikiTreeSessionManager(db_session)
