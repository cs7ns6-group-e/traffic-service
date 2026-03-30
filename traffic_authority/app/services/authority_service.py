import logging

from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser
from shared.exceptions import JourneyNotFoundException
from shared.models import Journey, RoadClosure
from shared.schemas import RoadClosureCreate

from app.repositories.authority_repo import AuthorityRepository

logger = logging.getLogger(__name__)


class AuthorityService:
    def __init__(self, repo: AuthorityRepository, db: AsyncSession) -> None:
        self._repo = repo
        self._db = db

    async def list_journeys(
        self,
        region: str | None,
        status: str | None,
        road: str | None,
        limit: int,
        offset: int,
    ) -> list[Journey]:
        return await self._repo.list_journeys(self._db, region, status, road, limit, offset)

    async def force_cancel(
        self, journey_id: str, user: CurrentUser, reason: str
    ) -> Journey:
        journey = await self._repo.get_journey(self._db, journey_id)
        if not journey:
            raise JourneyNotFoundException(f"Journey {journey_id} not found")
        journey.status = "AUTHORITY_CANCELLED"
        await self._db.flush()
        await self._db.refresh(journey)
        logger.info(
            "Authority %s cancelled journey %s: %s", user.id, journey_id, reason
        )
        return journey

    async def create_closure(
        self, data: RoadClosureCreate, user: CurrentUser
    ) -> RoadClosure:
        closure = RoadClosure(
            road_name=data.road_name,
            region=data.region,
            reason=data.reason,
            created_by=user.id,
        )
        closure = await self._repo.create_closure(self._db, closure)

        # Cancel upcoming journeys on this road
        upcoming = await self._repo.find_journeys_on_road(
            self._db, data.road_name, data.region
        )
        for journey in upcoming:
            journey.status = "AUTHORITY_CANCELLED"
        await self._db.flush()

        logger.info(
            "Road closure created: %s in %s. Cancelled %d journeys.",
            data.road_name,
            data.region,
            len(upcoming),
        )
        return closure

    async def remove_closure(self, closure_id: str, user: CurrentUser) -> None:
        await self._repo.delete_closure(self._db, closure_id)
        logger.info("Closure %s removed by %s", closure_id, user.id)

    async def get_stats(self) -> dict:
        return await self._repo.get_journey_stats(self._db)
