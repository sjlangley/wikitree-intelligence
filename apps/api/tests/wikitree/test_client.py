"""Tests for WikiTree API client."""

from unittest.mock import Mock, patch

import httpx
import pytest

from api.wikitree.client import WikiTreeAPIError, WikiTreeClient


class TestWikiTreeClient:
    """Test WikiTree API client."""

    @pytest.mark.asyncio
    async def test_get_login_url(self):
        """Test login URL generation."""
        client = WikiTreeClient(app_id='TestApp')
        return_url = 'https://example.com/callback'

        login_url = client.get_login_url(return_url)

        assert 'https://api.wikitree.com/api.php' in login_url
        assert 'action=clientLogin' in login_url
        assert 'returnURL=https%3A%2F%2Fexample.com%2Fcallback' in login_url
        assert 'appId=TestApp' in login_url

    @pytest.mark.asyncio
    async def test_get_logout_url(self):
        """Test logout URL generation."""
        client = WikiTreeClient(app_id='TestApp')
        return_url = 'https://example.com/logout'

        logout_url = client.get_logout_url(return_url)

        assert 'https://api.wikitree.com/api.php' in logout_url
        assert 'action=clientLogin' in logout_url
        assert 'doLogout=1' in logout_url
        assert 'returnURL=https%3A%2F%2Fexample.com%2Flogout' in logout_url
        assert 'appId=TestApp' in logout_url

    @pytest.mark.asyncio
    async def test_validate_authcode_success(self):
        """Test successful authcode validation."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                'clientLogin': {
                    'result': 'Success',
                    'userid': 12345,
                    'username': 'TestUser-1',
                }
            }
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                result = await client.validate_authcode('test-authcode-123')

                assert result['user_id'] == '12345'
                assert result['user_name'] == 'TestUser-1'
                assert result['wikitree_id'] == 'TestUser-1'

    @pytest.mark.asyncio
    async def test_validate_authcode_failure(self):
        """Test authcode validation failure."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={
                'clientLogin': {'result': 'Fail', 'error': 'Invalid authcode'}
            }
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                with pytest.raises(
                    WikiTreeAPIError, match='Authcode validation failed'
                ):
                    await client.validate_authcode('invalid-authcode')

    @pytest.mark.asyncio
    async def test_validate_authcode_http_error(self):
        """Test authcode validation with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPError('Connection failed')
        )

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                with pytest.raises(WikiTreeAPIError, match='HTTP error'):
                    await client.validate_authcode('test-authcode')

    @pytest.mark.asyncio
    async def test_check_login_status_logged_in(self):
        """Test check login status when user is logged in."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={'clientLogin': {'result': 'Ok', 'userid': 12345}}
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                is_logged_in = await client.check_login_status(12345)

                assert is_logged_in is True

    @pytest.mark.asyncio
    async def test_check_login_status_not_logged_in(self):
        """Test check login status when user is not logged in."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value={'clientLogin': {'result': 'Fail'}}
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                is_logged_in = await client.check_login_status(12345)

                assert is_logged_in is False

    @pytest.mark.asyncio
    async def test_get_profile_success(self):
        """Test successful profile retrieval."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value=[
                {
                    'status': 0,
                    'Id': 12345,
                    'Name': 'Doe',
                    'FirstName': 'John',
                    'BirthDate': '1900-01-01',
                    'DeathDate': '1980-12-31',
                    'Privacy': 60,
                }
            ]
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                profile = await client.get_profile('Doe-1')

                assert profile['Id'] == 12345
                assert profile['Name'] == 'Doe'
                assert profile['FirstName'] == 'John'
                assert profile['Privacy'] == 60

    @pytest.mark.asyncio
    async def test_get_profile_with_fields(self):
        """Test profile retrieval with specific fields."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value=[
                {
                    'status': 0,
                    'Id': 12345,
                    'Name': 'Doe',
                    'BirthDate': '1900-01-01',
                }
            ]
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                profile = await client.get_profile(
                    'Doe-1', fields=['Id', 'Name', 'BirthDate']
                )

                assert profile['Id'] == 12345
                assert profile['Name'] == 'Doe'
                assert profile['BirthDate'] == '1900-01-01'

    @pytest.mark.asyncio
    async def test_get_profile_not_found(self):
        """Test profile retrieval for non-existent profile."""
        mock_response = Mock()
        mock_response.json = Mock(
            return_value=[{'status': 1, 'error': 'Profile not found'}]
        )
        mock_response.raise_for_status = Mock()

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                with pytest.raises(
                    WikiTreeAPIError, match='Profile retrieval failed'
                ):
                    await client.get_profile('NonExistent-1')

    @pytest.mark.asyncio
    async def test_get_profile_http_error(self):
        """Test profile retrieval with HTTP error."""
        mock_response = Mock()
        mock_response.raise_for_status = Mock(
            side_effect=httpx.HTTPError('Connection failed')
        )

        async with WikiTreeClient() as client:
            with patch.object(
                client._client, 'post', return_value=mock_response
            ):
                with pytest.raises(WikiTreeAPIError, match='HTTP error'):
                    await client.get_profile('Doe-1')

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test async context manager opens and closes client."""
        client = WikiTreeClient()

        assert client._client is None

        async with client:
            assert client._client is not None
            assert isinstance(client._client, httpx.AsyncClient)

        # Client should be closed after context exit
        # (we can't directly check if closed, but _client remains set)

    @pytest.mark.asyncio
    async def test_client_not_initialized_error(self):
        """Test error when client methods called without context manager."""
        client = WikiTreeClient()

        with pytest.raises(RuntimeError, match='Client not initialized'):
            await client.validate_authcode('test-code')

        with pytest.raises(RuntimeError, match='Client not initialized'):
            await client.check_login_status(12345)

        with pytest.raises(RuntimeError, match='Client not initialized'):
            await client.get_profile('Doe-1')
