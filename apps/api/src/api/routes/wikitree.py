"""WikiTree connection API routes.

Endpoints for managing WikiTree authentication and profile access.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.user import User
from api.security.session_auth import get_current_user
from api.wikitree import WikiTreeClient, WikiTreeSessionManager
from api.wikitree.client import WikiTreeAPIError

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/wikitree', tags=['wikitree'])


# Helper Functions


def get_user_id(user: User) -> str:
    """Extract user ID from User model.

    Args:
        user: User model with userid string

    Returns:
        User ID as string (Google subject ID)
    """
    return user.userid


# Request/Response Models


class ConnectInitiateRequest(BaseModel):
    """Request to initiate WikiTree connection."""

    return_url: str = Field(
        ..., description='URL to redirect back to after login'
    )


class ConnectInitiateResponse(BaseModel):
    """Response with WikiTree login URL."""

    login_url: str = Field(
        ..., description='WikiTree login URL for browser redirect'
    )


class ConnectCallbackRequest(BaseModel):
    """WikiTree callback with authcode."""

    authcode: str = Field(..., description='Authorization code from WikiTree')


class WikiTreeConnectionStatus(BaseModel):
    """Current WikiTree connection status."""

    is_connected: bool = Field(
        ..., description='Whether user has active WikiTree connection'
    )
    wikitree_user_id: int | None = Field(
        None, description='WikiTree user ID if connected'
    )
    wikitree_user_name: str | None = Field(
        None, description='WikiTree user name if connected'
    )
    connected_at: str | None = Field(
        None, description='When connection was established'
    )
    expires_at: str | None = Field(
        None, description='When connection expires'
    )
    last_verified_at: str | None = Field(
        None, description='Last time connection was verified'
    )


class WikiTreeProfileResponse(BaseModel):
    """WikiTree profile data."""

    wikitree_id: str = Field(..., description='WikiTree person ID')
    name: str | None = Field(None, description='Full name')
    birth_date: str | None = Field(None, description='Birth date')
    death_date: str | None = Field(None, description='Death date')
    privacy: int | None = Field(
        None, description='Privacy level (60=public, 50=private)'
    )
    data: dict = Field(
        default_factory=dict, description='Full profile data from WikiTree'
    )


class ErrorResponse(BaseModel):
    """Error response."""

    detail: str = Field(..., description='Error message')


# Dependency Injection


async def get_wikitree_client() -> AsyncGenerator[WikiTreeClient, None]:
    """Get WikiTree API client."""
    client = WikiTreeClient()
    async with client:
        yield client


async def get_session_manager(
    db: Annotated[AsyncSession, Depends(get_db)]
) -> WikiTreeSessionManager:
    """Get WikiTree session manager."""
    return WikiTreeSessionManager(db)


# Routes


@router.post(
    '/connect/initiate',
    response_model=ConnectInitiateResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {'description': 'Login URL generated successfully'},
        401: {'description': 'Not authenticated', 'model': ErrorResponse},
        400: {'description': 'Invalid return URL', 'model': ErrorResponse},
    },
)
async def initiate_connection(
    request: ConnectInitiateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    client: Annotated[WikiTreeClient, Depends(get_wikitree_client)],
) -> ConnectInitiateResponse:
    """Initiate WikiTree connection flow.

    Returns a WikiTree login URL that the frontend should redirect to.
    After login, WikiTree will redirect back to the return_url with an authcode.
    """
    logger.info(
        'Initiating WikiTree connection',
        extra={'user_id': str(get_user_id(current_user))},
    )

    if not request.return_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='return_url is required',
        )

    login_url = client.get_login_url(request.return_url)

    logger.debug(
        'Generated WikiTree login URL',
        extra={'user_id': str(get_user_id(current_user))},
    )

    return ConnectInitiateResponse(login_url=login_url)


@router.post(
    '/connect/callback',
    response_model=WikiTreeConnectionStatus,
    status_code=status.HTTP_200_OK,
    responses={
        200: {'description': 'Connection established successfully'},
        401: {'description': 'Not authenticated', 'model': ErrorResponse},
        400: {
            'description': 'Invalid or expired authcode',
            'model': ErrorResponse,
        },
        500: {
            'description': 'Failed to validate authcode',
            'model': ErrorResponse,
        },
    },
)
async def handle_callback(
    request: ConnectCallbackRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    client: Annotated[WikiTreeClient, Depends(get_wikitree_client)],
    session_mgr: Annotated[
        WikiTreeSessionManager, Depends(get_session_manager)
    ],
) -> WikiTreeConnectionStatus:
    """Handle WikiTree callback with authcode.

    Validates the authcode with WikiTree and stores the connection
    in the database if successful.
    """
    logger.info(
        'Handling WikiTree callback', extra={'user_id': str(get_user_id(current_user))}
    )

    if not request.authcode:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='authcode is required',
        )

    try:
        # Validate authcode and get user info
        user_info = await client.validate_authcode(request.authcode)

        wikitree_user_id = user_info['user_id']
        wikitree_user_name = user_info['user_name']

        logger.info(
            'WikiTree authcode validated',
            extra={
                'user_id': str(get_user_id(current_user)),
                'wikitree_user_id': wikitree_user_id,
                'wikitree_user_name': wikitree_user_name,
            },
        )

        # Store connection in database
        connection = await session_mgr.create_connection(
            user_id=get_user_id(current_user),
            wikitree_user_id=wikitree_user_id,
            wikitree_user_name=wikitree_user_name,
        )

        logger.info(
            'WikiTree connection stored',
            extra={
                'user_id': str(get_user_id(current_user)),
                'connection_id': str(connection.id),
            },
        )

        return WikiTreeConnectionStatus(
            is_connected=True,
            wikitree_user_id=int(connection.wikitree_user_key) if connection.wikitree_user_key else None,
            wikitree_user_name=connection.session_ref,
            connected_at=(
                connection.connected_at.isoformat()
                if connection.connected_at
                else None
            ),
            expires_at=(
                connection.expires_at.isoformat()
                if connection.expires_at
                else None
            ),
            last_verified_at=(
                connection.last_verified_at.isoformat()
                if connection.last_verified_at
                else None
            ),
        )

    except (ValueError, WikiTreeAPIError) as e:
        logger.warning(
            'WikiTree authcode validation failed',
            extra={'user_id': str(get_user_id(current_user)), 'error': str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f'Invalid or expired authcode: {e}',
        ) from e
    except Exception as e:
        logger.error(
            'Failed to establish WikiTree connection',
            extra={'user_id': str(get_user_id(current_user))},
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to establish WikiTree connection',
        ) from e


@router.post(
    '/disconnect',
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        204: {'description': 'Disconnected successfully'},
        401: {'description': 'Not authenticated', 'model': ErrorResponse},
        404: {
            'description': 'No active connection found',
            'model': ErrorResponse,
        },
    },
)
async def disconnect(
    current_user: Annotated[User, Depends(get_current_user)],
    session_mgr: Annotated[
        WikiTreeSessionManager, Depends(get_session_manager)
    ],
    client: Annotated[WikiTreeClient, Depends(get_wikitree_client)],
) -> None:
    """Disconnect WikiTree connection.

    Marks the connection as disconnected in the database.
    The user's session cookies on WikiTree remain valid,
    but this app will no longer use them.
    """
    logger.info(
        'Disconnecting WikiTree', extra={'user_id': str(get_user_id(current_user))}
    )

    connection = await session_mgr.get_connection(get_user_id(current_user))

    if not connection or not session_mgr.is_connected(connection):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='No active WikiTree connection found',
        )

    await session_mgr.disconnect(get_user_id(current_user))

    logger.info(
        'WikiTree connection disconnected',
        extra={'user_id': str(get_user_id(current_user))},
    )


@router.get(
    '/status',
    response_model=WikiTreeConnectionStatus,
    status_code=status.HTTP_200_OK,
    responses={
        200: {'description': 'Connection status retrieved'},
        401: {'description': 'Not authenticated', 'model': ErrorResponse},
    },
)
async def get_connection_status(
    current_user: Annotated[User, Depends(get_current_user)],
    session_mgr: Annotated[
        WikiTreeSessionManager, Depends(get_session_manager)
    ],
    client: Annotated[WikiTreeClient, Depends(get_wikitree_client)],
    verify: Annotated[
        bool, Query(description='Verify connection with WikiTree')
    ] = False,
) -> WikiTreeConnectionStatus:
    """Get current WikiTree connection status.

    If verify=true, checks with WikiTree API to confirm session is still valid.
    """
    logger.debug(
        'Checking WikiTree connection status',
        extra={'user_id': str(get_user_id(current_user)), 'verify': verify},
    )

    connection = await session_mgr.get_connection(get_user_id(current_user))

    if not connection:
        return WikiTreeConnectionStatus(is_connected=False)

    is_connected = session_mgr.is_connected(connection)

    # Optionally verify with WikiTree API
    if verify and is_connected and connection.wikitree_user_key:
        try:
            # Convert wikitree_user_key to int for API call
            is_still_valid = await client.check_login_status(
                int(connection.wikitree_user_key)
            )
            if not is_still_valid:
                logger.info(
                    'WikiTree session expired',
                    extra={'user_id': str(get_user_id(current_user))},
                )
                await session_mgr.mark_expired(get_user_id(current_user))
                is_connected = False
            else:
                await session_mgr.verify_and_update(
                    get_user_id(current_user), is_valid=True
                )
        except Exception:
            logger.warning(
                'Failed to verify WikiTree session',
                extra={'user_id': str(get_user_id(current_user))},
                exc_info=True,
            )
            # Don't fail the request, just return cached status

    # Extract user_name from session_ref
    wikitree_user_name = connection.session_ref if connection.session_ref else None

    return WikiTreeConnectionStatus(
        is_connected=is_connected,
        wikitree_user_id=(
            connection.wikitree_user_key if is_connected else None
        ),
        wikitree_user_name=wikitree_user_name,
        connected_at=(
            connection.connected_at.isoformat()
            if connection.connected_at
            else None
        ),
        expires_at=(
            connection.expires_at.isoformat()
            if connection.expires_at
            else None
        ),
        last_verified_at=(
            connection.last_verified_at.isoformat()
            if connection.last_verified_at
            else None
        ),
    )


@router.get(
    '/profile/{wikitree_id}',
    response_model=WikiTreeProfileResponse,
    status_code=status.HTTP_200_OK,
    responses={
        200: {'description': 'Profile retrieved successfully'},
        401: {'description': 'Not authenticated', 'model': ErrorResponse},
        403: {
            'description': (
                'Not connected to WikiTree or no access to private '
                'profile'
            ),
            'model': ErrorResponse,
        },
        404: {'description': 'Profile not found', 'model': ErrorResponse},
        500: {
            'description': 'Failed to fetch profile',
            'model': ErrorResponse,
        },
    },
)
async def get_profile(
    wikitree_id: str,
    current_user: Annotated[User, Depends(get_current_user)],
    session_mgr: Annotated[
        WikiTreeSessionManager, Depends(get_session_manager)
    ],
    client: Annotated[WikiTreeClient, Depends(get_wikitree_client)],
    fields: Annotated[
        str | None,
        Query(description='Comma-separated WikiTree fields to retrieve'),
    ] = None,
) -> WikiTreeProfileResponse:
    """Get WikiTree profile for a person.

    Requires an active WikiTree connection to access private profiles.
    Public profiles can be accessed without connection, but private data
    requires the user to be logged in to WikiTree.
    """
    logger.info(
        'Fetching WikiTree profile',
        extra={'user_id': str(get_user_id(current_user)), 'wikitree_id': wikitree_id},
    )

    # Check if user has active WikiTree connection
    connection = await session_mgr.get_connection(get_user_id(current_user))
    is_connected = connection and session_mgr.is_connected(connection)

    if not is_connected:
        logger.warning(
            'No active WikiTree connection for profile request',
            extra={'user_id': str(get_user_id(current_user))},
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='WikiTree connection required to access profiles',
        )

    try:
        # Parse fields if provided
        field_list = (
            [f.strip() for f in fields.split(',')] if fields else None
        )

        # Fetch profile from WikiTree
        profile_data = await client.get_profile(wikitree_id, fields=field_list)

        logger.info(
            'WikiTree profile retrieved',
            extra={
                'user_id': str(get_user_id(current_user)),
                'wikitree_id': wikitree_id,
                'privacy': profile_data.get('Privacy'),
            },
        )

        return WikiTreeProfileResponse(
            wikitree_id=wikitree_id,
            name=profile_data.get('Name'),
            birth_date=profile_data.get('BirthDate'),
            death_date=profile_data.get('DeathDate'),
            privacy=profile_data.get('Privacy'),
            data=profile_data,
        )

    except WikiTreeAPIError as e:
        # Profile-specific errors (status != 0) are treated as not found
        if "Profile retrieval failed" in str(e):
            logger.warning(
                'WikiTree profile not found',
                extra={
                    'user_id': str(get_user_id(current_user)),
                    'wikitree_id': wikitree_id,
                    'error': str(e),
                },
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Profile not found: {e}',
            ) from e
        else:
            # Generic API errors (connection, HTTP, etc.) are server errors
            logger.error(
                'Failed to fetch WikiTree profile',
                extra={
                    'user_id': str(get_user_id(current_user)),
                    'wikitree_id': wikitree_id,
                },
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f'Failed to fetch WikiTree profile: {e}',
            ) from e
    except ValueError as e:
        logger.warning(
            'WikiTree profile not found',
            extra={
                'user_id': str(get_user_id(current_user)),
                'wikitree_id': wikitree_id,
                'error': str(e),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Profile not found: {e}',
        ) from e
    except Exception as e:
        logger.error(
            'Failed to fetch WikiTree profile',
            extra={
                'user_id': str(get_user_id(current_user)),
                'wikitree_id': wikitree_id,
            },
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Failed to fetch WikiTree profile',
        ) from e
