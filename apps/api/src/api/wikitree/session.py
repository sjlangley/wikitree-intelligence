"""WikiTree session management and database integration."""

import logging
from datetime import datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import WikiTreeConnection

logger = logging.getLogger(__name__)

# WikiTree sessions typically expire after 30 days of inactivity
SESSION_EXPIRY_DAYS = 30


class WikiTreeSessionManager:
    """Manage WikiTree connection state in database."""

    def __init__(self, db_session: AsyncSession):
        """Initialize session manager.

        Args:
            db_session: SQLAlchemy async database session
        """
        self.db = db_session

    async def create_connection(
        self,
        user_id: UUID,
        wikitree_user_id: int,
        wikitree_user_name: str,
    ) -> WikiTreeConnection:
        """Create or update WikiTree connection for a user.

        Args:
            user_id: App user UUID
            wikitree_user_id: WikiTree user ID (integer)
            wikitree_user_name: WikiTree user name (WikiTree ID)

        Returns:
            WikiTreeConnection record
        """
        # Check if connection already exists
        stmt = select(WikiTreeConnection).where(
            WikiTreeConnection.user_id == user_id
        )
        result = await self.db.execute(stmt)
        connection = result.scalar_one_or_none()

        now = datetime.utcnow()
        expires_at = now + timedelta(days=SESSION_EXPIRY_DAYS)

        if connection:
            # Update existing connection
            connection.wikitree_user_key = str(wikitree_user_id)
            connection.status = "connected"
            connection.session_ref = wikitree_user_name
            connection.connected_at = now
            connection.expires_at = expires_at
            connection.last_verified_at = now
            logger.info(f"Updated WikiTree connection for user {user_id}")
        else:
            # Create new connection
            connection = WikiTreeConnection(
                user_id=user_id,
                wikitree_user_key=str(wikitree_user_id),
                status="connected",
                session_ref=wikitree_user_name,
                connected_at=now,
                expires_at=expires_at,
                last_verified_at=now,
            )
            self.db.add(connection)
            logger.info(f"Created WikiTree connection for user {user_id}")

        await self.db.commit()
        await self.db.refresh(connection)
        return connection

    async def get_connection(
        self, user_id: UUID
    ) -> WikiTreeConnection | None:
        """Get WikiTree connection for a user.

        Args:
            user_id: App user UUID

        Returns:
            WikiTreeConnection or None if not found
        """
        stmt = select(WikiTreeConnection).where(
            WikiTreeConnection.user_id == user_id
        )
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def disconnect(self, user_id: UUID) -> None:
        """Disconnect WikiTree connection for a user.

        Args:
            user_id: App user UUID
        """
        connection = await self.get_connection(user_id)
        if connection:
            connection.status = "disconnected"
            connection.session_ref = None
            await self.db.commit()
            logger.info(f"Disconnected WikiTree for user {user_id}")

    async def mark_expired(self, user_id: UUID) -> None:
        """Mark WikiTree connection as expired.

        Args:
            user_id: App user UUID
        """
        connection = await self.get_connection(user_id)
        if connection:
            connection.status = "expired"
            await self.db.commit()
            logger.info(f"Marked WikiTree connection expired for user {user_id}")

    async def verify_and_update(
        self, user_id: UUID, is_valid: bool
    ) -> None:
        """Update connection verification status.

        Args:
            user_id: App user UUID
            is_valid: Whether session is still valid
        """
        connection = await self.get_connection(user_id)
        if connection:
            connection.last_verified_at = datetime.utcnow()
            if not is_valid:
                connection.status = "expired"
            await self.db.commit()

    def is_connected(self, connection: WikiTreeConnection | None) -> bool:
        """Check if a connection is currently active.

        Args:
            connection: WikiTreeConnection or None

        Returns:
            True if connected and not expired
        """
        if not connection:
            return False

        if connection.status != "connected":
            return False

        # Check expiration
        if connection.expires_at and connection.expires_at < datetime.utcnow():
            return False

        return True
