import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from shared.auth import CurrentUser, get_current_user
from shared.cache import CacheClient
from shared.database import get_db
from shared.schemas import ConflictCheckRequest, ConflictCheckResponse

from app.services.conflict_service import ConflictService

logger = logging.getLogger(__name__)
router = APIRouter()


def get_conflict_service(db: AsyncSession = Depends(get_db)) -> ConflictService:
    from app.config import get_settings
    from app.repositories.conflict_repo import ConflictRepository

    settings = get_settings()
    repo = ConflictRepository()
    cache = CacheClient(settings.redis_url)
    return ConflictService(repo=repo, db=db, cache=cache)


@router.post("/check", response_model=ConflictCheckResponse)
async def check_conflict(
    request: ConflictCheckRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ConflictService = Depends(get_conflict_service),
) -> ConflictCheckResponse:
    from app.config import get_settings
    settings = get_settings()
    return await service.check(request, settings.region)


@router.post("/cross-region", status_code=201)
async def register_cross_region(
    origin: str,
    dest: str,
    start_time: str,
    from_region: str,
    service: ConflictService = Depends(get_conflict_service),
) -> dict:
    await service.register_cross_region(origin, dest, start_time, from_region)
    return {"status": "registered"}


@router.delete("/invalidate")
async def invalidate_cache(
    origin: Annotated[str, Query()],
    dest: Annotated[str, Query()],
    start_time: Annotated[str, Query()],
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    service: ConflictService = Depends(get_conflict_service),
) -> dict:
    await service.invalidate(origin, dest, start_time)
    return {"status": "invalidated"}
