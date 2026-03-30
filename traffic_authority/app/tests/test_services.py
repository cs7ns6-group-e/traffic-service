from datetime import datetime, timedelta

import pytest

from shared.auth import CurrentUser
from shared.exceptions import JourneyNotFoundException
from shared.models import Journey
from shared.schemas import RoadClosureCreate
from app.repositories.authority_repo import AuthorityRepository
from app.services.authority_service import AuthorityService
from app.tests.conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
async def test_force_cancel_not_found(db_session):
    repo = AuthorityRepository()
    service = AuthorityService(repo=repo, db=db_session)
    user = CurrentUser(id="a1", email="a@t.com", name="A", roles=["traffic_authority"])
    with pytest.raises(JourneyNotFoundException):
        await service.force_cancel("nonexistent", user, "test")


@pytest.mark.asyncio
async def test_create_closure_cancels_journeys(db_session):
    journey = Journey(
        id="j-road",
        driver_id="driver-1",
        origin="M50 Motorway North",
        destination="Cork",
        start_time=datetime.utcnow() + timedelta(hours=1),
        status="CONFIRMED",
        region="EU",
        route_segments=[],
        is_cross_region=False,
    )
    db_session.add(journey)
    await db_session.commit()

    repo = AuthorityRepository()
    service = AuthorityService(repo=repo, db=db_session)
    user = CurrentUser(id="a1", email="a@t.com", name="A", roles=["traffic_authority"])

    closure = await service.create_closure(
        RoadClosureCreate(road_name="M50 Motorway", reason="Emergency", region="EU"), user
    )
    assert closure.road_name == "M50 Motorway"

    await db_session.refresh(journey)
    assert journey.status == "AUTHORITY_CANCELLED"
