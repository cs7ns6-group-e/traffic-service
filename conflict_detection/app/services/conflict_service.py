import hashlib
import json
import logging
from datetime import datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from shared.cache import CacheClient
from shared.schemas import ConflictCheckRequest, ConflictCheckResponse

from app.repositories.conflict_repo import ConflictRepository

logger = logging.getLogger(__name__)


class ConflictService:
    CONFLICT_CACHE_TTL = 30
    LOCK_TTL = 60
    CROSS_REGION_TTL = 3600

    def __init__(self, repo: ConflictRepository, db: AsyncSession, cache: CacheClient) -> None:
        self._repo = repo
        self._db = db
        self._cache = cache

    def _build_key(self, origin: str, dest: str, start_time: str) -> str:
        raw = f"{origin}:{dest}:{start_time}"
        return hashlib.md5(raw.encode()).hexdigest()  # noqa: S324

    async def check(self, request: ConflictCheckRequest, region: str) -> ConflictCheckResponse:
        key = self._build_key(request.origin, request.dest, request.start_time)

        cached = self._cache.get(f"conflict:{key}")
        if cached:
            data = json.loads(cached)
            return ConflictCheckResponse(**data)

        if not self._cache.set_lock(key):
            return ConflictCheckResponse(conflict=True, reason="Slot temporarily reserved")

        try:
            start = datetime.fromisoformat(request.start_time)
        except ValueError:
            start = datetime.utcnow()

        db_conflicts = await self._repo.find_conflicts(
            self._db, request.origin, request.dest, start, region
        )

        cross_region_key = f"cross_region:{key}"
        cross_region_reserved = self._cache.exists(cross_region_key)

        if db_conflicts or cross_region_reserved:
            reason = "Cross-region booking conflict" if cross_region_reserved else "Existing booking on same route and time"
            result = ConflictCheckResponse(conflict=True, reason=reason)
            self._cache.set(f"conflict:{key}", json.dumps(result.model_dump()), self.CONFLICT_CACHE_TTL)
            self._cache.release_lock(key)
            return result

        result = ConflictCheckResponse(conflict=False)
        self._cache.set(f"conflict:{key}", json.dumps(result.model_dump()), self.CONFLICT_CACHE_TTL)
        return result

    async def register_cross_region(
        self, origin: str, dest: str, start_time: str, from_region: str
    ) -> None:
        key = self._build_key(origin, dest, start_time)
        self._cache.set(
            f"cross_region:{key}",
            json.dumps({"from_region": from_region}),
            self.CROSS_REGION_TTL,
        )
        logger.info("Registered cross-region booking %s->%s at %s from %s", origin, dest, start_time, from_region)

    async def invalidate(self, origin: str, dest: str, start_time: str) -> None:
        key = self._build_key(origin, dest, start_time)
        self._cache.delete(f"conflict:{key}", f"cross_region:{key}")
        self._cache.release_lock(key)
