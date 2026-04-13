"""Tests for health check endpoints."""

import pytest


@pytest.mark.asyncio
async def test_liveness_endpoint(async_test_client):
    """Test liveness probe returns 200 with alive status."""
    response = await async_test_client.get('/health/live')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'alive'
    assert 'worker_id' in data
    assert data['worker_id'].startswith('worker-')


@pytest.mark.asyncio
async def test_readiness_endpoint(async_test_client):
    """Test readiness probe returns 200 with ready status.

    Note: Once database is implemented, this should also test:
    - Returns 503 when DB connection fails
    - Returns 200 when DB connection is healthy
    """
    response = await async_test_client.get('/health/ready')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'ready'
    assert 'worker_id' in data
    assert data['worker_id'].startswith('worker-')
