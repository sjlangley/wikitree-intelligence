"""Shared pytest fixtures for API tests."""

from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
import pytest
import pytest_asyncio

from api.app import app


@pytest_asyncio.fixture()
async def async_test_client() -> AsyncClient:
    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app), base_url='http://test'
        ) as client:
            yield client
