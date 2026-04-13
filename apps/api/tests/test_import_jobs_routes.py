"""Tests for import jobs REST API endpoints.

Tests all HTTP endpoints:
- POST /api/import-jobs
- GET /api/import-jobs
- GET /api/import-jobs/{id}
- POST /api/import-jobs/{id}/pause
- POST /api/import-jobs/{id}/resume
- DELETE /api/import-jobs/{id}
"""

import io
from pathlib import Path
import tempfile
from uuid import UUID, uuid4

from httpx import AsyncClient
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlmodel import SQLModel

from api.app import app
from api.database import ImportJob, ImportJobStage, get_db
from api.models.user import User
from api.security.session_auth import get_current_user
from api.state_machines import ImportJobStageStatus, ImportJobStatus

TEST_USER_EMAIL = 'test@example.com'
TEST_USER_ID = 'test-user-123'
TEST_USER_NAME = 'Test User'


@pytest.fixture
def test_user():
    """Create test user."""
    return User(email=TEST_USER_EMAIL, userid=TEST_USER_ID, name=TEST_USER_NAME)


@pytest_asyncio.fixture
async def test_db():
    """Create test database with clean schema."""
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with AsyncSession(engine) as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def async_test_client(test_db, test_user):
    """Create async test client with auth override."""

    async def override_get_db():
        yield test_db

    def override_get_current_user():
        return test_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    from asgi_lifespan import LifespanManager
    from httpx import ASGITransport

    async with LifespanManager(app):
        async with AsyncClient(
            transport=ASGITransport(app), base_url='http://test'
        ) as client:
            yield client

    app.dependency_overrides.clear()


@pytest.fixture
def temp_gedcom_storage():
    """Create temporary GEDCOM storage directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_gedcom_file():
    """Create sample GEDCOM file content."""
    content = b"""0 HEAD
1 SOUR Test
1 GEDC
2 VERS 5.5.1
1 CHAR UTF-8
0 @I1@ INDI
1 NAME John /Doe/
1 SEX M
1 BIRT
2 DATE 1 JAN 1900
2 PLAC New York, NY
0 TRLR
"""
    return io.BytesIO(content)


# ============================================================================
# POST /api/import-jobs
# ============================================================================


@pytest.mark.asyncio
async def test_create_import_job_success(
    async_test_client,
    sample_gedcom_file,
    temp_gedcom_storage,
    test_user,
    monkeypatch,
):
    """Test successful GEDCOM upload."""
    monkeypatch.setattr(
        'api.routes.import_jobs.GEDCOM_STORAGE_ROOT', temp_gedcom_storage
    )

    files = {
        'file': ('test.ged', sample_gedcom_file, 'application/octet-stream')
    }
    response = await async_test_client.post('/api/import-jobs', files=files)

    assert response.status_code == 201
    data = response.json()
    assert data['status'] == 'queued'  # Job is queued after successful upload
    assert data['original_filename'] == 'test.ged'
    assert data['user_id'] == TEST_USER_ID
    assert len(data['stages']) == 6
    assert data['stages'][0]['name'] == 'validate'

    # Verify file was stored
    job_id = UUID(data['id'])
    file_path = (
        temp_gedcom_storage / TEST_USER_ID / str(job_id) / 'original.ged'
    )
    assert file_path.exists()


@pytest.mark.asyncio
async def test_create_import_job_no_file(async_test_client):
    """Test upload without file."""
    response = await async_test_client.post('/api/import-jobs', files={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_import_job_wrong_extension(async_test_client):
    """Test upload with non-.ged file."""
    files = {'file': ('test.txt', io.BytesIO(b'content'), 'text/plain')}
    response = await async_test_client.post('/api/import-jobs', files=files)

    assert response.status_code == 422
    assert 'must be a .ged GEDCOM file' in response.json()['detail']


@pytest.mark.asyncio
async def test_create_import_job_file_too_large(async_test_client):
    """Test upload exceeding size limit."""
    # Create 101MB file
    large_file = io.BytesIO(b'0' * (101 * 1024 * 1024))
    files = {'file': ('large.ged', large_file, 'application/octet-stream')}

    response = await async_test_client.post('/api/import-jobs', files=files)

    assert response.status_code == 413
    assert '100MB limit' in response.json()['detail']


# ============================================================================
# GET /api/import-jobs
# ============================================================================


@pytest.mark.asyncio
async def test_list_import_jobs_empty(async_test_client):
    """Test listing jobs when none exist."""
    response = await async_test_client.get('/api/import-jobs')

    assert response.status_code == 200
    data = response.json()
    assert data['jobs'] == []
    assert data['total'] == 0
    assert data['limit'] == 20
    assert data['offset'] == 0


@pytest.mark.asyncio
async def test_list_import_jobs_with_data(
    async_test_client, test_db, test_user
):
    """Test listing jobs with existing data."""
    # Create test jobs
    for i in range(3):
        job = ImportJob(
            user_id=test_user.userid,
            source_type='gedcom',
            original_filename=f'test{i}.ged',
            stored_path=f'{test_user.userid}/job{i}/original.ged',
            file_size_bytes=1000,
            content_sha256='abc123',
            status=ImportJobStatus.UPLOADED,
        )
        test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    await test_db.commit()

    response = await async_test_client.get('/api/import-jobs')

    assert response.status_code == 200
    data = response.json()
    assert len(data['jobs']) == 3
    assert data['total'] == 3


@pytest.mark.asyncio
async def test_list_import_jobs_pagination(
    async_test_client, test_db, test_user
):
    """Test pagination params."""
    # Create 5 test jobs
    for i in range(5):
        job = ImportJob(
            user_id=test_user.userid,
            source_type='gedcom',
            original_filename=f'test{i}.ged',
            stored_path=f'{test_user.userid}/job{i}/original.ged',
            file_size_bytes=1000,
            content_sha256='abc123',
            status=ImportJobStatus.UPLOADED,
        )
        test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    await test_db.commit()

    response = await async_test_client.get('/api/import-jobs?limit=2&offset=1')

    assert response.status_code == 200
    data = response.json()
    assert len(data['jobs']) == 2
    assert data['total'] == 5
    assert data['limit'] == 2
    assert data['offset'] == 1


@pytest.mark.asyncio
async def test_list_import_jobs_status_filter(
    async_test_client, test_db, test_user
):
    """Test status filter."""
    # Create jobs with different statuses
    for status in [ImportJobStatus.UPLOADED, ImportJobStatus.COMPLETED]:
        job = ImportJob(
            user_id=test_user.userid,
            source_type='gedcom',
            original_filename='test.ged',
            stored_path=f'{test_user.userid}/job/original.ged',
            file_size_bytes=1000,
            content_sha256='abc123',
            status=status,
        )
        test_db.add(job)
    await test_db.commit()

    response = await async_test_client.get('/api/import-jobs?status=completed')

    assert response.status_code == 200
    data = response.json()
    assert len(data['jobs']) == 1
    assert data['jobs'][0]['status'] == 'completed'


# ============================================================================
# GET /api/import-jobs/{id}
# ============================================================================


@pytest.mark.asyncio
async def test_get_import_job_success(async_test_client, test_db, test_user):
    """Test getting job detail."""
    job = ImportJob(
        user_id=test_user.userid,
        source_type='gedcom',
        original_filename='test.ged',
        stored_path=f'{test_user.userid}/job1/original.ged',
        file_size_bytes=1000,
        content_sha256='abc123',
        status=ImportJobStatus.UPLOADED,
    )
    test_db.add(job)
    await test_db.flush()

    # Add stages
    for idx, stage_name in enumerate(['validate', 'parse']):
        stage = ImportJobStage(
            import_job_id=job.id,
            stage_name=stage_name,
            order=idx,
            status=ImportJobStageStatus.PENDING,
        )
        test_db.add(stage)
    await test_db.flush()
    job_id = job.id  # Cache ID before commit
    await test_db.commit()

    response = await async_test_client.get(f'/api/import-jobs/{job_id}')

    assert response.status_code == 200
    data = response.json()
    assert data['id'] == str(job.id)
    assert len(data['stages']) == 2


@pytest.mark.asyncio
async def test_get_import_job_not_found(async_test_client):
    """Test getting non-existent job."""
    fake_id = uuid4()
    response = await async_test_client.get(f'/api/import-jobs/{fake_id}')

    assert response.status_code == 404


# ============================================================================
# POST /api/import-jobs/{id}/pause
# ============================================================================


@pytest.mark.asyncio
async def test_pause_job_success(async_test_client, test_db, test_user):
    """Test pausing running job."""
    job = ImportJob(
        user_id=test_user.userid,
        source_type='gedcom',
        original_filename='test.ged',
        stored_path=f'{test_user.userid}/job/original.ged',
        file_size_bytes=1000,
        content_sha256='abc123',
        status=ImportJobStatus.IN_PROGRESS,
    )
    test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    job_id = job.id  # Cache ID before commit
    await test_db.commit()

    response = await async_test_client.post(f'/api/import-jobs/{job_id}/pause')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'paused'
    assert 'current batch completes' in data['message']


@pytest.mark.asyncio
async def test_pause_job_not_found(async_test_client):
    """Test pausing non-existent job."""
    fake_id = uuid4()
    response = await async_test_client.post(f'/api/import-jobs/{fake_id}/pause')

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_pause_job_already_completed(
    async_test_client, test_db, test_user
):
    """Test pausing completed job."""
    job = ImportJob(
        user_id=test_user.userid,
        source_type='gedcom',
        original_filename='test.ged',
        stored_path=f'{test_user.userid}/job/original.ged',
        file_size_bytes=1000,
        content_sha256='abc123',
        status=ImportJobStatus.COMPLETED,
    )
    test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    job_id = job.id  # Cache ID before commit
    await test_db.commit()

    response = await async_test_client.post(f'/api/import-jobs/{job_id}/pause')

    assert response.status_code == 409


# ============================================================================
# POST /api/import-jobs/{id}/resume
# ============================================================================


@pytest.mark.asyncio
async def test_resume_job_success(async_test_client, test_db, test_user):
    """Test resuming paused job."""
    job = ImportJob(
        user_id=test_user.userid,
        source_type='gedcom',
        original_filename='test.ged',
        stored_path=f'{test_user.userid}/job/original.ged',
        file_size_bytes=1000,
        content_sha256='abc123',
        status=ImportJobStatus.PAUSED,
    )
    test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    job_id = job.id  # Cache ID before commit
    await test_db.commit()

    response = await async_test_client.post(f'/api/import-jobs/{job_id}/resume')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'queued'  # Resume puts job back in queue
    assert 'queued for resumption' in data['message']


@pytest.mark.asyncio
async def test_resume_job_not_paused(async_test_client, test_db, test_user):
    """Test resuming non-paused job."""
    job = ImportJob(
        user_id=test_user.userid,
        source_type='gedcom',
        original_filename='test.ged',
        stored_path=f'{test_user.userid}/job/original.ged',
        file_size_bytes=1000,
        content_sha256='abc123',
        status=ImportJobStatus.IN_PROGRESS,
    )
    test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    job_id = job.id  # Cache ID before commit
    await test_db.commit()

    response = await async_test_client.post(f'/api/import-jobs/{job_id}/resume')

    assert response.status_code == 409


# ============================================================================
# DELETE /api/import-jobs/{id}
# ============================================================================


@pytest.mark.asyncio
async def test_delete_job_success(
    async_test_client, test_db, test_user, temp_gedcom_storage, monkeypatch
):
    """Test deleting job, files, and stages."""
    monkeypatch.setattr(
        'api.routes.import_jobs.GEDCOM_STORAGE_ROOT', temp_gedcom_storage
    )

    job = ImportJob(
        user_id=test_user.userid,
        source_type='gedcom',
        original_filename='test.ged',
        stored_path=f'{test_user.userid}/job/original.ged',
        file_size_bytes=1000,
        content_sha256='abc123',
        status=ImportJobStatus.UPLOADED,
    )
    test_db.add(job)
    await test_db.flush()  # Flush to get job.id
    job_id = job.id  # Cache ID before commit

    # Add stages to verify cascade delete works
    for idx, stage_name in enumerate(['validate', 'parse']):
        stage = ImportJobStage(
            import_job_id=job_id,
            stage_name=stage_name,
            order=idx,
            status=ImportJobStageStatus.PENDING,
        )
        test_db.add(stage)

    # Update stored_path to match actual implementation pattern
    job.stored_path = f'{test_user.userid}/{job_id}/original.ged'
    await test_db.commit()

    # Verify stages exist before delete
    from sqlalchemy import select

    stages_before = await test_db.execute(
        select(ImportJobStage).where(ImportJobStage.import_job_id == job_id)
    )
    assert len(list(stages_before.scalars().all())) == 2

    # Create file using the actual job_id (matching implementation)
    file_path = temp_gedcom_storage / test_user.userid / str(job_id)
    file_path.mkdir(parents=True, exist_ok=True)
    (file_path / 'original.ged').write_text('test content')

    response = await async_test_client.delete(f'/api/import-jobs/{job_id}')

    assert response.status_code == 200
    data = response.json()
    assert data['status'] == 'cancelled'
    assert 'files deleted' in data['message']

    # Verify file deleted
    assert not file_path.exists()

    # Verify stages deleted
    stages_after = await test_db.execute(
        select(ImportJobStage).where(ImportJobStage.import_job_id == job_id)
    )
    assert len(list(stages_after.scalars().all())) == 0


@pytest.mark.asyncio
async def test_delete_job_not_found(async_test_client):
    """Test deleting non-existent job."""
    fake_id = uuid4()
    response = await async_test_client.delete(f'/api/import-jobs/{fake_id}')

    assert response.status_code == 404
