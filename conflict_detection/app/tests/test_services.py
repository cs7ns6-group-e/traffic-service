from datetime import datetime, timedelta

import pytest

from shared.models import Journey
from shared.schemas import ConflictCheckRequest
from app.repositories.conflict_repo import ConflictRepository
from app.services.conflict_service import ConflictService
from app.tests.conftest import *  # noqa: F401, F403


@pytest.mark.asyncio
async def test_conflict_check_ghost_reservation(db_session, mock_cache):
    repo = ConflictRepository()
    service = ConflictService(repo=repo, db=db_session, cache=mock_cache)
    request = ConflictCheckRequest(
        origin="Dublin", dest="Cork", start_time=datetime.utcnow().isoformat(), segments=[]
    )
    result1 = await service.check(request, "EU")
    assert result1.conflict is False

    result2 = await service.check(request, "EU")
    assert result2.conflict is True
    assert "reserved" in (result2.reason or "").lower()


@pytest.mark.asyncio
async def test_conflict_check_db_conflict(db_session, mock_cache):
    start_time = datetime.utcnow() + timedelta(hours=1)
    journey = Journey(
        id="j-existing",
        driver_id="other-driver",
        origin="Dublin",
        destination="Cork",
        start_time=start_time,
        status="CONFIRMED",
        region="EU",
        route_segments=[],
        is_cross_region=False,
    )
    db_session.add(journey)
    await db_session.commit()

    repo = ConflictRepository()
    service = ConflictService(repo=repo, db=db_session, cache=mock_cache)
    request = ConflictCheckRequest(
        origin="Dublin", dest="Cork", start_time=start_time.isoformat(), segments=[]
    )
    result = await service.check(request, "EU")
    assert result.conflict is True


@pytest.mark.asyncio
async def test_conflict_check_cache_hit(db_session, mock_cache):
    import json
    repo = ConflictRepository()
    service = ConflictService(repo=repo, db=db_session, cache=mock_cache)

    from app.services.conflict_service import ConflictService as CS
    start_time = datetime.utcnow().isoformat()
    key = service._build_key("A", "B", start_time)
    mock_cache.set(f"conflict:{key}", json.dumps({"conflict": True, "reason": "cached"}))

    request = ConflictCheckRequest(origin="A", dest="B", start_time=start_time, segments=[])
    result = await service.check(request, "EU")
    assert result.conflict is True
    assert result.reason == "cached"
