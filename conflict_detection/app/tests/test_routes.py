import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

from shared.auth import get_current_user
from app.main import app
from app.tests.conftest import *  # noqa: F401, F403


@pytest_asyncio.fixture
async def async_client(db_session, mock_current_user):
    from shared.database import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_health(async_client):
    resp = await async_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["service"] == "conflict_detection"
