"""Shared pytest fixtures for API tests."""

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from api.app import app
from api.models.user import User
from api.security.security import get_current_google_user

TEST_USER_EMAIL = 'test_user@test.org'
TEST_USER_ID = 'test-oid-123'
TEST_USER_NAME = 'Test User'


@pytest.fixture
def test_user():
    """Create a test user for the session."""
    return User(email=TEST_USER_EMAIL, userid=TEST_USER_ID, name=TEST_USER_NAME)


@pytest_asyncio.fixture()
async def async_test_client() -> AsyncClient:
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app), base_url='http://test'
        ) as client:
            yield client


@pytest.fixture
def override_google_bearer_token_dependency(test_user):
    # Override the get_current_google_user dependency for the test and inject
    # the test_user instance as the authenticated user.
    def override_get_current_user() -> User:
        return test_user

    # Apply the override
    app.dependency_overrides[get_current_google_user] = (
        override_get_current_user
    )

    # Ensure that the override is cleaned up after the test
    yield

    # Clean up the specific override after the test is done
    app.dependency_overrides.pop(get_current_google_user, None)


@pytest_asyncio.fixture()
async def authenticated_async_test_client(
    async_test_client,
    override_google_bearer_token_dependency,
):
    response = await async_test_client.post('/auth/login')
    assert response.status_code == 200

    # the AsyncClient cookie jar now contains the session cookie
    yield async_test_client
