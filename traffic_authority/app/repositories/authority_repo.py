import logging
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Journey, RoadClosure

logger = logging.getLogger(__name__)


class AuthorityRepository:
    async def list_journeys(
        self,
        session: AsyncSession,
        region: str | None,
        status: str | None,
        road: str | None,
        limit: int,
        offset: int,
    ) -> list[Journey]:
        query = select(Journey)
        if region:
            query = query.where(Journey.region == region)
        if status:
            query = query.where(Journey.status == status)
        if road:
            query = query.where(
                Journey.origin.contains(road) | Journey.destination.contains(road)
            )
        query = query.order_by(Journey.created_at.desc()).limit(limit).offset(offset)
        result = await session.execute(query)
        return list(result.scalars().all())

    async def get_journey(self, session: AsyncSession, journey_id: str) -> Journey | None:
        result = await session.execute(select(Journey).where(Journey.id == journey_id))
        return result.scalar_one_or_none()

    async def create_closure(self, session: AsyncSession, closure: RoadClosure) -> RoadClosure:
        session.add(closure)
        await session.flush()
        await session.refresh(closure)
        return closure

    async def find_journeys_on_road(
        self, session: AsyncSession, road_name: str, region: str
    ) -> list[Journey]:
        result = await session.execute(
            select(Journey).where(
                Journey.region == region,
                Journey.status.in_(["PENDING", "CONFIRMED"]),
                Journey.origin.contains(road_name) | Journey.destination.contains(road_name),
            )
        )
        return list(result.scalars().all())

    async def delete_closure(self, session: AsyncSession, closure_id: str) -> None:
        result = await session.execute(
            select(RoadClosure).where(RoadClosure.id == closure_id)
        )
        closure = result.scalar_one_or_none()
        if closure:
            await session.delete(closure)
            await session.flush()

    async def get_journey_stats(self, session: AsyncSession) -> dict:
        result = await session.execute(select(Journey))
        journeys = result.scalars().all()
        stats: dict = defaultdict(lambda: defaultdict(int))
        for j in journeys:
            stats[j.region][j.status] += 1
        return {region: dict(statuses) for region, statuses in stats.items()}
