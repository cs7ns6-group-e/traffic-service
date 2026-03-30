from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from shared.auth import get_current_user
from shared.models import Journey
from app.main import app
from app.tests.conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
async def test_book_journey_success(async_client, mock_publisher):
    future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    with patch("app.services.journey_service.httpx.AsyncClient") as mock_http:
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(
            return_value=AsyncMock(
                status_code=200,
                json=lambda: {"conflict": False},
                raise_for_status=lambda: None,
            )
        )
        resp = await async_client.post(
            "/journeys",
            json={
                "driver_id": "user-1",
                "origin": "Dublin, Ireland",
                "destination": "Cork, Ireland",
                "start_time": future_time,
                "region": "EU",
            },
        )
    assert resp.status_code == 201
    data = resp.json()
    assert data["driver_id"] == "user-1"
    assert data["status"] == "CONFIRMED"


@pytest.mark.asyncio
async def test_book_journey_conflict_returns_409(async_client):
    future_time = (datetime.utcnow() + timedelta(hours=2)).isoformat()
    with patch("app.services.journey_service.httpx.AsyncClient") as mock_http:
        post_mock = AsyncMock()
        post_mock.raise_for_status = lambda: None
        post_mock.json = lambda: {"conflict": True, "reason": "Slot taken"}
        mock_http.return_value.__aenter__.return_value.post = AsyncMock(return_value=post_mock)
        resp = await async_client.post(
            "/journeys",
            json={
                "driver_id": "user-1",
                "origin": "Dublin, Ireland",
                "destination": "Cork, Ireland",
                "start_time": future_time,
                "region": "EU",
            },
        )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_get_journey_not_found_returns_404(async_client):
    resp = await async_client.get("/journeys/nonexistent-id")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_cancel_journey_not_owner_returns_403(async_client, db_session):
    from shared.auth import get_current_user
    from shared.models import Journey
    from datetime import datetime, timedelta

    journey = Journey(
        id="j-999",
        driver_id="other-user",
        origin="Dublin",
        destination="Cork",
        start_time=datetime.utcnow() + timedelta(hours=1),
        status="CONFIRMED",
        region="EU",
        route_segments=[],
        is_cross_region=False,
    )
    db_session.add(journey)
    await db_session.commit()

    resp = await async_client.delete("/journeys/j-999")
    assert resp.status_code == 403
