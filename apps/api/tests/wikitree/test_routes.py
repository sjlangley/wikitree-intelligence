"""Tests for WikiTree connection routes."""

from collections.abc import AsyncGenerator
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from api.app import app
from api.database import WikiTreeConnection
from api.routes.wikitree import get_session_manager, get_wikitree_client
from api.wikitree import WikiTreeClient, WikiTreeSessionManager
from api.wikitree.client import WikiTreeAPIError


@pytest.fixture
def mock_wikitree_client():
    """Mock WikiTree client with default responses."""
    mock_client = Mock(spec=WikiTreeClient)
    mock_client.get_login_url = Mock(
        return_value='https://api.wikitree.com/api.php?action=clientLogin&returnURL=https://example.com/callback&appId=WikiTreeIntelligence'
    )
    mock_client.validate_authcode = AsyncMock()
    mock_client.check_login_status = AsyncMock()
    mock_client.get_profile = AsyncMock()
    return mock_client


@pytest.fixture
def mock_session_manager():
    """Mock WikiTree session manager with default responses."""
    mock_manager = Mock(spec=WikiTreeSessionManager)
    mock_manager.create_connection = AsyncMock()
    mock_manager.get_connection = AsyncMock(return_value=None)
    mock_manager.disconnect = AsyncMock()
    mock_manager.is_connected = Mock(return_value=False)  # Not async
    mock_manager.verify_and_update = AsyncMock()
    return mock_manager


@pytest.fixture
def override_wikitree_dependencies(mock_wikitree_client, mock_session_manager):
    """Override WikiTree dependencies for testing."""

    async def get_mock_client() -> AsyncGenerator[WikiTreeClient, None]:
        yield mock_wikitree_client

    def get_mock_session_manager() -> WikiTreeSessionManager:
        return mock_session_manager

    app.dependency_overrides[get_wikitree_client] = get_mock_client
    app.dependency_overrides[get_session_manager] = get_mock_session_manager

    yield

    app.dependency_overrides.pop(get_wikitree_client, None)
    app.dependency_overrides.pop(get_session_manager, None)


class TestWikiTreeRoutes:
    """Test WikiTree API routes."""

    @pytest.mark.asyncio
    async def test_initiate_connection(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
    ):
        """Test POST /api/wikitree/connect/initiate."""
        response = await authenticated_async_test_client.post(
            '/api/wikitree/connect/initiate',
            json={'return_url': '/wikitree/callback'},
        )

        assert response.status_code == 200
        data = response.json()
        assert 'login_url' in data
        assert 'https://api.wikitree.com/api.php' in data['login_url']
        assert 'action=clientLogin' in data['login_url']
        mock_wikitree_client.get_login_url.assert_called_once_with(
            '/wikitree/callback'
        )

    @pytest.mark.asyncio
    async def test_initiate_connection_absolute_url_rejected(
        self, authenticated_async_test_client, override_wikitree_dependencies
    ):
        """Test POST /api/wikitree/connect/initiate rejects absolute URLs."""
        response = await authenticated_async_test_client.post(
            '/api/wikitree/connect/initiate',
            json={'return_url': 'https://evil.com/callback'},
        )

        assert response.status_code == 400
        assert 'relative path' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_initiate_connection_missing_return_url(
        self, authenticated_async_test_client, override_wikitree_dependencies
    ):
        """Test POST /api/wikitree/connect/initiate with missing return_url."""
        response = await authenticated_async_test_client.post(
            '/api/wikitree/connect/initiate',
            json={'return_url': ''},
        )

        assert response.status_code == 400
        assert 'return_url is required' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_handle_callback_success(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test POST /api/wikitree/connect/callback with valid authcode."""
        # Configure mocks
        mock_wikitree_client.validate_authcode.return_value = {
            'user_id': 12345,
            'user_name': 'TestUser-1',
            'wikitree_id': 'TestUser-1',
        }

        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.wikitree_user_key = '12345'
        mock_connection.session_ref = 'TestUser-1'
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.connected_at = datetime.now(timezone.utc)
        mock_connection.expires_at = datetime.now(timezone.utc) + timedelta(
            days=30
        )
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.status = 'connected'
        mock_session_manager.create_connection.return_value = mock_connection

        response = await authenticated_async_test_client.post(
            '/api/wikitree/connect/callback',
            json={'authcode': 'test-authcode-123'},
        )

        assert response.status_code == 200
        data = response.json()
        assert data['is_connected'] is True
        assert data['wikitree_user_id'] == 12345
        assert data['wikitree_user_name'] == 'TestUser-1'
        assert data['connected_at'] is not None
        assert data['expires_at'] is not None

    @pytest.mark.asyncio
    async def test_handle_callback_invalid_authcode(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
    ):
        """Test POST /api/wikitree/connect/callback with invalid authcode."""
        mock_wikitree_client.validate_authcode.side_effect = WikiTreeAPIError(
            'Invalid authcode'
        )

        response = await authenticated_async_test_client.post(
            '/api/wikitree/connect/callback',
            json={'authcode': 'invalid-authcode'},
        )

        assert response.status_code == 400
        assert 'Invalid or expired authcode' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_handle_callback_missing_authcode(
        self, authenticated_async_test_client, override_wikitree_dependencies
    ):
        """Test POST /api/wikitree/connect/callback with missing authcode."""
        response = await authenticated_async_test_client.post(
            '/api/wikitree/connect/callback',
            json={'authcode': ''},
        )

        assert response.status_code == 400
        assert 'authcode is required' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_disconnect_success(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_session_manager,
    ):
        """Test POST /api/wikitree/disconnect with active connection."""
        # Mock an existing connection
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = (
            True  # Connection is active
        )

        response = await authenticated_async_test_client.post(
            '/api/wikitree/disconnect'
        )

        assert response.status_code == 204
        mock_session_manager.disconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_session_manager,
    ):
        """Test POST /api/wikitree/disconnect with no active connection."""
        # No connection exists
        mock_session_manager.get_connection.return_value = None

        response = await authenticated_async_test_client.post(
            '/api/wikitree/disconnect'
        )

        assert response.status_code == 404
        assert 'No active WikiTree connection' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_get_status_not_connected(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/status with no connection."""
        # No connection
        mock_session_manager.get_connection.return_value = None
        mock_session_manager.is_connected.return_value = False

        response = await authenticated_async_test_client.get(
            '/api/wikitree/status'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['is_connected'] is False
        assert data['wikitree_user_id'] is None
        assert data['wikitree_user_name'] is None

    @pytest.mark.asyncio
    async def test_get_status_connected(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/status with active connection."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.wikitree_user_key = '12345'
        mock_connection.session_ref = 'TestUser-1'
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.connected_at = datetime.now(timezone.utc)
        mock_connection.expires_at = datetime.now(timezone.utc) + timedelta(
            days=30
        )
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        response = await authenticated_async_test_client.get(
            '/api/wikitree/status'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['is_connected'] is True
        assert data['wikitree_user_id'] == 12345
        assert data['wikitree_user_name'] == 'TestUser-1'
        assert data['connected_at'] is not None
        assert data['expires_at'] is not None

    @pytest.mark.asyncio
    async def test_get_status_with_verify_valid(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/status?verify=true with valid session."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.wikitree_user_key = '12345'
        mock_connection.session_ref = 'TestUser-1'
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.connected_at = datetime.now(timezone.utc)
        mock_connection.expires_at = datetime.now(timezone.utc) + timedelta(
            days=30
        )
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        # WikiTree confirms user is still logged in
        mock_wikitree_client.check_login_status.return_value = True

        response = await authenticated_async_test_client.get(
            '/api/wikitree/status?verify=true'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['is_connected'] is True
        mock_wikitree_client.check_login_status.assert_called_once_with(12345)
        mock_session_manager.verify_and_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_status_with_verify_expired(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/status?verify=true with expired session."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.wikitree_user_key = '12345'
        mock_connection.session_ref = 'TestUser-1'
        mock_connection.connected_at = datetime.now(timezone.utc)
        mock_connection.expires_at = datetime.now(timezone.utc) + timedelta(
            days=30
        )
        mock_connection.last_verified_at = datetime.now(timezone.utc)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        # WikiTree says user is NOT logged in anymore
        mock_wikitree_client.check_login_status.return_value = False

        response = await authenticated_async_test_client.get(
            '/api/wikitree/status?verify=true'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['is_connected'] is False
        # After marking as expired, should have called mark_expired
        mock_wikitree_client.check_login_status.assert_called_once_with(12345)
        mock_session_manager.mark_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_profile_success(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/profile/{id} with active connection."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        # Mock profile data
        mock_wikitree_client.get_profile.return_value = {
            'Id': 12345,
            'Name': 'Doe',
            'FirstName': 'John',
            'BirthDate': '1900-01-01',
            'Privacy': 60,
        }

        response = await authenticated_async_test_client.get(
            '/api/wikitree/profile/Doe-1'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['wikitree_id'] == 'Doe-1'
        assert data['name'] == 'Doe'
        assert data['birth_date'] == '1900-01-01'
        assert data['privacy'] == 60
        assert data['data']['Id'] == 12345
        assert data['data']['FirstName'] == 'John'
        mock_wikitree_client.get_profile.assert_called_once_with(
            'Doe-1', fields=None
        )

    @pytest.mark.asyncio
    async def test_get_profile_with_fields(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/profile/{id} with specific fields."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        # Mock profile data
        mock_wikitree_client.get_profile.return_value = {
            'Id': 12345,
            'Name': 'Doe',
            'BirthDate': '1900-01-01',
        }

        response = await authenticated_async_test_client.get(
            '/api/wikitree/profile/Doe-1?fields=Id,Name,BirthDate'
        )

        assert response.status_code == 200
        data = response.json()
        assert data['wikitree_id'] == 'Doe-1'
        assert data['name'] == 'Doe'
        assert data['birth_date'] == '1900-01-01'
        assert data['data']['Id'] == 12345
        mock_wikitree_client.get_profile.assert_called_once_with(
            'Doe-1', fields=['Id', 'Name', 'BirthDate']
        )

    @pytest.mark.asyncio
    async def test_get_profile_no_connection(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/profile/{id} with no connection."""
        # No connection
        mock_session_manager.get_connection.return_value = None
        mock_session_manager.is_connected.return_value = False

        response = await authenticated_async_test_client.get(
            '/api/wikitree/profile/Doe-1'
        )

        assert response.status_code == 403
        assert 'WikiTree connection required' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_get_profile_not_found(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/profile/{id} for non-existent profile."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        # Mock profile not found error
        mock_wikitree_client.get_profile.side_effect = WikiTreeAPIError(
            'Profile retrieval failed: 1'
        )

        response = await authenticated_async_test_client.get(
            '/api/wikitree/profile/NonExistent-1'
        )

        assert response.status_code == 404
        assert 'Profile not found' in response.json()['detail']

    @pytest.mark.asyncio
    async def test_get_profile_api_error(
        self,
        authenticated_async_test_client,
        override_wikitree_dependencies,
        mock_wikitree_client,
        mock_session_manager,
    ):
        """Test GET /api/wikitree/profile/{id} with API error."""
        # Mock connected state
        mock_connection = Mock(spec=WikiTreeConnection)
        mock_connection.status = 'connected'

        mock_session_manager.get_connection.return_value = mock_connection
        mock_session_manager.is_connected.return_value = True

        # Mock generic API error
        mock_wikitree_client.get_profile.side_effect = WikiTreeAPIError(
            'Connection timeout'
        )

        response = await authenticated_async_test_client.get(
            '/api/wikitree/profile/Doe-1'
        )

        assert response.status_code == 500
        assert 'Failed to fetch WikiTree profile' in response.json()['detail']
