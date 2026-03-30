from datetime import datetime, timedelta

import pytest

from shared.auth import get_current_user
from shared.models import Journey
from app.main import app
from app.tests.conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
async def test_list_journeys_empty(async_client):
    resp = await async_client.get("/authority/journeys")
    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_force_cancel_not_found(async_client):
    resp = await async_client.post(
        "/authority/cancel/nonexistent",
        json={"reason": "test cancellation"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_authority_cancel_requires_role(db_session):
    from shared.auth import CurrentUser
    from httpx import AsyncClient, ASGITransport
    from shared.database import get_db

    driver = CurrentUser(id="u1", email="u@t.com", name="U", roles=["driver"])
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_current_user] = lambda: driver
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post(
            "/authority/cancel/some-id",
            json={"reason": "test"},
        )
    app.dependency_overrides.clear()
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_closure(async_client):
    resp = await async_client.post(
        "/authority/closure",
        json={"road_name": "M50 Motorway", "reason": "Maintenance", "region": "EU"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["road_name"] == "M50 Motorway"
    assert data["active"] is True


@pytest.mark.asyncio
async def test_get_stats(async_client):
    resp = await async_client.get("/authority/stats")
    assert resp.status_code == 200
