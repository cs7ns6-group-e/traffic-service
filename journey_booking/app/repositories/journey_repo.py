import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Journey

logger = logging.getLogger(__name__)


class JourneyRepository:
    async def create(self, session: AsyncSession, journey: Journey) -> Journey:
        session.add(journey)
        await session.flush()
        await session.refresh(journey)
        return journey

    async def get_by_id(self, session: AsyncSession, journey_id: str) -> Journey | None:
        result = await session.execute(select(Journey).where(Journey.id == journey_id))
        return result.scalar_one_or_none()

    async def get_by_driver(self, session: AsyncSession, driver_id: str) -> list[Journey]:
        result = await session.execute(
            select(Journey).where(Journey.driver_id == driver_id).order_by(Journey.created_at.desc())
        )
        return list(result.scalars().all())

    async def update_status(self, session: AsyncSession, journey_id: str, status: str) -> Journey:
        journey = await self.get_by_id(session, journey_id)
        if journey is None:
            from shared.exceptions import JourneyNotFoundException
            raise JourneyNotFoundException(f"Journey {journey_id} not found")
        journey.status = status
        await session.flush()
        await session.refresh(journey)
        return journey

    async def find_conflicts(
        self,
        session: AsyncSession,
        origin: str,
        dest: str,
        start: datetime,
        region: str,
    ) -> list[Journey]:
        window_start = start - timedelta(minutes=30)
        window_end = start + timedelta(minutes=30)
        result = await session.execute(
            select(Journey).where(
                Journey.origin == origin,
                Journey.destination == dest,
                Journey.region == region,
                Journey.start_time >= window_start,
                Journey.start_time <= window_end,
                Journey.status.in_(["PENDING", "CONFIRMED"]),
            )
        )
        return list(result.scalars().all())
