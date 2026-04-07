"""Tests for Google bearer token verification."""

from unittest.mock import patch

from fastapi import HTTPException
from google.auth import exceptions as google_exceptions
import pytest

from api.models.user import User
from api.security.google_bearer_token import (
    get_google_request,
    verify_bearer_token,
)


class TestGetGoogleRequest:
    """Test get_google_request function."""

    def test_returns_google_request_object(self):
        """Test that get_google_request returns a Request object."""
        request = get_google_request()
        assert request is not None

    def test_caches_request_object(self):
        """Test that get_google_request uses lru_cache."""
        req1 = get_google_request()
        req2 = get_google_request()
        # Should return same cached instance
        assert req1 is req2


class TestVerifyBearerToken:
    """Test verify_bearer_token function."""

    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_successful_verification(self, mock_verify):
        """Test successful token verification."""
        mock_payload = {
            'sub': 'user-123',
            'email': 'test@example.com',
            'name': 'Test User',
        }
        mock_verify.return_value = mock_payload

        user = verify_bearer_token('valid-token')

        assert isinstance(user, User)
        assert user.userid == 'user-123'
        assert user.email == 'test@example.com'
        assert user.name == 'Test User'

    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_minimal_payload(self, mock_verify):
        """Test verification with minimal required fields."""
        mock_payload = {
            'sub': 'user-456',
        }
        mock_verify.return_value = mock_payload

        user = verify_bearer_token('valid-token')

        assert user.userid == 'user-456'
        assert user.email is None
        assert user.name is None

    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_google_auth_error(self, mock_verify):
        """Test that GoogleAuthError raises 401."""
        mock_verify.side_effect = google_exceptions.GoogleAuthError(
            'Bad signature'
        )

        with pytest.raises(HTTPException) as exc_info:
            verify_bearer_token('invalid-token')

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == 'Authentication failed'

    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_value_error(self, mock_verify):
        """Test that ValueError raises 401."""
        mock_verify.side_effect = ValueError('Malformed token')

        with pytest.raises(HTTPException) as exc_info:
            verify_bearer_token('malformed-token')

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == 'Invalid token'

    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_missing_userid(self, mock_verify):
        """Test that missing userid raises 401."""
        mock_payload = {
            'email': 'test@example.com',
            'name': 'Test User',
        }
        mock_verify.return_value = mock_payload

        with pytest.raises(HTTPException) as exc_info:
            verify_bearer_token('token-without-sub')

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == 'Invalid token payload'

    @patch('api.security.google_bearer_token.settings')
    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_allowed_hosted_domain(self, mock_verify, mock_settings):
        """Test verification succeeds with allowed hosted domain."""
        mock_settings.client_id = 'test-client-id'
        mock_settings.allowed_hosted_domains = ['example.com', 'company.org']

        mock_payload = {
            'sub': 'user-789',
            'email': 'user@example.com',
            'hd': 'example.com',
        }
        mock_verify.return_value = mock_payload

        user = verify_bearer_token('valid-token')

        assert user.userid == 'user-789'
        assert user.email == 'user@example.com'

    @patch('api.security.google_bearer_token.settings')
    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_unauthorized_hosted_domain(self, mock_verify, mock_settings):
        """Test that unauthorized hosted domain raises 403."""
        mock_settings.client_id = 'test-client-id'
        mock_settings.allowed_hosted_domains = ['example.com']

        mock_payload = {
            'sub': 'user-999',
            'email': 'user@unauthorized.com',
            'hd': 'unauthorized.com',
        }
        mock_verify.return_value = mock_payload

        with pytest.raises(HTTPException) as exc_info:
            verify_bearer_token('token-from-wrong-domain')

        assert exc_info.value.status_code == 403
        assert exc_info.value.detail == 'Unauthorized hosted domain'

    @patch('api.security.google_bearer_token.settings')
    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_no_hosted_domain_with_allowed_list(
        self, mock_verify, mock_settings
    ):
        """Test that missing hd with allowed domains list raises 403."""
        mock_settings.client_id = 'test-client-id'
        mock_settings.allowed_hosted_domains = ['example.com']

        mock_payload = {
            'sub': 'user-000',
            'email': 'personal@gmail.com',
            # No 'hd' field - personal account
        }
        mock_verify.return_value = mock_payload

        with pytest.raises(HTTPException) as exc_info:
            verify_bearer_token('personal-account-token')

        assert exc_info.value.status_code == 403

    @patch('api.security.google_bearer_token.settings')
    @patch(
        'api.security.google_bearer_token.google_id_token.verify_oauth2_token'
    )
    def test_empty_allowed_domains_list(self, mock_verify, mock_settings):
        """Test that empty allowed_hosted_domains list allows all domains."""
        mock_settings.client_id = 'test-client-id'
        mock_settings.allowed_hosted_domains = []

        mock_payload = {
            'sub': 'user-111',
            'email': 'user@anydomain.com',
            'hd': 'anydomain.com',
        }
        mock_verify.return_value = mock_payload

        user = verify_bearer_token('valid-token')

        # Should succeed - empty list means no domain restrictions
        assert user.userid == 'user-111'
