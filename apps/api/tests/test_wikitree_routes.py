"""Tests for WikiTree connection routes."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from api.wikitree.client import WikiTreeAPIError


class TestWikiTreeRoutes:
    """Test WikiTree API routes."""

    @pytest.mark.asyncio
    async def test_initiate_connection(self, authenticated_async_test_client):
        """Test POST /api/wikitree/connect/initiate."""
        response = await authenticated_async_test_client.post(
            "/api/wikitree/connect/initiate",
            json={"return_url": "https://example.com/callback"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "login_url" in data
        assert "https://api.wikitree.com/api.php" in data["login_url"]
        assert "action=clientLogin" in data["login_url"]

    @pytest.mark.asyncio
    async def test_initiate_connection_missing_return_url(
        self, authenticated_async_test_client
    ):
        """Test POST /api/wikitree/connect/initiate with missing return_url."""
        response = await authenticated_async_test_client.post(
            "/api/wikitree/connect/initiate",
            json={"return_url": ""},
        )

        assert response.status_code == 400
        assert "return_url is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_handle_callback_success(
        self, authenticated_async_test_client
    ):
        """Test POST /api/wikitree/connect/callback with valid authcode."""
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            response = await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode-123"},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is True
        assert data["wikitree_user_id"] == 12345
        assert data["wikitree_user_name"] == "TestUser-1"
        assert data["connected_at"] is not None
        assert data["expires_at"] is not None

    @pytest.mark.asyncio
    async def test_handle_callback_invalid_authcode(
        self, authenticated_async_test_client
    ):
        """Test POST /api/wikitree/connect/callback with invalid authcode."""
        mock_validate = AsyncMock(
            side_effect=ValueError("Invalid authcode")
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            response = await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "invalid-authcode"},
            )

        assert response.status_code == 400
        assert "Invalid or expired authcode" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_handle_callback_missing_authcode(
        self, authenticated_async_test_client
    ):
        """Test POST /api/wikitree/connect/callback with missing authcode."""
        response = await authenticated_async_test_client.post(
            "/api/wikitree/connect/callback",
            json={"authcode": ""},
        )

        assert response.status_code == 400
        assert "authcode is required" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_disconnect_success(self, authenticated_async_test_client):
        """Test POST /api/wikitree/disconnect with active connection."""
        # First create a connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Now disconnect
        response = await authenticated_async_test_client.post(
            "/api/wikitree/disconnect"
        )

        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_disconnect_no_connection(
        self, authenticated_async_test_client
    ):
        """Test POST /api/wikitree/disconnect with no active connection."""
        response = await authenticated_async_test_client.post(
            "/api/wikitree/disconnect"
        )

        assert response.status_code == 404
        assert (
            "No active WikiTree connection" in response.json()["detail"]
        )

    @pytest.mark.asyncio
    async def test_get_status_not_connected(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/status with no connection."""
        response = await authenticated_async_test_client.get(
            "/api/wikitree/status"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is False
        assert data["wikitree_user_id"] is None

    @pytest.mark.asyncio
    async def test_get_status_connected(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/status with active connection."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Check status
        response = await authenticated_async_test_client.get(
            "/api/wikitree/status"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is True
        assert data["wikitree_user_id"] == 12345

    @pytest.mark.asyncio
    async def test_get_status_with_verify_valid(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/status with verify=true and valid session."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Check status with verification
        mock_check_login = AsyncMock(return_value=True)

        with patch(
            "api.routes.wikitree.WikiTreeClient.check_login_status",
            mock_check_login,
        ):
            response = await authenticated_async_test_client.get(
                "/api/wikitree/status?verify=true"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is True
        assert data["last_verified_at"] is not None

    @pytest.mark.asyncio
    async def test_get_status_with_verify_expired(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/status with verify=true and expired session."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Check status with verification - session expired
        mock_check_login = AsyncMock(return_value=False)

        with patch(
            "api.routes.wikitree.WikiTreeClient.check_login_status",
            mock_check_login,
        ):
            response = await authenticated_async_test_client.get(
                "/api/wikitree/status?verify=true"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["is_connected"] is False

    @pytest.mark.asyncio
    async def test_get_profile_success(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/profile/{wikitree_id} with active connection."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Get profile
        mock_get_profile = AsyncMock(
            return_value={
                "Id": 67890,
                "Name": "Doe",
                "FirstName": "John",
                "BirthDate": "1900-01-01",
                "DeathDate": "1980-12-31",
                "Privacy": 60,
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.get_profile",
            mock_get_profile,
        ):
            response = await authenticated_async_test_client.get(
                "/api/wikitree/profile/Doe-1"
            )

        assert response.status_code == 200
        data = response.json()
        assert data["wikitree_id"] == "Doe-1"
        assert data["name"] == "Doe"
        assert data["birth_date"] == "1900-01-01"
        assert data["death_date"] == "1980-12-31"
        assert data["privacy"] == 60

    @pytest.mark.asyncio
    async def test_get_profile_with_fields(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/profile with specific fields."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Get profile with fields
        mock_get_profile = AsyncMock(
            return_value={"Id": 67890, "Name": "Doe", "BirthDate": "1900-01-01"}
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.get_profile",
            mock_get_profile,
        ):
            response = await authenticated_async_test_client.get(
                "/api/wikitree/profile/Doe-1?fields=Id,Name,BirthDate"
            )

        assert response.status_code == 200
        # Verify fields parameter was passed
        mock_get_profile.assert_called_once()
        call_args = mock_get_profile.call_args
        assert call_args[1]["fields"] == ["Id", "Name", "BirthDate"]

    @pytest.mark.asyncio
    async def test_get_profile_no_connection(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/profile without active connection."""
        response = await authenticated_async_test_client.get(
            "/api/wikitree/profile/Doe-1"
        )

        assert response.status_code == 403
        assert (
            "WikiTree connection required" in response.json()["detail"]
        )

    @pytest.mark.asyncio
    async def test_get_profile_not_found(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/profile for non-existent profile."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Get profile - not found
        mock_get_profile = AsyncMock(
            side_effect=ValueError("Profile not found")
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.get_profile",
            mock_get_profile,
        ):
            response = await authenticated_async_test_client.get(
                "/api/wikitree/profile/NonExistent-1"
            )

        assert response.status_code == 404
        assert "Profile not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_profile_api_error(
        self, authenticated_async_test_client
    ):
        """Test GET /api/wikitree/profile with API error."""
        # Create connection
        mock_validate = AsyncMock(
            return_value={
                "user_id": 12345,
                "user_name": "TestUser-1",
                "wikitree_id": "TestUser-1",
            }
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.validate_authcode",
            mock_validate,
        ):
            await authenticated_async_test_client.post(
                "/api/wikitree/connect/callback",
                json={"authcode": "test-authcode"},
            )

        # Get profile - API error
        mock_get_profile = AsyncMock(
            side_effect=WikiTreeAPIError("API request failed")
        )

        with patch(
            "api.routes.wikitree.WikiTreeClient.get_profile",
            mock_get_profile,
        ):
            response = await authenticated_async_test_client.get(
                "/api/wikitree/profile/Doe-1"
            )

        assert response.status_code == 500
        assert (
            "Failed to fetch WikiTree profile" in response.json()["detail"]
        )
