"""Tests for WikiTree session manager."""

from datetime import datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from api.database import WikiTreeConnection
from api.wikitree.session import (
    SESSION_EXPIRY_DAYS,
    WikiTreeSessionManager,
)


@pytest_asyncio.fixture
async def db_session():
    """Create an in-memory SQLite database for testing."""
    # Create async engine with in-memory SQLite
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
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


class TestWikiTreeSessionManager:
    """Test WikiTree session manager."""

    @pytest.mark.asyncio
    async def test_create_connection_new(self, session_manager):
        """Test creating a new WikiTree connection."""
        user_id = uuid4()
        wikitree_user_id = 12345
        wikitree_user_name = "TestUser-1"

        connection = await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=wikitree_user_id,
            wikitree_user_name=wikitree_user_name,
        )

        assert connection.user_id == user_id
        assert connection.wikitree_user_key == str(wikitree_user_id)
        assert connection.status == "connected"
        assert connection.connected_at is not None
        assert connection.expires_at is not None

        # Check expiry is ~30 days in future
        time_until_expiry = connection.expires_at - datetime.utcnow()
        assert 29 <= time_until_expiry.days <= 30

    @pytest.mark.asyncio
    async def test_create_connection_update_existing(self, session_manager):
        """Test updating an existing WikiTree connection."""
        user_id = uuid4()

        # Create initial connection
        connection1 = await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Update with new WikiTree user
        connection2 = await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=67890,
            wikitree_user_name="TestUser-2",
        )

        # Should be same connection record
        assert connection1.id == connection2.id
        assert connection2.wikitree_user_key == "67890"
        assert connection2.status == "connected"

    @pytest.mark.asyncio
    async def test_get_connection_exists(self, session_manager):
        """Test getting an existing connection."""
        user_id = uuid4()

        # Create connection
        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Retrieve connection
        connection = await session_manager.get_connection(user_id)

        assert connection is not None
        assert connection.user_id == user_id
        assert connection.wikitree_user_key == "12345"

    @pytest.mark.asyncio
    async def test_get_connection_not_exists(self, session_manager):
        """Test getting a non-existent connection."""
        user_id = uuid4()

        connection = await session_manager.get_connection(user_id)

        assert connection is None

    @pytest.mark.asyncio
    async def test_disconnect(self, session_manager):
        """Test disconnecting a WikiTree connection."""
        user_id = uuid4()

        # Create connection
        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Disconnect
        await session_manager.disconnect(user_id)

        # Verify status changed
        connection = await session_manager.get_connection(user_id)
        assert connection.status == "disconnected"
        assert connection.session_ref is None

    @pytest.mark.asyncio
    async def test_disconnect_nonexistent(self, session_manager):
        """Test disconnecting a non-existent connection (should be no-op)."""
        user_id = uuid4()

        # Should not raise error
        await session_manager.disconnect(user_id)

    @pytest.mark.asyncio
    async def test_mark_expired(self, session_manager):
        """Test marking a connection as expired."""
        user_id = uuid4()

        # Create connection
        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Mark expired
        await session_manager.mark_expired(user_id)

        # Verify status changed
        connection = await session_manager.get_connection(user_id)
        assert connection.status == "expired"

    @pytest.mark.asyncio
    async def test_mark_expired_nonexistent(self, session_manager):
        """Test marking a non-existent connection as expired (should be no-op)."""
        user_id = uuid4()

        # Should not raise error
        await session_manager.mark_expired(user_id)

    @pytest.mark.asyncio
    async def test_verify_and_update_valid(self, session_manager):
        """Test verifying and updating a valid connection."""
        user_id = uuid4()

        # Create connection
        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Verify
        await session_manager.verify_and_update(user_id, is_valid=True)

        # Check last_verified_at updated
        connection = await session_manager.get_connection(user_id)
        assert connection.last_verified_at is not None

    @pytest.mark.asyncio
    async def test_verify_and_update_invalid(self, session_manager):
        """Test verifying an invalid (expired) connection."""
        user_id = uuid4()

        # Create connection
        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Mark as invalid
        await session_manager.verify_and_update(user_id, is_valid=False)

        # Should be marked expired
        connection = await session_manager.get_connection(user_id)
        assert connection.status == "expired"

    @pytest.mark.asyncio
    async def test_is_connected_active(self, session_manager):
        """Test is_connected for an active connection."""
        user_id = uuid4()

        connection = await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        assert session_manager.is_connected(connection) is True

    @pytest.mark.asyncio
    async def test_is_connected_disconnected(self, session_manager):
        """Test is_connected for a disconnected connection."""
        user_id = uuid4()

        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        await session_manager.disconnect(user_id)

        connection = await session_manager.get_connection(user_id)
        assert session_manager.is_connected(connection) is False

    @pytest.mark.asyncio
    async def test_is_connected_expired(self, session_manager):
        """Test is_connected for an expired connection."""
        user_id = uuid4()

        await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        await session_manager.mark_expired(user_id)

        connection = await session_manager.get_connection(user_id)
        assert session_manager.is_connected(connection) is False

    @pytest.mark.asyncio
    async def test_is_connected_past_expiry(
        self, session_manager, db_session
    ):
        """Test is_connected for a connection past expiry date."""
        user_id = uuid4()

        connection = await session_manager.create_connection(
            user_id=user_id,
            wikitree_user_id=12345,
            wikitree_user_name="TestUser-1",
        )

        # Manually set expires_at to past
        connection.expires_at = datetime.utcnow() - timedelta(days=1)
        db_session.add(connection)
        await db_session.commit()
        await db_session.refresh(connection)

        assert session_manager.is_connected(connection) is False

    @pytest.mark.asyncio
    async def test_is_connected_none(self, session_manager):
        """Test is_connected with None connection."""
        assert session_manager.is_connected(None) is False

    @pytest.mark.asyncio
    async def test_session_expiry_constant(self):
        """Test session expiry constant is reasonable."""
        assert SESSION_EXPIRY_DAYS == 30
        assert isinstance(SESSION_EXPIRY_DAYS, int)
