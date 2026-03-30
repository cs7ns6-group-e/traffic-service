import logging
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.models import Journey

logger = logging.getLogger(__name__)


class ConflictRepository:
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
