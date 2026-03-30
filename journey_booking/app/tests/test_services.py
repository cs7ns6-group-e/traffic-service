from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.auth import CurrentUser
from shared.exceptions import ForbiddenException, JourneyConflictException, JourneyNotFoundException
from shared.models import Journey
from app.repositories.journey_repo import JourneyRepository
from app.services.journey_service import JourneyService, detect_region


@pytest.mark.parametrize(
    "origin,expected_region",
    [
        ("Dublin, Ireland", "EU"),
        ("New York, USA", "US"),
        ("Tokyo, Japan", "APAC"),
        ("Unknown Place", "EU"),
    ],
)
def test_region_detection(origin, expected_region):
    assert detect_region(origin) == expected_region


@pytest.mark.asyncio
async def test_get_journey_not_found(db_session):
    repo = JourneyRepository()
    service = JourneyService(
        repo=repo,
        db=db_session,
        conflict_service_url="http://conflict:8002",
        routing_service_url="http://routing:8004",
        publisher=MagicMock(),
        region="EU",
    )
    user = CurrentUser(id="u1", email="u@t.com", name="U", roles=["driver"])
    with pytest.raises(JourneyNotFoundException):
        await service.get("nonexistent", user)


@pytest.mark.asyncio
async def test_cancel_not_owner(db_session):
    repo = JourneyRepository()
    journey = Journey(
        id="j-1",
        driver_id="other",
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

    service = JourneyService(
        repo=repo,
        db=db_session,
        conflict_service_url="http://conflict:8002",
        routing_service_url="http://routing:8004",
        publisher=MagicMock(),
        region="EU",
    )
    user = CurrentUser(id="u1", email="u@t.com", name="U", roles=["driver"])
    with pytest.raises(ForbiddenException):
        await service.cancel("j-1", user)
